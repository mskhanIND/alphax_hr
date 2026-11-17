"""In-app "Report a problem": a short report from any user, with the page, version, login and recent
errors added automatically. Each report is kept on the site (AlphaX Feedback) and, when the site is
connected, sent to a private GitHub repository as an issue so the development team can answer it.

Connecting a site (done once on the server, never in code or chat):
    bench --site <site> set-config alphax_feedback_repo "owner/repo"
    bench --site <site> set-config alphax_feedback_token "<fine-grained token: that repo only, Issues + Contents read/write>"
"""

import base64
import re

import frappe
from frappe import _
from frappe.utils import cint, cstr, now_datetime

from alphax_hr.api._common import is_hr_manager, login_required, roles, settings

DOCTYPE = "AlphaX Feedback"
TESTER_MARK = "<!-- alphax-tester -->"
API = "https://api.github.com"
MAX_SHOT = 6 * 1024 * 1024  # bytes after decoding
STATUS_LABELS = {  # GitHub label -> status shown to the tester
	"question": "Question for you",
	"retest": "Fixed - please check",
	"in-progress": "Being worked on",
	"not-a-bug": "Answered",
	"reopened": "Reopened",
}


# ------------------------------------------------------------------ config
def _conf():
	repo = cstr(frappe.conf.get("alphax_feedback_repo")).strip()
	token = cstr(frappe.conf.get("alphax_feedback_token")).strip()
	if repo and token and re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
		return repo, token
	return None, None


def enabled() -> bool:
	return bool(cint(settings().get("report_button")))


@frappe.whitelist()
def status():
	login_required()
	repo, _token = _conf()
	return {"enabled": enabled(), "connected": bool(repo)}


# ------------------------------------------------------------------ submit
def _clip(value, n):
	return cstr(value).strip()[:n]


@frappe.whitelist()
def submit(went_wrong: str, doing: str = "", page: str = "", last_error: str = "", recent_pages: str = "",
		   device: str = "", screenshot: str = ""):
	user = login_required()
	if not enabled():
		frappe.throw(_("Reporting problems is switched off on this site."), frappe.PermissionError)
	went_wrong = _clip(went_wrong, 4000)
	if len(went_wrong) < 3:
		frappe.throw(_("Please write what went wrong."))
	doc = frappe.get_doc({
		"doctype": DOCTYPE,
		"title": _clip(re.sub(r"\s+", " ", went_wrong), 120),
		"status": "Received",
		"reporter": user,
		"page": _clip(page, 300),
		"app_version": _app_version(),
		"site": frappe.local.site,
		"roles": ", ".join(sorted(roles(user) - {"All", "Guest", "Desk User"}))[:1000],
		"doing": _clip(doing, 4000),
		"went_wrong": went_wrong,
		"last_error": _clip(last_error, 6000),
		"recent_pages": _clip(recent_pages, 1000),
		"device": _clip(device, 500),
	}).insert(ignore_permissions=True)
	if screenshot:
		_save_screenshot(doc, screenshot)
	frappe.db.commit()
	_relay(doc)
	return _row(doc)


def _app_version():
	import alphax_hr

	return alphax_hr.__version__


def _save_screenshot(doc, data_url):
	m = re.match(r"data:image/(png|jpeg|jpg|webp);base64,(.+)$", cstr(data_url), re.S)
	if not m:
		frappe.throw(_("The screenshot could not be read. Please attach a PNG or JPG picture."))
	ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
	raw = base64.b64decode(m.group(2))
	if len(raw) > MAX_SHOT:
		frappe.throw(_("The picture is too large (over 6 MB)."))
	f = frappe.get_doc({
		"doctype": "File", "file_name": f"{doc.name}.{ext}", "content": raw, "is_private": 1,
		"attached_to_doctype": DOCTYPE, "attached_to_name": doc.name, "attached_to_field": "screenshot",
	}).insert(ignore_permissions=True)
	doc.db_set("screenshot", f.file_url, update_modified=False)


# ------------------------------------------------------------------ GitHub relay
def _gh(method, path, token, **kw):
	import requests

	r = requests.request(method, API + path, timeout=15, headers={
		"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
		"X-GitHub-Api-Version": "2022-11-28", "User-Agent": "alphax-hr"}, **kw)
	if r.status_code >= 400:
		raise RuntimeError(f"GitHub {r.status_code}: {r.text[:300]}")
	return r.json() if r.text else {}


def _issue_body(doc, shot_url=None):
	ctx = [("Site", doc.site), ("Version", doc.app_version), ("Reported by", f"{doc.reporter} ({frappe.utils.get_fullname(doc.reporter)})"),
		   ("Roles", doc.roles), ("Page", doc.page), ("When", f"{doc.creation} (server time)"), ("Browser", doc.device)]
	lines = ["| | |", "|---|---|"] + [f"| {k} | {cstr(v).replace('|', '/').replace(chr(10), ' ')} |" for k, v in ctx if v]
	parts = ["### What went wrong", doc.went_wrong]
	if doc.doing:
		parts += ["### What they were trying to do", doc.doing]
	if doc.last_error:
		parts += ["### Errors shown recently", "```", doc.last_error.replace("```", "'''"), "```"]
	if doc.recent_pages:
		parts += ["### Pages before", doc.recent_pages]
	if shot_url:
		parts += ["### Screenshot", f"![screenshot]({shot_url})"]
	parts += ["### Details", "\n".join(lines), "", f"_In-app report {doc.name}. Labels for replies: `question`, `in-progress`, `retest`, `not-a-bug`; close when done._"]
	return "\n\n".join(parts)


def _upload_shot(doc, repo, token):
	if not doc.screenshot:
		return None
	f = frappe.get_doc("File", {"file_url": doc.screenshot, "attached_to_name": doc.name})
	path = f"screenshots/{frappe.utils.get_datetime(doc.creation).strftime('%Y-%m')}/{frappe.local.site}-{doc.name}.{f.file_url.rsplit('.', 1)[-1]}"
	res = _gh("PUT", f"/repos/{repo}/contents/{path}", token, json={
		"message": f"Screenshot for {doc.name}", "content": base64.b64encode(f.get_content()).decode()})
	return res.get("content", {}).get("html_url", "") + "?raw=true"


def _relay(doc):
	"""Send one report to GitHub. Never raises: a failure is kept and retried by the hourly job."""
	repo, token = _conf()
	if not repo or doc.github_issue:
		return
	try:
		shot = None
		try:
			shot = _upload_shot(doc, repo, token)
		except Exception as e:  # the report still goes, without the picture
			frappe.log_error(f"Feedback screenshot upload failed: {e}", "AlphaX feedback")
		page = (doc.page or "").split("?")[0] or "/"
		data = {"title": f"[{doc.site}] {page} · {doc.title}"[:240], "body": _issue_body(doc, shot)}
		try:
			res = _gh("POST", f"/repos/{repo}/issues", token, json={**data, "labels": ["tester-report"]})
		except RuntimeError:
			res = _gh("POST", f"/repos/{repo}/issues", token, json=data)
		doc.db_set({"github_issue": res["number"], "github_url": res.get("html_url"), "relay_error": ""}, update_modified=False)
	except Exception as e:
		doc.db_set({"relay_error": cstr(e)[:500], "relay_attempts": cint(doc.relay_attempts) + 1}, update_modified=False)
	frappe.db.commit()


def hourly():
	"""Retry reports that could not be sent, and refresh the status of open ones."""
	repo, token = _conf()
	if not repo:
		return
	for name in frappe.get_all(DOCTYPE, filters={"github_issue": ["in", [0, None]], "relay_attempts": ["<", 48]}, pluck="name", limit=50):
		_relay(frappe.get_doc(DOCTYPE, name))
	for name in frappe.get_all(DOCTYPE, filters={"github_issue": [">", 0], "status": ["!=", "Closed"]}, pluck="name", limit=100):
		try:
			_sync(frappe.get_doc(DOCTYPE, name), repo, token)
		except Exception:
			pass
	frappe.db.commit()


def _status_from_issue(issue):
	if issue.get("state") == "closed":
		return "Closed"
	names = [cstr(lbl.get("name")).lower() for lbl in issue.get("labels") or []]
	for key, label in STATUS_LABELS.items():
		if key in names:
			return label
	return "Received"


def _sync(doc, repo, token, with_comments=False):
	issue = _gh("GET", f"/repos/{repo}/issues/{doc.github_issue}", token)
	st = _status_from_issue(issue)
	if st != doc.status and doc.status != "Closed":  # a tester's Pass stays closed
		doc.db_set("status", st)
	if not with_comments:
		return []
	comments = _gh("GET", f"/repos/{repo}/issues/{doc.github_issue}/comments?per_page=50", token)
	out = []
	for c in comments:
		body = cstr(c.get("body"))
		mine = TESTER_MARK in body
		body = body.replace(TESTER_MARK, "")
		body = re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()
		body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "[picture]", body)
		out.append({"text": body.replace("**", "")[:4000], "on": c.get("created_at"), "mine": mine})
	return out


# ------------------------------------------------------------------ the reporter's view
def _row(doc):
	return {"name": doc.name, "title": doc.title, "status": doc.status, "page": doc.page, "creation": str(doc.creation),
			"ticket": doc.github_issue or None, "sent": bool(doc.github_issue), "retest": doc.retest or None,
			"reporter": frappe.utils.get_fullname(doc.reporter) if doc.reporter != frappe.session.user else None}


def _own(name):
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.reporter != frappe.session.user and not is_hr_manager():
		frappe.throw(_("Not your report."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def mine(everyone: int = 0):
	user = login_required()
	filters = {} if cint(everyone) and is_hr_manager() else {"reporter": user}
	names = frappe.get_all(DOCTYPE, filters=filters, pluck="name", order_by="creation desc", limit=100)
	return [_row(frappe.get_doc(DOCTYPE, n)) for n in names]


@frappe.whitelist()
def detail(name: str):
	login_required()
	doc = _own(name)
	replies, live = [], False
	repo, token = _conf()
	if repo and doc.github_issue:
		try:
			replies = _sync(doc, repo, token, with_comments=True)
			live = True
			doc.reload()
		except Exception:
			pass
	return {**_row(doc), "doing": doc.doing, "went_wrong": doc.went_wrong, "last_error": doc.last_error,
			"screenshot": doc.screenshot, "replies": replies, "live": live, "retest_note": doc.retest_note}


@frappe.whitelist()
def retest(name: str, result: str, note: str = ""):
	login_required()
	doc = _own(name)
	if result not in ("Pass", "Fail"):
		frappe.throw(_("Choose Pass or Fail."))
	note = _clip(note, 2000)
	if result == "Fail" and not note:
		frappe.throw(_("Please say what still goes wrong."))
	doc.db_set({"retest": result, "retest_note": note, "retest_on": now_datetime(),
				"status": "Closed" if result == "Pass" else "Reopened"})
	repo, token = _conf()
	if repo and doc.github_issue:
		try:
			n = doc.github_issue
			text = f"{TESTER_MARK}\n**Tester check: {result}** ({frappe.utils.get_fullname(frappe.session.user)}, version {_app_version()})"
			if note:
				text += f"\n\n{note}"
			_gh("POST", f"/repos/{repo}/issues/{n}/comments", token, json={"body": text})
			if result == "Pass":
				_gh("PATCH", f"/repos/{repo}/issues/{n}", token, json={"state": "closed"})
			else:
				_gh("PATCH", f"/repos/{repo}/issues/{n}", token, json={"state": "open"})
				_gh("POST", f"/repos/{repo}/issues/{n}/labels", token, json={"labels": ["reopened"]})
				try:
					_gh("DELETE", f"/repos/{repo}/issues/{n}/labels/retest", token)
				except RuntimeError:
					pass
		except Exception as e:
			frappe.log_error(f"Feedback retest relay failed: {e}", "AlphaX feedback")
	frappe.db.commit()
	return detail(name)


@frappe.whitelist()
def reply(name: str, text: str):
	"""The reporter answers a question from the team."""
	login_required()
	doc = _own(name)
	text = _clip(text, 4000)
	if len(text) < 2:
		frappe.throw(_("Please write your answer."))
	doc.db_set({"status": "Received", "retest_note": text})
	repo, token = _conf()
	if repo and doc.github_issue:
		try:
			body = f"{TESTER_MARK}\n**Tester answer** ({frappe.utils.get_fullname(frappe.session.user)}):\n\n{text}"
			_gh("POST", f"/repos/{repo}/issues/{doc.github_issue}/comments", token, json={"body": body})
			try:
				_gh("DELETE", f"/repos/{repo}/issues/{doc.github_issue}/labels/question", token)
			except RuntimeError:
				pass
		except Exception as e:
			frappe.log_error(f"Feedback reply relay failed: {e}", "AlphaX feedback")
	frappe.db.commit()
	return detail(name)
