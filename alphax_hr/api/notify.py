"""Phone / browser notifications for AlphaX users (approvals, decisions, messages, announcements)."""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime, nowdate

from alphax_hr.api._common import login_required, parse_json, settings
from alphax_hr import push

DOCTYPE = "AlphaX Push Subscription"


def keys():
	"""VAPID keys, created once and kept in AlphaX HR Settings (private key encrypted)."""
	from frappe.utils.password import get_decrypted_password, set_encrypted_password

	pub = frappe.db.get_single_value("AlphaX HR Settings", "push_public_key")
	priv = get_decrypted_password("AlphaX HR Settings", "AlphaX HR Settings", "push_private_key", raise_exception=False) if pub else None
	if not (pub and priv):
		priv, pub = push.new_vapid_keys()
		frappe.db.set_single_value("AlphaX HR Settings", "push_public_key", pub)
		set_encrypted_password("AlphaX HR Settings", "AlphaX HR Settings", priv, "push_private_key")
	return priv, pub


@frappe.whitelist()
def public_key():
	login_required()
	return {"key": keys()[1], "enabled": bool(frappe.db.exists("DocType", DOCTYPE))}


@frappe.whitelist(methods=["POST"])
def subscribe(subscription, device=None):
	user = login_required()
	sub = parse_json(subscription, {}) or {}
	endpoint = sub.get("endpoint") or ""
	k = sub.get("keys") or {}
	if not endpoint.startswith("https://") or not k.get("p256dh") or not k.get("auth"):
		frappe.throw(_("Invalid push subscription."))
	h = push.endpoint_hash(endpoint)
	name = frappe.db.get_value(DOCTYPE, {"endpoint_hash": h})
	doc = frappe.get_doc(DOCTYPE, name) if name else frappe.new_doc(DOCTYPE)
	doc.update({"user": user, "endpoint": endpoint, "endpoint_hash": h, "p256dh": k["p256dh"], "auth": k["auth"],
				"device": (device or "")[:120], "last_error": None})
	doc.flags.ignore_permissions = True
	doc.save()
	return {"ok": True, "devices": frappe.db.count(DOCTYPE, {"user": user})}


@frappe.whitelist(methods=["POST"])
def unsubscribe(endpoint):
	user = login_required()
	frappe.db.delete(DOCTYPE, {"endpoint_hash": push.endpoint_hash(endpoint or ""), "user": user})
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def test():
	user = login_required()
	n = send([user], _app_name(), _("Notifications are working on this device."), "/alphax", now=True)
	return {"sent": n}


def send(users, title, body, url="/alphax", tag=None, now=False):
	"""Queue a notification to every device of these users. Returns the number of devices (when sent now)."""
	users = sorted({u for u in (users or []) if u and u not in ("Guest", "Administrator")})
	if not users or not frappe.db.exists("DocType", DOCTYPE) or not frappe.db.exists(DOCTYPE, {"user": ["in", users]}):
		return 0
	payload = {"title": title, "body": (body or "")[:240], "url": url, "tag": tag}
	if now or frappe.flags.in_test:
		return deliver(users, payload)
	frappe.enqueue("alphax_hr.api.notify.deliver", users=users, payload=payload, queue="short", enqueue_after_commit=True)
	return 0


def deliver(users, payload):
	import requests

	priv, pub = keys()
	subject = settings().get("push_contact") or f"mailto:hr@{frappe.local.site}"
	if not subject.startswith(("mailto:", "https://")):
		subject = "mailto:" + subject
	body = json.dumps(payload).encode()
	sent = 0
	for s in frappe.get_all(DOCTYPE, filters={"user": ["in", users]}, fields=["name", "endpoint", "p256dh", "auth"]):
		try:
			res = requests.post(s.endpoint, data=push.encrypt(body, s.p256dh, s.auth), timeout=10, headers={
				"Authorization": push.vapid_header(s.endpoint, priv, pub, subject), "TTL": "86400",
				"Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "Urgency": "normal"})
			if res.status_code in (404, 410):
				frappe.db.delete(DOCTYPE, {"name": s.name})  # the browser dropped this subscription
			elif res.status_code >= 400:
				frappe.db.set_value(DOCTYPE, s.name, "last_error", f"{res.status_code}: {res.text[:300]}")
			else:
				sent += 1
		except Exception as exc:  # noqa: BLE001 - one bad device must not stop the others
			frappe.db.set_value(DOCTYPE, s.name, "last_error", str(exc)[:300])
	return sent


# ------------------------------------------------------------------ hooks
def _app_name():
	return frappe.get_cached_doc("AlphaX HR Settings").get("portal_title") or "AlphaX HR"


def _safe(fn):
	"""A notification problem must never block saving the record that triggered it."""
	import functools

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except Exception:  # noqa: BLE001
			frappe.log_error(title=f"AlphaX notification: {fn.__name__}")

	return wrapper


@_safe
def on_notification_log(doc, method=None):
	"""Every Frappe/AlphaX alert to a user (messages, warnings, assignments, mentions) also goes to their phone."""
	if doc.flags.get("alphax_pushed"):  # sent by alerts.event with its own push
		return
	if doc.for_user and doc.get("document_type") not in ("Leave Application",):
		url = "/alphax"
		if doc.document_type == "AlphaX Request":
			url = "/alphax/me/requests"
		elif doc.document_type == "AlphaX Penalty":
			url = "/alphax/me/warnings"
		send([doc.for_user], _app_name(), frappe.utils.strip_html(doc.subject or ""), url)


def _dates(doc):
	return f"{frappe.utils.formatdate(doc.from_date)} → {frappe.utils.formatdate(doc.to_date)}"


@_safe
def on_leave_insert(doc, method=None):
	from alphax_hr.api import alerts
	from alphax_hr.leave_engine import counting_rule

	if doc.status != "Open":
		return
	ref = ("Leave Application", doc.name)
	days = f" · {doc.total_leave_days:g} " + _("day(s)") if doc.get("total_leave_days") else ""
	rule = counting_rule(doc.leave_type)
	if rule and cint(rule.emergency):
		alerts.event("Emergency leave", _("Emergency leave: {0}").format(doc.employee_name),
					 f"{doc.leave_type}, {_dates(doc)}{days}. {doc.description or ''}".strip(), employee=doc.employee,
					 managers=[doc.leave_approver] if doc.leave_approver else None, url="/alphax/approvals", doc=ref, tag=doc.name)
		return
	if doc.leave_approver:
		alerts.event("Leave request", _("Leave request from {0}").format(doc.employee_name),
					 f"{doc.leave_type}, {_dates(doc)}{days}", employee=doc.employee, managers=[doc.leave_approver],
					 url="/alphax/approvals", doc=ref, tag=doc.name)


@_safe
def on_leave_decided(doc, method=None):
	from alphax_hr.api import alerts

	if doc.status in ("Approved", "Rejected"):
		alerts.event("Leave decision", _("Leave {0}").format(_(doc.status).lower()), f"{doc.leave_type}, {_dates(doc)}",
					 employee=doc.employee, url="/alphax/me/leave", doc=("Leave Application", doc.name), tag=doc.name)


@_safe
def request_created(doc):
	from alphax_hr.api import alerts

	if doc.status == "Pending Manager" and doc.approver:
		managers = [doc.approver]
	elif doc.status == "Pending HR":
		managers = list(alerts.hr_users())
	elif doc.status == "Pending Management":
		from alphax_hr.api.requests import management_users

		managers = management_users()
	else:
		return
	alerts.event("Request submitted", _("New request: {0}").format(_(doc.request_type)), doc.employee_name or "",
				 employee=doc.employee, managers=managers, url="/alphax/requests" if doc.status == "Pending HR" else "/alphax/approvals",
				 doc=("AlphaX Request", doc.name), tag=doc.name)


@_safe
def request_decided(doc):
	from alphax_hr.api import alerts

	user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if user and user != frappe.session.user:
		alerts.event("Request decision", _(doc.request_type), _("Your request is now: {0}").format(_(doc.status)),
					 employee=doc.employee, url="/alphax/me/requests", doc=("AlphaX Request", doc.name), tag=doc.name)
	if doc.status in ("Pending Manager", "Pending HR", "Pending Management"):
		request_created(doc)


@_safe
def announcement(doc):
	from alphax_hr.api import alerts

	if getdate(doc.publish_on) > getdate(nowdate()):
		return
	filters = {"status": "Active", "user_id": ["is", "set"]}
	if doc.audience == "Company":
		filters["company"] = doc.company
	elif doc.audience == "Department":
		filters["department"] = doc.department
	users = frappe.get_all("Employee", filters=filters, pluck="user_id")
	alerts.event("Announcement", doc.title, frappe.utils.strip_html(doc.body or "")[:160], users=users, url="/alphax",
				 doc=("AlphaX Announcement", doc.name), tag=f"ann-{doc.name}")


@_safe
def on_checkin(doc, method=None):
	"""Every punch (app, device or import of today's punches) can confirm to the employee and flag late arrival."""
	if frappe.flags.in_import or frappe.flags.in_migrate or not doc.time:
		return
	if (now_datetime() - get_datetime(doc.time)).total_seconds() > 6 * 3600:
		return  # a historical sync, not a live punch
	frappe.enqueue("alphax_hr.api.alerts.on_checkin", queue="short", enqueue_after_commit=True, now=bool(frappe.flags.in_test),
				   employee=doc.employee, log_type=doc.log_type or "IN", when=get_datetime(doc.time),
				   location=doc.get("alphax_location"))


@frappe.whitelist()
def status():
	user = login_required()
	return {"devices": frappe.db.count(DOCTYPE, {"user": user}) if frappe.db.exists("DocType", DOCTYPE) else 0}


def daily_announcements():
	"""Announcements scheduled for today are pushed the morning they go live."""
	if not frappe.db.exists("DocType", "AlphaX Announcement"):
		return
	for name in frappe.get_all("AlphaX Announcement", filters={"publish_on": nowdate(), "creation": ["<", nowdate()]}, pluck="name"):
		announcement(frappe.get_doc("AlphaX Announcement", name))
