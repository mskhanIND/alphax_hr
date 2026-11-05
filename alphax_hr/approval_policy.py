"""Approval policies: business-day timers, escalation, HR reminder and automatic rejection, and optional
multi-level approval chains.

A policy applies to one kind of approval (requests, leave, expenses ...) and, optionally, only to some request or
leave types, companies, departments, branches, designations, amounts or numbers of days. The most specific
enabled policy wins. Without a matching policy the hourly reminder/escalation in Settings applies as before.

Timeline of one approval step (all in working days on the employee's holiday list):
    submitted ── escalate_after_days ──▶ escalated to HR (and the approver's manager)
              ── remind_after_days ───▶ HR reminder to the approver (also sent by HR from Approval delays)
              ── reject_after_days ───▶ rejected automatically with the policy's comment (if auto_reject)

Multi-level chains (requests and leave): the levels are resolved to people when the request is raised and the
request moves level by level. A rejection closes it; when the employee raises it again the policy decides whether
it starts again from the first level or resumes at the level that rejected (earlier approvals are carried over).
"""
from __future__ import annotations

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime

POLICY = "AlphaX Approval Policy"
STATE = "AlphaX Approval State"
HR = "HR"
MANAGEMENT = "Management"
KINDS = {"AlphaX Request": "Requests", "Leave Application": "Leave", "Expense Claim": "Expense claims",
		 "Attendance Request": "Attendance corrections", "Shift Request": "Shift changes",
		 "Compensatory Leave Request": "Compensatory leave", "AlphaX Leave Plan": "Vacation plans"}
MULTI_LEVEL = ("AlphaX Request", "Leave Application")
AUTO_REJECT = ("AlphaX Request", "Leave Application", "Expense Claim", "Shift Request", "AlphaX Leave Plan")
RESUME = "From the level that rejected"
# Never rejected automatically: a resignation not answered within 30 days counts as accepted (Saudi Labor Law).
NEVER_AUTO_REJECT = {"Resignation"}
RESIGNATION_ACCEPT_DAYS = 30


def can_auto_reject(doctype, what=None):
	return doctype in AUTO_REJECT and not (doctype == "AlphaX Request" and what in NEVER_AUTO_REJECT)
DEFAULT_COMMENT = ("Rejected automatically: no decision was taken within the approval time. "
				   "If you still need it, raise the request again.")
LEVEL_TYPES = ("Reporting manager", "Manager's manager", "Specific user", "HR", "Management")


def installed():
	return bool(frappe.db.exists("DocType", POLICY))


def seed():
	"""Two switched-off examples HR can turn on or copy. Never changes a policy that already exists."""
	if not installed():
		return
	examples = [
		{"policy_name": "Standard approval times", "applies_to": "All approvals", "escalate_after_days": 2, "remind_after_days": 1,
		 "reject_after_days": 2, "auto_reject": 1, "rejection_comment": DEFAULT_COMMENT,
		 "description": "Manager has 2 working days, then HR is told; 1 working day later HR reminds the manager; "
						"2 more working days without a decision and the request is rejected with a comment."},
		{"policy_name": "Loans: two managers and finance", "applies_to": "Requests", "multi_level": 1, "escalate_after_days": 2,
		 "remind_after_days": 1, "reject_after_days": 2, "auto_reject": 0, "restart_rule": "From the first level",
		 "description": "Example of levels: reporting manager, then their manager, then HR; management only from 20,000.",
		 "levels": [{"level_label": "Line manager", "approver_type": "Reporting manager"},
					{"level_label": "Second manager", "approver_type": "Manager's manager"},
					{"level_label": "HR", "approver_type": "HR"},
					{"level_label": "Management", "approver_type": "Management", "min_amount": 20000}]},
	]
	for ex in examples:
		if frappe.db.exists(POLICY, ex["policy_name"]):
			continue
		try:
			if ex["policy_name"].startswith("Loans") and frappe.db.exists("AlphaX Request Type", "Loan Request"):
				ex["request_type"] = "Loan Request"
			frappe.get_doc({"doctype": POLICY, "enabled": 0, **ex}).insert(ignore_permissions=True)
		except Exception:  # noqa: BLE001 - examples only
			frappe.log_error(title="AlphaX approval policy example")


# ----------------------------------------------------------------------------- facts and matching
def facts(doc):
	"""What a policy can be conditioned on, for one document."""
	emp = frappe.db.get_value("Employee", doc.get("employee"), ["company", "department", "branch", "designation", "user_id"],
							  as_dict=True) or frappe._dict()
	out = frappe._dict(kind=KINDS.get(doc.doctype), employee=doc.get("employee"), employee_user=emp.user_id,
					   company=doc.get("company") or emp.company, department=doc.get("department") or emp.department,
					   branch=emp.branch, designation=emp.designation, request_type=None, leave_type=None, amount=0.0, days=0.0)
	if doc.doctype == "AlphaX Request":
		out.request_type = doc.request_type
		details = doc.get("details")
		details = (json.loads(details) if isinstance(details, str) and details.strip() else details) or {}
		out.amount = max([flt(details.get(k)) for k in ("amount", "loan_amount", "advance_amount", "total")] + [0])
		if details.get("from_date") and details.get("to_date"):
			out.days = (getdate(details["to_date"]) - getdate(details["from_date"])).days + 1
	elif doc.doctype == "Leave Application":
		out.leave_type, out.days = doc.leave_type, flt(doc.get("total_leave_days"))
	elif doc.doctype == "Expense Claim":
		out.amount = flt(doc.get("total_claimed_amount"))
	elif doc.doctype in ("Attendance Request", "Shift Request"):
		if doc.get("from_date") and doc.get("to_date"):
			out.days = (getdate(doc.to_date) - getdate(doc.from_date)).days + 1
	return out


CONDITIONS = ("request_type", "leave_type", "company", "department", "branch", "designation")


def _policies():
	if not installed():
		return []
	cache = getattr(frappe.local, "alphax_policies", None)
	if cache is None:
		cache = frappe.get_all(POLICY, filters={"enabled": 1}, fields=["name", "applies_to", "priority", "min_amount", "min_days",
																		*CONDITIONS], order_by="priority desc, name asc")
		frappe.local.alphax_policies = cache
	return cache


def clear_cache(*_args, **_kw):
	frappe.local.alphax_policies = None


def matches(p, f):
	if p.applies_to not in ("All approvals", f.kind):
		return False
	for c in CONDITIONS:
		if p.get(c) and p.get(c) != f.get(c):
			return False
	if flt(p.min_amount) and f.amount < flt(p.min_amount):
		return False
	if flt(p.min_days) and f.days < flt(p.min_days):
		return False
	return True


def find(doc, f=None):
	"""The enabled policy for this document (most conditions met wins, then priority), as a Document, or None."""
	f = f or facts(doc)
	if not f.kind:
		return None
	best, score = None, None
	for p in _policies():
		if not matches(p, f):
			continue
		s = (sum(1 for c in CONDITIONS if p.get(c)) + (1 if p.applies_to != "All approvals" else 0)
			 + (1 if flt(p.min_amount) or flt(p.min_days) else 0), cint(p.priority))
		if score is None or s > score:
			best, score = p.name, s
	return frappe.get_cached_doc(POLICY, best) if best else None


# ----------------------------------------------------------------------------- chains
def _manager_of(employee):
	from alphax_hr.api.requests import _manager

	return _manager(employee) if employee else None


def resolve_levels(policy, f, raised_by=None):
	"""The policy's levels that apply here, each resolved to a user, HR or Management. Levels without anyone to ask
	(no manager's manager, the employee themselves, the person who raised it) are skipped."""
	out, seen = [], set()
	mine = {u for u in (f.employee_user, raised_by) if u}
	for row in policy.get("levels") or []:
		if flt(row.min_amount) and f.amount < flt(row.min_amount):
			continue
		if flt(row.min_days) and f.days < flt(row.min_days):
			continue
		who = None
		if row.approver_type == "Reporting manager":
			who = _manager_of(f.employee)
		elif row.approver_type == "Manager's manager":
			boss = _manager_of(f.employee)
			boss_emp = frappe.db.get_value("Employee", {"user_id": boss, "status": "Active"}, "name") if boss else None
			who = _manager_of(boss_emp) if boss_emp else None
		elif row.approver_type == "Specific user":
			who = row.user if row.user and frappe.db.get_value("User", row.user, "enabled") else None
		elif row.approver_type in (HR, MANAGEMENT):
			who = row.approver_type
		if not who or who in mine:
			continue
		if cint(policy.skip_repeat) and who in seen:
			continue
		seen.add(who)
		out.append({"label": row.level_label or _(row.approver_type), "type": row.approver_type, "approver": who})
	return out


def state_of(doctype, name):
	if not installed() or not name:
		return None
	n = frappe.db.get_value(STATE, {"reference_doctype": doctype, "reference_name": name}, "name")
	return frappe.get_doc(STATE, n) if n else None


def levels(state):
	return json.loads(state.levels_json or "[]")


def trail(state):
	return json.loads(state.trail_json or "[]")


def current(state):
	lv = levels(state)
	return lv[state.current_level] if state and state.status == "Pending" and 0 <= cint(state.current_level) < len(lv) else None


def start(doc, policy, chain, previous=None):
	"""Create the approval state for a new document. ``previous``: the rejected document it was raised again from."""
	first, carried = 0, []
	prev = state_of(doc.doctype, previous) if previous else None
	if prev and prev.status == "Rejected" and policy.restart_rule == RESUME:
		old = levels(prev)
		k = cint(prev.rejected_level)
		# resume only while the chain up to the rejecting level is the same
		if len(chain) > k and [x["approver"] for x in old[: k + 1]] == [x["approver"] for x in chain[: k + 1]]:
			first = k
			carried = [dict(t, carried=1) for t in trail(prev) if t.get("action") == "Approved" and cint(t.get("level")) < k]
	st = frappe.get_doc({"doctype": STATE, "reference_doctype": doc.doctype, "reference_name": doc.name, "policy": policy.name,
						 "levels_json": json.dumps(chain, ensure_ascii=False), "current_level": first, "status": "Pending",
						 "level_since": now_datetime(), "previous": previous, "trail_json": json.dumps(carried, ensure_ascii=False)})
	st.insert(ignore_permissions=True)
	return st


def _record(state, user, action, comment=None):
	t = trail(state)
	lv = current(state) or {}
	t.append({"level": cint(state.current_level), "label": lv.get("label"), "approver": lv.get("approver"), "by": user,
			  "by_name": frappe.utils.get_fullname(user) if user else _("System"), "action": action,
			  "at": str(now_datetime()), "comment": (comment or "")[:500]})
	state.trail_json = json.dumps(t, ensure_ascii=False)


def advance(state, user, comment=None):
	"""Approve the current level; returns the next level, or None when the chain is complete."""
	_record(state, user, "Approved", comment)
	state.current_level = cint(state.current_level) + 1
	state.level_since = now_datetime()
	nxt = current(state)
	if not nxt:
		state.status = "Approved"
	state.save(ignore_permissions=True)
	return nxt


def reject(state, user, comment=None, auto=False):
	_record(state, user, "Rejected automatically" if auto else "Rejected", comment)
	state.rejected_level = cint(state.current_level)
	state.status = "Rejected"
	state.save(ignore_permissions=True)


def close(doctype, name, status="Cancelled"):
	st = state_of(doctype, name)
	if st and st.status == "Pending":
		st.status = status
		st.save(ignore_permissions=True)


def share_with(doc, level):
	"""Let the people of this level open the document (employees are usually limited to their own Employee record)."""
	if not level:
		return
	if level["approver"] == HR:
		return
	if level["approver"] == MANAGEMENT:
		from alphax_hr.api.requests import management_users

		users = management_users()
	else:
		users = [level["approver"]]
	submit = 1 if doc.doctype == "Leave Application" else 0
	for u in users:
		frappe.share.add_docshare(doc.doctype, doc.name, u, read=1, write=1, submit=submit, flags={"ignore_share_permission": True})


def can_act(level, user):
	from alphax_hr.api._common import is_hr
	from alphax_hr.api.requests import is_management

	if not level:
		return False
	if level["approver"] == HR:
		return is_hr(user)
	if level["approver"] == MANAGEMENT:
		return is_management(user)
	return level["approver"] == user or is_hr(user)


def summary(doctype, name):
	"""For the record view: the chain with who approved each level and where it waits now."""
	st = state_of(doctype, name)
	if not st:
		return None
	done = {}
	for t in trail(st):
		done[cint(t.get("level"))] = t
	cur = cint(st.current_level)
	rows = []
	for i, lv in enumerate(levels(st)):
		t = done.get(i)
		state = (t or {}).get("action") or ("Waiting" if st.status == "Pending" and i == cur else
											("Skipped" if st.status != "Pending" and i > cur else "Not reached"))
		rows.append({"level": i + 1, "label": lv["label"], "approver": lv["approver"],
					 "approver_name": _group_name(lv["approver"]), "state": state,
					 "by_name": (t or {}).get("by_name"), "at": (t or {}).get("at"), "comment": (t or {}).get("comment"),
					 "carried": cint((t or {}).get("carried"))})
	pol = frappe.db.get_value(POLICY, st.policy, ["policy_name", "restart_rule"], as_dict=True) or {}
	return {"policy": st.policy, "status": st.status, "levels": rows, "previous": st.previous,
			"restart_rule": pol.get("restart_rule"), "since": str(st.level_since)}


def _group_name(approver):
	return {HR: _("HR team"), MANAGEMENT: _("Management")}.get(approver) or frappe.utils.get_fullname(approver)


# ----------------------------------------------------------------------------- leave
def on_leave_insert(doc, method=None):
	"""Leave: start the chain if a multi-level policy applies; the first level becomes the leave approver."""
	try:
		if doc.status != "Open" or not installed():
			return
		f = facts(doc)
		policy = find(doc, f)
		if not policy or not cint(policy.multi_level):
			return
		chain = resolve_levels(policy, f, raised_by=frappe.session.user)
		if not chain:
			return
		st = start(doc, policy, chain, previous=doc.flags.get("alphax_previous"))
		lv = current(st)
		if lv and lv["approver"] not in (HR, MANAGEMENT) and lv["approver"] != doc.leave_approver:
			doc.db_set("leave_approver", lv["approver"], update_modified=False)
		share_with(doc, lv)
	except Exception:  # noqa: BLE001 - never block the leave request itself
		frappe.log_error(title="AlphaX approval chain (leave)")


def on_leave_cancel(doc, method=None):
	close("Leave Application", doc.name)


# ----------------------------------------------------------------------------- working days
def _holidays(employee):
	cache = getattr(frappe.local, "alphax_hol", None)
	if cache is None:
		cache = frappe.local.alphax_hol = {}
	hl = None
	if employee:
		hl = frappe.db.get_value("Employee", employee, "holiday_list")
		if not hl:
			company = frappe.db.get_value("Employee", employee, "company")
			hl = frappe.db.get_value("Company", company, "default_holiday_list") if company else None
	if hl not in cache:
		cache[hl] = {getdate(d) for d in frappe.get_all("Holiday", filters={"parent": hl}, pluck="holiday_date")} if hl else set()
	return cache[hl]


def working_days(since, now=None, employee=None):
	"""Whole working days elapsed since ``since`` (a day counts once the same time of day has passed on it)."""
	since, now = get_datetime(since), get_datetime(now or now_datetime())
	hol = _holidays(employee)
	n, d = 0, since.date() + timedelta(days=1)
	while d <= now.date():
		if d not in hol and (d < now.date() or now.time() >= since.time()):
			n += 1
		d += timedelta(days=1)
	return n


def add_working_days(since, days, employee=None):
	"""The moment ``days`` working days after ``since`` (for showing deadlines)."""
	since = get_datetime(since)
	hol, d, n = _holidays(employee), since, 0
	while n < cint(days):
		d += timedelta(days=1)
		if d.date() not in hol:
			n += 1
	return d


# ----------------------------------------------------------------------------- automatic rejection
def auto_reject(item, policy):
	"""Reject one waiting document because nobody decided in time; the policy's comment explains why."""
	if not can_auto_reject(item.doctype, item.get("what")):
		return False
	comment = (policy.rejection_comment or _(DEFAULT_COMMENT)).strip()
	dt, name = item.doctype, item.name
	doc = frappe.get_doc(dt, name)
	note = _("Rejected automatically by {0}: {1}").format(_("the approval policy"), comment)
	if dt == "AlphaX Request":
		from alphax_hr.api import requests

		requests.auto_reject(doc, comment)
	elif dt == "Leave Application":
		doc.add_comment("Comment", frappe.utils.escape_html(note))
		doc.status = "Rejected"
		doc.flags.ignore_permissions = True
		doc.submit()
	elif dt == "Expense Claim":
		doc.add_comment("Comment", frappe.utils.escape_html(note))
		doc.approval_status = "Rejected"
		doc.flags.ignore_permissions = True
		doc.save()
	elif dt == "Shift Request":
		doc.add_comment("Comment", frappe.utils.escape_html(note))
		doc.status = "Rejected"
		doc.flags.ignore_permissions = True
		doc.submit()
	elif dt == "AlphaX Leave Plan":
		doc.add_comment("Comment", frappe.utils.escape_html(note))
		doc.status = "Rejected"
		if doc.meta.has_field("decided_on"):
			doc.decided_on = now_datetime()
		doc.save(ignore_permissions=True)
	else:
		return False
	st = state_of(dt, name)
	if st and st.status == "Pending":
		reject(st, None, comment, auto=True)
	return True
