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

        print("\n== Sites with extra mandatory Employee fields (CentralHRMS/IRSAA style)")
        def site_specific_mandatory():
            frappe.set_user("Administrator")
            made = []
            try:
                if not frappe.db.exists("Custom Field", "Employee-custom_saudinonsaudi"):
                    frappe.get_doc({"doctype": "Custom Field", "dt": "Employee", "fieldname": "custom_saudinonsaudi",
                                    "label": "Saudi/Non-Saudi", "fieldtype": "Select", "options": "\nSaudi\nNon-Saudi",
                                    "reqd": 1, "insert_after": "gender"}).insert(ignore_permissions=True)
                    made.append(("Custom Field", "Employee-custom_saudinonsaudi"))
                if not frappe.db.exists("Custom Field", "Employee-custom_insurance_class"):
                    frappe.get_doc({"doctype": "Custom Field", "dt": "Employee", "fieldname": "custom_insurance_class",
                                    "label": "Insurance Class", "fieldtype": "Link", "options": "Branch",
                                    "reqd": 1, "insert_after": "gender"}).insert(ignore_permissions=True)
                    made.append(("Custom Field", "Employee-custom_insurance_class"))
                for fn, label in (("custom_identity_number", "Identity Number"), ("iqama_national_id", "National ID / Iqama / Border No"),
                                  ("custom_nid_border_no", "National ID / Iqama / Border No")):  # unknown name: found by label
                    if not frappe.db.exists("Custom Field", "Employee-" + fn):
                        frappe.get_doc({"doctype": "Custom Field", "dt": "Employee", "fieldname": fn, "label": label,
                                        "fieldtype": "Data", "reqd": 1, "insert_after": "gender"}).insert(ignore_permissions=True)
                        made.append(("Custom Field", "Employee-" + fn))
                ensure("Branch", {"branch": "AXT VIP"}, {})
                from frappe.custom.doctype.property_setter.property_setter import make_property_setter
                make_property_setter("Employee", "marital_status", "reqd", 1, "Check")
                made.append(("Property Setter", "Employee-marital_status-reqd"))
                frappe.clear_cache(doctype="Employee")
                frappe.db.commit()

                frappe.set_user(f["hr"])
                form = hr.new_employee_form()
                req = {x["fieldname"]: x for x in form["required"]}
                assert {"custom_saudinonsaudi", "custom_insurance_class", "marital_status"} <= set(req), list(req)
                assert req["marital_status"]["options"][1:] == ["Single", "Married", "Divorced", "Widowed"], req["marital_status"]
                assert req["custom_insurance_class"]["options"] == "Branch"
                assert req["custom_identity_number"].get("mirrors") == "alphax_iqama_number", req["custom_identity_number"]
                assert req["custom_nid_border_no"].get("mirrors") == "alphax_iqama_number", req["custom_nid_border_no"]
                assert req["marital_status"]["step"] == "personal" and req["custom_insurance_class"]["step"] == "identity", req
                assert {c["fieldname"]: c["step"] for c in form["core"]}["department"] == "job"
                assert hr.lookup("Branch", "AXT"), "link lookup must allow site-specific Employee links"

                base = {"first_name": "Mandatory", "last_name": "Check", "gender": "Male", "date_of_birth": "1990-01-01",
                        "date_of_joining": nowdate(), "company": COMPANY, "alphax_is_saudi": 0}
                try:
                    hr.create_employee(base)
                    raise AssertionError("expected friendly missing-fields error")
                except frappe.ValidationError as exc:
                    frappe.clear_messages()
                    msg = str(exc)
                    assert "Insurance Class" in msg and "Marital Status" in msg and "Saudi/Non-Saudi" not in msg, msg
                    assert "Identity Number" in msg, "without an Iqama the mirrored field is still missing"
                unique_id = "23" + frappe.generate_hash(length=12).translate(str.maketrans("abcdef", "123456"))[:8]
                unique_id = "".join(ch if ch.isdigit() else "7" for ch in unique_id)
                created = hr.create_employee({**base, "custom_insurance_class": "AXT VIP", "marital_status": "Single",
                                              "alphax_iqama_number": unique_id})
                assert frappe.db.get_value("Employee", created["name"], "custom_identity_number") == unique_id
                assert frappe.db.get_value("Employee", created["name"], "iqama_national_id") == unique_id
                assert frappe.db.get_value("Employee", created["name"], "custom_nid_border_no") == unique_id
                made.append(("Employee", created["name"]))
                assert frappe.db.get_value("Employee", created["name"], "custom_saudinonsaudi") == "Non-Saudi"
                assert created["sections"]["company_required"]["custom_insurance_class"] == "AXT VIP"
                assert not created["missing_required"]

                # An older record missing the new mandatory fields is flagged, and can be fixed in one save.
                frappe.set_user("Administrator")
                # Deleted custom fields keep their DB column: clear leftovers from earlier runs.
                frappe.db.set_value("Employee", f["e_emp2"], {"custom_insurance_class": None, "marital_status": None,
                                                              "custom_identity_number": None, "iqama_national_id": None,
                                                              "custom_nid_border_no": None},
                                    update_modified=False)
                old = frappe.get_doc("Employee", f["e_emp2"])
                frappe.set_user(f["hr"])
                d = hr.employee(old.name)
                assert "Insurance Class" in d["missing_required"], d["missing_required"]
                # The duplicate ID fields are hidden in AlphaX and filled from the employee's own Iqama number.
                assert "custom_nid_border_no" not in d["sections"].get("company_required", {}), d["sections"]["company_required"]
                fixed = hr.update_employee(old.name, {"custom_insurance_class": "AXT VIP", "marital_status": "Married"}, d["modified"])
                iqama = frappe.db.get_value("Employee", old.name, "alphax_iqama_number")
                assert iqama and frappe.db.get_value("Employee", old.name, "custom_nid_border_no") == iqama
                assert "Insurance Class" not in fixed["missing_required"]
            finally:
                frappe.set_user("Administrator")
                for dt, name in reversed(made):
                    if dt == "Employee":
                        frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
                    elif frappe.db.exists(dt, name):
                        frappe.delete_doc(dt, name, ignore_permissions=True)
                frappe.clear_cache(doctype="Employee")
                frappe.db.commit()
        check("form, validation and save follow the site's own mandatory fields", site_specific_mandatory)

        print("\n== Phase 1: Saudi leave engine and employee rules")
        from alphax_hr.api import leave_setup
        from alphax_hr import leave_engine
        frappe.db.set_value("Employee", f["e_emp2"], "gender", "Male")  # Omar
        for key, value in (("validate_iban", 1), ("probation_days", 90), ("min_employee_age", 18)):
            frappe.db.set_single_value("AlphaX HR Settings", key, value)
        frappe.db.set_value("Employee", f["e_emp2"], {"alphax_probation_end_date": None, "iban": None})
        frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
        frappe.db.commit()

        def statutory_setup():
            frappe.set_user(f["emp"])
            expect_error(leave_setup.create_statutory_leave_types, frappe.PermissionError)
            frappe.set_user(f["hr"])
            res = leave_setup.create_statutory_leave_types()
            kinds = {r["rule"] for r in res["rules"]}
            assert {"Maternity", "Paternity", "Sick", "Hajj", "Bereavement (Sibling)"} <= kinds, kinds
            assert not res["missing_kinds"], res["missing_kinds"]
            frappe.set_user(f["emp2"])
            types = {t["leave_type"]: t["rule"] for t in ess.leave_types()}
            assert types.get("Paternity Leave", {}).get("kind") == "Paternity", types
            assert "Maternity Leave" not in types, "maternity hidden for male employees"
        check("statutory leave types created and offered by gender", statutory_setup)

        def leave_dates(offset, days=1):
            start = getdate(add_days(nowdate(), offset))
            return str(start), str(add_days(start, days - 1))

        def statutory_rules():
            frappe.set_user(f["emp2"])
            frm, to = leave_dates(20, 3)
            birth = str(add_days(frm, -1))
            ok = ess.apply_leave("Paternity Leave", frm, to, event_date=birth)
            assert ok["total_leave_days"] == 3, ok
            frappe.set_user("Administrator"); frappe.delete_doc("Leave Application", ok["name"], force=True); frappe.set_user(f["emp2"])
            try:
                ess.apply_leave("Paternity Leave", *leave_dates(40, 2), event_date=str(add_days(nowdate(), 20)))
                raise AssertionError("expected window error")
            except frappe.ValidationError as exc:
                frappe.clear_messages(); assert "within 7 day" in str(exc), str(exc)
            try:
                ess.apply_leave("Bereavement Leave (Sibling)", *leave_dates(22, 1), event_date=nowdate(), relation="Mother")
                raise AssertionError("expected relation error")
            except frappe.ValidationError as exc:
                frappe.clear_messages(); assert "Brother, Sister" in str(exc), str(exc)
            sib = ess.apply_leave("Bereavement Leave (Sibling)", *leave_dates(23, 1), event_date=nowdate(), relation="Brother")
            assert sib["name"]
            try:
                ess.apply_leave("Hajj Leave", *leave_dates(24, 2))
                raise AssertionError("expected service error")
            except frappe.ValidationError as exc:
                frappe.clear_messages(); assert "730 days of service" in str(exc), str(exc)
        check("paternity window, sibling relation, Hajj service enforced", statutory_rules)

        def sick_tiers_and_attachment():
            frappe.set_user(f["hr"])
            ov = leave_setup.overview()
            sick = next(r for r in ov["rules"] if r["rule"] == "Sick")
            if sick["needs_allocation"]:  # HRMS ships its own Sick Leave type that expects allocations
                leave_setup.allow_without_allocation(sick["leave_type"])
            frappe.set_user(f["emp"])  # Eman
            first = ess.apply_leave("Sick Leave", *leave_dates(60, 25))
            second = ess.apply_leave("Sick Leave", *leave_dates(86, 10))
            text = frappe.db.get_value("Leave Application", second["name"], "alphax_sick_breakdown")
            assert text.startswith("5 day(s) full pay · 5 day(s) 75% pay"), text
            frappe.set_user(f["mgr"])
            frappe.db.savepoint("before_approve")  # an HTTP request rolls back on error; mimic that
            try:
                approvals.act("Leave Application", first["name"], "Approve")
                raise AssertionError("expected attachment error")
            except frappe.ValidationError as exc:
                frappe.clear_messages(); frappe.db.rollback(save_point="before_approve")
                assert "supporting document" in str(exc), str(exc)
            frappe.set_user(f["emp"])
            frappe.get_doc({"doctype": "File", "file_name": "medical-certificate.txt", "content": "certificate",
                            "attached_to_doctype": "Leave Application", "attached_to_name": first["name"], "is_private": 1}).insert()
            frappe.set_user(f["mgr"])
            assert approvals.act("Leave Application", first["name"], "Approve")["docstatus"] == 1
        check("sick leave tiers across requests; certificate required to approve", sick_tiers_and_attachment)

        def annual_allocation():
            frappe.set_user("Administrator")
            lt = ensure("Leave Type", {"leave_type_name": "AXT Saudi Annual"},
                        {"is_carry_forward": 1, "maximum_carry_forwarded_leaves": 21, "expire_carry_forwarded_leaves_after_days": 90}).name
            frappe.db.set_single_value("AlphaX HR Settings", "annual_leave_type", lt)
            frappe.db.set_single_value("AlphaX HR Settings", "annual_policy", "Saudi Labor Law")
            for e in (f["e_emp"], f["e_emp2"]):
                frappe.db.set_value("Employee", e, "alphax_annual_leave_days", 0)
            frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
            frappe.db.commit()
            frappe.set_user(f["emp"])
            expect_error(lambda: leave_setup.annual_allocation(apply=1), frappe.PermissionError)
            frappe.set_user(f["hr"])
            plan = leave_setup.annual_allocation()
            eman = next(r for r in plan["rows"] if r["employee"] == f["e_emp"])
            assert eman["days"] == 30 and eman["from_date"].endswith("-01-10") and eman["service_year"] == 6, eman
            res = leave_setup.annual_allocation(apply=1)
            assert not res["failed"], res["failed"]
            again = leave_setup.annual_allocation()
            assert next(r for r in again["rows"] if r["employee"] == f["e_emp"])["action"] == "exists"
            omar = next(r for r in again["rows"] if r["employee"] == f["e_emp2"])
            assert omar["days"] == 21 and omar["from_date"].endswith("-03-01"), omar
        check("annual allocation per service year: 30 days after 5 years, idempotent", annual_allocation)

        def annual_policy_and_contract():
            frappe.set_user("Administrator")
            expect_error(lambda: leave_setup.update_annual_settings({"annual_policy": "Fixed for all employees", "annual_fixed_days": 20}),
                         frappe.ValidationError)
            leave_setup.update_annual_settings({"annual_policy": "Fixed for all employees", "annual_fixed_days": 30})
            frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
            try:
                omar = next(r for r in leave_engine.plan_annual_allocations()["rows"] if r["employee"] == f["e_emp2"])
                assert omar["days"] == 30 and omar["source"] == "company", omar  # IRSAA case: 30 for everyone
                frappe.db.set_value("Employee", f["e_emp2"], "alphax_annual_leave_days", 25)
                frappe.db.set_value("Employee", f["e_emp"], "alphax_annual_leave_days", 25)
                rows = {r["employee"]: r for r in leave_engine.plan_annual_allocations()["rows"]}
                assert rows[f["e_emp2"]]["days"] == 25 and rows[f["e_emp2"]]["source"] == "contract", rows[f["e_emp2"]]
                # 6th service year: the law's 30 days beat a 25-day contract
                assert rows[f["e_emp"]]["days"] == 30 and rows[f["e_emp"]]["source"] == "legal_minimum", rows[f["e_emp"]]
                doc = frappe.get_doc("Employee", f["e_emp2"])
                doc.alphax_annual_leave_days = 15
                expect_error(doc.save, frappe.ValidationError)
            finally:
                frappe.db.set_value("Employee", f["e_emp2"], "alphax_annual_leave_days", 0)
                frappe.db.set_value("Employee", f["e_emp"], "alphax_annual_leave_days", 0)
                frappe.db.set_single_value("AlphaX HR Settings", "annual_policy", "Saudi Labor Law")
                frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
                frappe.db.commit()
        check("annual policy: fixed 30 for all, contract override, legal minimum", annual_policy_and_contract)

        def fixed_leave_type_names():
            frappe.set_user("Administrator")
            lt = frappe.db.get_single_value("AlphaX HR Settings", "annual_leave_type")
            expect_error(lambda: frappe.rename_doc("Leave Type", lt, lt + " X"), frappe.ValidationError)
            expect_error(lambda: frappe.delete_doc("Leave Type", lt), frappe.ValidationError, frappe.LinkExistsError)
            expect_error(leave_setup.setup_annual_leave_type, frappe.ValidationError)
            assert frappe.db.exists("Leave Type", lt)
        check("statutory and annual leave type names are fixed", fixed_leave_type_names)

        def people_export_and_org_chart():
            frappe.set_user(f["hr"])
            listing = hr.employees(search="Omar")
            row = next(r for r in listing["rows"] if r["name"] == f["e_emp2"])
            assert "missing" in row and isinstance(listing["departments"], list), row
            hr.export_employees(search="Test", file_format="xlsx")
            assert frappe.response["type"] == "binary" and frappe.response["filename"].endswith(".xlsx")
            assert frappe.response["filecontent"][:2] == b"PK"  # a real xlsx (zip)
            hr.export_employees(search="Test", file_format="csv")
            text = frappe.response["filecontent"].decode("utf-8-sig")
            assert "Employee ID" in text.splitlines()[0] and "Omar Test" in text, text[:200]
            frappe.response.pop("filecontent", None); frappe.response.pop("type", None)
            frappe.db.set_value("Employee", f["e_emp"], "reports_to", f["e_mgr"])
            chart = {r["name"]: r for r in hr.org_chart()["rows"]}
            assert chart[f["e_emp"]]["reports_to"] == f["e_mgr"], chart[f["e_emp"]]
            frappe.set_user(f["emp"])
            expect_error(lambda: hr.export_employees(), frappe.PermissionError)
        check("people: missing-field counts, Excel/CSV export, org chart; employees blocked", people_export_and_org_chart)

        def escalation():
            frappe.set_user(f["emp2"])
            name = ess.apply_leave("AXT Annual", *leave_dates(28, 1))["name"]
            frappe.set_user("Administrator")
            frappe.db.set_single_value("AlphaX HR Settings", "leave_escalation_hours", 24)
            frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
            frappe.db.set_value("Leave Application", name, "creation", add_days(nowdate(), -3), update_modified=False)
            leave_engine.escalate_pending_leaves()
            assert frappe.db.get_value("Leave Application", name, "alphax_escalated_on")
            assert frappe.db.exists("Notification Log", {"for_user": f["mgr"], "document_name": name})
            leave_engine.escalate_pending_leaves()  # second run must not notify again
            assert frappe.db.count("Notification Log", {"for_user": f["mgr"], "document_name": name}) == 1
        check("untouched requests escalate once to approver and HR", escalation)

        def employee_rules():
            frappe.set_user(f["hr"])
            d = hr.employee(f["e_emp2"])
            upd = hr.update_employee(f["e_emp2"], {"alphax_iqama_number": "1012345678"}, d["modified"])
            assert upd["sections"]["saudi"]["alphax_is_saudi"] == 1, "ID starting with 1 makes the employee Saudi"
            for bad, words in (("9012345678", "start with 1"), ("12345", "10 digits")):
                d = hr.employee(f["e_emp2"])
                try:
                    hr.update_employee(f["e_emp2"], {"alphax_iqama_number": bad}, d["modified"])
                    raise AssertionError("expected ID error")
                except frappe.ValidationError as exc:
                    frappe.clear_messages(); assert words in str(exc), str(exc)
            other = frappe.db.get_value("Employee", f["e_emp"], "alphax_iqama_number")
            d = hr.employee(f["e_emp2"])
            try:
                hr.update_employee(f["e_emp2"], {"alphax_iqama_number": other}, d["modified"])
                raise AssertionError("expected duplicate error")
            except frappe.ValidationError as exc:
                frappe.clear_messages(); assert "already belongs" in str(exc), str(exc)
            d = hr.employee(f["e_emp2"])
            hr.update_employee(f["e_emp2"], {"alphax_iqama_number": "2311112222"}, d["modified"])  # restore
            frappe.set_user("Administrator")
            emp = frappe.get_doc("Employee", f["e_emp2"])
            emp.iban = "SA0380000000608010167518"
            try:
                emp.save(); raise AssertionError("expected IBAN error")
            except frappe.ValidationError as exc:
                frappe.clear_messages(); assert "IBAN" in str(exc)
            emp.reload(); emp.iban = "sa03 8000 0000 6080 1016 7519"; emp.save()
            assert emp.iban == "SA0380000000608010167519"
            assert str(emp.alphax_probation_end_date) == str(add_days(emp.date_of_joining, 89)), emp.alphax_probation_end_date
        check("ID number rules, Saudi flag from ID, duplicates, IBAN, probation date", employee_rules)

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
