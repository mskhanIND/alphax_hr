"""Integration tests against a real Frappe + ERPNext + HRMS site.

Usage (from the bench directory):
    ./env/bin/python apps/alphax_hr/tests/integration/run_frappe_tests.py SITE_NAME

Creates an isolated test company, users for each role, then exercises the
AlphaX API as each user, including negative (security) cases.
Safe to re-run: fixtures are reused.
"""
import sys
import traceback

import frappe
from frappe.utils import add_days, getdate, nowdate

COMPANY = "AlphaX Test Co"
ABBR = "AXT"
PASSED, FAILED = [], []


def check(name, fn):
    try:
        fn()
        PASSED.append(name)
        print(f"  PASS  {name}")
    except Exception as exc:  # noqa: BLE001
        FAILED.append(name)
        print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
        traceback.print_exc(limit=3)
    finally:
        frappe.set_user("Administrator")
        frappe.db.rollback() if False else None


def expect_error(fn, *types):
    try:
        fn()
    except types:
        frappe.clear_messages()
        return
    except Exception as exc:  # noqa: BLE001
        frappe.clear_messages()
        if types and not isinstance(exc, types):
            raise AssertionError(f"expected {types}, got {type(exc).__name__}: {exc}")
        return
    raise AssertionError(f"expected error {types}")


# --------------------------------------------------------------- fixtures
def ensure(doctype, filters, values):
    name = frappe.db.exists(doctype, filters)
    if name:
        return frappe.get_doc(doctype, name)
    doc = frappe.get_doc({"doctype": doctype, **filters, **values})
    doc.insert(ignore_permissions=True)
    return doc


def make_user(email, first, roles):
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "send_welcome_email": 0,
                        "new_password": "Test@12345!x"}).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    user.add_roles(*roles)
    return email


def setup_fixtures():
    frappe.set_user("Administrator")
    year = getdate(nowdate()).year
    if not frappe.db.exists("Warehouse Type", "Transit"):
        # Fresh site without the setup wizard: install ERPNext's base fixtures.
        from erpnext.setup.setup_wizard.operations.install_fixtures import install as install_fixtures

        install_fixtures(country="Saudi Arabia")
    if not frappe.db.exists("Gender", "Female"):
        from frappe.desk.page.setup_wizard.install_fixtures import install as install_frappe_fixtures

        install_frappe_fixtures()
    if not frappe.db.exists("Company", COMPANY):
        frappe.get_doc({"doctype": "Company", "company_name": COMPANY, "abbr": ABBR, "default_currency": "SAR",
                        "country": "Saudi Arabia", "chart_of_accounts": "Standard"}).insert(ignore_permissions=True)
    hl_name = f"AXT {year}"
    if not frappe.db.exists("Holiday List", hl_name):
        hl = frappe.get_doc({"doctype": "Holiday List", "holiday_list_name": hl_name,
                             "from_date": f"{year}-01-01", "to_date": f"{year + 1}-12-31",
                             "weekly_off": "Friday"})
        hl.get_weekly_off_dates()
        hl.insert(ignore_permissions=True)
    frappe.db.set_value("Company", COMPANY, "default_holiday_list", hl_name)
    dept = ensure("Department", {"department_name": "AXT Operations", "company": COMPANY}, {}).name
    hr = make_user("hr@axt.test", "Hana", ["HR Manager", "HR User", "Employee"])
    mgr = make_user("mgr@axt.test", "Majed", ["Employee", "Leave Approver"])
    emp = make_user("emp@axt.test", "Eman", ["Employee"])
    emp2 = make_user("emp2@axt.test", "Omar", ["Employee"])

    def employee(first, user, saudi, approver=None, joining="2021-01-10"):
        name = frappe.db.get_value("Employee", {"user_id": user})
        if name:
            return name
        doc = frappe.get_doc({"doctype": "Employee", "first_name": first, "last_name": "Test", "gender": "Female",
                              "date_of_birth": "1990-05-05", "date_of_joining": joining, "company": COMPANY,
                              "department": dept, "user_id": user, "holiday_list": hl_name, "status": "Active",
                              "leave_approver": approver, "alphax_is_saudi": saudi,
                              "alphax_gosi_registration_date": "2025-02-01" if saudi else None,
                              "alphax_iqama_number": None if saudi else "2" + str(abs(hash(user)))[:9],
                              "alphax_iqama_expiry": None if saudi else add_days(nowdate(), 20)})
        doc.insert(ignore_permissions=True)
        return doc.name

    e_hr = employee("Hana", hr, 1)
    # Real-world setup: HR staff must not be restricted to their own Employee record.
    frappe.db.set_value("Employee", e_hr, "create_user_permission", 0)
    for up in frappe.get_all("User Permission", filters={"user": hr, "allow": "Employee"}, pluck="name"):
        frappe.delete_doc("User Permission", up, ignore_permissions=True)
    e_hr = employee("Hana", hr, 1)
    e_mgr = employee("Majed", mgr, 1)
    e_emp = employee("Eman", emp, 0, approver=mgr)
    e_emp2 = employee("Omar", emp2, 0, approver=mgr, joining="2025-03-01")
    lt = ensure("Leave Type", {"leave_type_name": "AXT Annual"}, {"max_continuous_days_allowed": 0}).name
    for e in (e_emp, e_emp2):
        if not frappe.db.exists("Leave Allocation", {"employee": e, "leave_type": lt, "docstatus": 1}):
            frappe.get_doc({"doctype": "Leave Allocation", "employee": e, "leave_type": lt,
                            "from_date": f"{year}-01-01", "to_date": f"{year}-12-31",
                            "new_leaves_allocated": 21}).insert(ignore_permissions=True).submit()
    # Reset transactional test data so the suite is repeatable.
    for wf in frappe.get_all("Workflow", filters={"document_type": "Leave Application", "is_active": 1}, pluck="name"):
        frappe.db.set_value("Workflow", wf, "is_active", 0)
    for e in (e_emp, e_emp2):
        for la in frappe.get_all("Leave Application", filters={"employee": e}, fields=["name", "docstatus"]):
            for att in frappe.get_all("Attendance", filters={"leave_application": la.name, "docstatus": 1}, pluck="name"):
                frappe.get_doc("Attendance", att).cancel()
            if la.docstatus == 1:
                frappe.get_doc("Leave Application", la.name).cancel()
            frappe.db.delete("Leave Ledger Entry", {"transaction_name": la.name})
            frappe.db.delete("Attendance", {"leave_application": la.name})
            frappe.db.delete("Leave Application", {"name": la.name})
        frappe.db.delete("Employee Checkin", {"employee": e})
    frappe.db.commit()
    return dict(hr=hr, mgr=mgr, emp=emp, emp2=emp2, e_emp=e_emp, e_emp2=e_emp2, e_mgr=e_mgr, lt=lt, year=year)


def next_working_pair(start_offset):
    d = getdate(add_days(nowdate(), start_offset))
    while d.weekday() in (4,):  # skip Friday
        d = add_days(d, 1)
        d = getdate(d)
    return str(d), str(d)


# ------------------------------------------------------------------- tests
def run(site):
    frappe.init(site=site, sites_path=".")
    frappe.connect()
    try:
        f = setup_fixtures()
        from alphax_hr.api import approvals, compliance, ess, hr, payroll, session

        print("\n== Guest is locked out")
        def guest_blocked():
            frappe.set_user("Guest")
            for fn in (session.boot, ess.my_profile, hr.employees, compliance.overview, approvals.inbox):
                expect_error(fn, frappe.AuthenticationError, frappe.PermissionError, frappe.DoesNotExistError)
        check("guest cannot call any endpoint", guest_blocked)

        print("\n== Employee self-service")
        def emp_boot():
            frappe.set_user(f["emp"])
            b = session.boot()
            assert b["persona"] == {"employee": True, "approver": False, "hr": False, "hr_manager": False}, b["persona"]
        check("employee persona resolved on server", emp_boot)

        def emp_profile():
            frappe.set_user(f["emp"])
            p = ess.my_profile()
            assert p["name"] == f["e_emp"] and p["annual_entitlement_days"] == 30, p
        check("my_profile scoped + Saudi entitlement (5+ yrs => 30)", emp_profile)

        state = {}
        def emp_apply():
            frappe.set_user(f["emp"])
            bal = ess.my_leave_balances()
            assert any(b["leave_type"] == f["lt"] and b["balance"] == 21 for b in bal["balances"]), bal
            frm, to = next_working_pair(15)
            r = ess.apply_leave(f["lt"], frm, to, "family visit")
            assert r["total_leave_days"] == 1 and not r["warnings"], r
            state["leave"] = r["name"]
            assert frappe.db.get_value("Leave Application", r["name"], "leave_approver") == f["mgr"]
        check("apply_leave sets approver server-side, counts days", emp_apply)

        def emp_cannot_hr():
            frappe.set_user(f["emp"])
            for fn in (hr.employees, compliance.overview, lambda: payroll.gosi_register()):
                expect_error(fn, frappe.PermissionError)
        check("employee blocked from HR/payroll/compliance APIs", emp_cannot_hr)

        def emp2_isolation():
            frappe.set_user(f["emp2"])
            expect_error(lambda: ess.withdraw_leave(state["leave"]), frappe.PermissionError)
            mine = [r.name for r in ess.my_leave_applications()]
            assert state["leave"] not in mine
            expect_error(lambda: approvals.act("Leave Application", state["leave"], "Approve"), frappe.PermissionError)
        check("other employee cannot see/withdraw/approve my leave", emp2_isolation)

        def checkin():
            frappe.set_user(f["emp"])
            s = ess.check_in("IN")
            assert s["logs"] and s["next_action"] == "OUT", s
            expect_error(lambda: ess.check_in("IN"), frappe.ValidationError)
            expect_error(lambda: ess.check_in("SIDEWAYS"), frappe.ValidationError)
        check("check-in + duplicate guard + input validation", checkin)

        def attendance():
            frappe.set_user(f["emp"])
            a = ess.my_attendance()
            assert "summary" in a and a["today"]["next_action"] == "OUT"
        check("my_attendance month view", attendance)

        print("\n== Manager approvals")
        def mgr_inbox_and_approve():
            frappe.set_user(f["mgr"])
            b = session.boot()
            assert b["persona"]["approver"]
            box = approvals.inbox()
            row = next(r for r in box["items"] if r["name"] == state["leave"])
            assert "Approve" in row["actions"] and "Reject" in row["actions"], row
            expect_error(lambda: approvals.act("Leave Application", state["leave"], "Delete"), frappe.PermissionError)
            expect_error(lambda: approvals.act("User", "Administrator", "Approve"), frappe.PermissionError)
            res = approvals.act("Leave Application", state["leave"], "Approve", "enjoy")
            assert res["docstatus"] == 1 and res["status"] == "Approved", res
        check("manager inbox, approve -> submitted; bad actions refused", mgr_inbox_and_approve)

        def withdraw_after_approval():
            frappe.set_user(f["emp"])
            expect_error(lambda: ess.withdraw_leave(state["leave"]), frappe.ValidationError)
        check("approved leave cannot be withdrawn by employee", withdraw_after_approval)

        def reject_flow():
            frappe.set_user(f["emp2"])
            frm, to = next_working_pair(25)
            name = ess.apply_leave(f["lt"], frm, to)["name"]
            frappe.set_user(f["mgr"])
            res = approvals.act("Leave Application", name, "Reject")
            assert res["status"] == "Rejected", res
        check("reject flow", reject_flow)

        def workflow_named_submit():
            # Regression for the portal bug: a workflow action literally called "Submit".
            frappe.set_user("Administrator")
            wf_name = "AXT Leave WF"
            for st in ("Draft", "Pending", "Approved"):
                ensure("Workflow State", {"workflow_state_name": st}, {})
            for a in ("Submit", "Approve"):
                ensure("Workflow Action Master", {"workflow_action_name": a}, {})
            if frappe.db.exists("Workflow", wf_name):
                wf = frappe.get_doc("Workflow", wf_name)
                wf.is_active = 1
                wf.save(ignore_permissions=True)
            else:
                frappe.get_doc({
                    "doctype": "Workflow", "workflow_name": wf_name, "document_type": "Leave Application",
                    "is_active": 1, "workflow_state_field": "workflow_state", "send_email_alert": 0,
                    "states": [
                        {"state": "Draft", "doc_status": "0", "allow_edit": "Employee"},
                        {"state": "Pending", "doc_status": "0", "allow_edit": "Leave Approver"},
                        {"state": "Approved", "doc_status": "1", "allow_edit": "Leave Approver",
                         "update_field": "status", "update_value": "Approved"},
                    ],
                    "transitions": [
                        {"state": "Draft", "action": "Submit", "next_state": "Pending", "allowed": "Employee", "allow_self_approval": 1},
                        {"state": "Pending", "action": "Approve", "next_state": "Approved", "allowed": "Leave Approver", "allow_self_approval": 0},
                    ],
                }).insert(ignore_permissions=True)
            frappe.db.commit()
            try:
                frappe.set_user(f["emp2"])
                frm, to = next_working_pair(30)
                name = ess.apply_leave(f["lt"], frm, to)["name"]
                box = approvals.inbox()
                own = next((r for r in box["items"] if r["name"] == name), None)
                assert own and own["actions"] == ["Submit"], own
                r = approvals.act("Leave Application", name, "Submit")
                assert r["workflow_state"] == "Pending", r
                expect_error(lambda: approvals.act("Leave Application", name, "Approve"), frappe.PermissionError)
                frappe.set_user(f["mgr"])
                r = approvals.act("Leave Application", name, "Approve")
                assert r["workflow_state"] == "Approved" and r["docstatus"] == 1, r
            finally:
                frappe.set_user("Administrator")
                frappe.db.set_value("Workflow", wf_name, "is_active", 0)
                frappe.db.commit()
        check("workflow with an action named 'Submit' works end-to-end", workflow_named_submit)

        print("\n== HR core")
        def hr_directory():
            frappe.set_user(f["hr"])
            res = hr.employees(search="Eman")
            assert res["total"] >= 1 and res["rows"][0]["employee_name"].startswith("Eman"), res
            d = hr.employee(f["e_emp"])
            assert d["documents"]["iqama"] == "within_30", d["documents"]
            assert "no_user_account" not in d["issues"]
        check("directory search + profile with Iqama expiry bucket", hr_directory)

        def hr_update_stale():
            frappe.set_user(f["hr"])
            d = hr.employee(f["e_emp"])
            upd = hr.update_employee(f["e_emp"], {"cell_number": "0555000001", "status": "Left", "owner": "x"}, d["modified"])
            assert upd["sections"]["contact"]["cell_number"] == "0555000001"
            assert upd["sections"]["job"]["status"] == "Active", "status must not be editable here"
            expect_error(lambda: hr.update_employee(f["e_emp"], {"cell_number": "1"}, d["modified"]), frappe.TimestampMismatchError)
        check("update_employee: whitelisted fields + stale-write rejection", hr_update_stale)

        def hr_create():
            frappe.set_user(f["hr"])
            expect_error(lambda: hr.create_employee({"first_name": "X"}), frappe.ValidationError)
            if not frappe.db.exists("Employee", {"first_name": "Nora", "company": COMPANY}):
                r = hr.create_employee({"first_name": "Nora", "last_name": "New", "gender": "Female",
                                        "date_of_birth": "1995-01-01", "date_of_joining": nowdate(), "company": COMPANY,
                                        "alphax_is_saudi": 1})
                assert "gosi_registration_date_missing" in r["issues"], r["issues"]
        check("create_employee validates + flags missing GOSI date", hr_create)

        def lookup_allowlist():
            frappe.set_user(f["hr"])
            assert hr.lookup("Department", "AXT")
            expect_error(lambda: hr.lookup("User Permission", ""), frappe.PermissionError)
        check("lookup restricted to HR doctypes", lookup_allowlist)

        print("\n== Payroll & Saudi rules")
        def gosi_register():
            frappe.set_user(f["hr"])
            frappe.db.set_single_value("AlphaX HR Settings", "default_company", COMPANY)
            r = payroll.gosi_register()
            systems = {row["employee"]: row["system"] for row in r["rows"]}
            assert systems[f["e_mgr"]] == "New" and systems[f["e_emp"]] == "Non-Saudi", systems
            assert frappe.db.count("GOSI Contribution Rate") >= 7
        check("GOSI register classifies by registration date; rates seeded", gosi_register)

        def eosb():
            frappe.set_user(f["hr"])
            r = payroll.eosb(f["e_emp"], exit_date="2026-01-09", reason="Resignation", monthly_wage=10000)
            assert abs(r["service_years"] - 5.0) < 0.01 and abs(r["entitlement_factor"] - 2 / 3) < 0.001, r
        check("EOSB via API (resignation, 5 years => 2/3)", eosb)

        def compliance_overview():
            frappe.set_user(f["hr"])
            o = compliance.overview(COMPANY)
            keys = {c["key"]: c["count"] for c in o["checks"]}
            assert o["documents"]["iqama"]["within_30"] >= 2, o["documents"]
            assert "gosi_registration_date_missing" in keys
            assert 0 <= o["nitaqat"]["saudization_percent"] <= 100
        check("compliance overview: documents, readiness checks, Nitaqat", compliance_overview)

        def legacy_import_guard():
            frappe.set_user(f["mgr"])
            expect_error(lambda: compliance.import_legacy_fields(1), frappe.PermissionError)
            frappe.set_user(f["hr"])
            r = compliance.import_legacy_fields(1)
            assert r["dry_run"] is True
        check("legacy import is HR-Manager only and dry-runs", legacy_import_guard)

        print("\n== /alphax page")
        def www_page():
            from alphax_hr.www import alphax as page
            frappe.set_user(f["emp"])
            frappe.local.request = type("R", (), {"path": "/alphax"})()
            page.get_csrf_token = lambda: "test-token"
            ctx = page.get_context(frappe._dict())
            assert '"csrf_token"' in ctx.boot_json and "<" not in ctx.boot_json
            frappe.set_user("Guest")
            expect_error(lambda: page.get_context(frappe._dict()), frappe.Redirect)
        check("/alphax serves boot for users, redirects guests", www_page)

        frappe.db.commit()
    finally:
        frappe.destroy()
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILED:", ", ".join(FAILED))
        sys.exit(1)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "hr.test")
