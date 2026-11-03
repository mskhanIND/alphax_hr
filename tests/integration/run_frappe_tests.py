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
from frappe.utils import add_days, get_first_day, get_last_day, getdate, nowdate

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
        traceback.print_exc(limit=-8)
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
                              "alphax_iqama_expiry": None if saudi else add_days(nowdate(), 20),
                              "passport_number": None if saudi else "P" + str(abs(hash(user)))[:7]})
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
    if frappe.db.exists("DocType", "AlphaX Attendance Policy"):
        frappe.db.delete("AlphaX Attendance Policy")  # policies change how the register counts lateness
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
            assert b["persona"] == {"employee": True, "approver": False, "hr": False, "hr_manager": False, "system_manager": False}, b["persona"]
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
                assert "gosi_registration_date_missing" not in r["issues"], r["issues"]
                assert str(r["sections"]["saudi"]["alphax_gosi_registration_date"]) == nowdate()  # defaults to joining date
        check("create_employee validates; Saudi GOSI date defaults to the joining date", hr_create)

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
                assert {"custom_saudinonsaudi", "custom_insurance_class"} <= set(req), list(req)
                core = {c["fieldname"]: c for c in form["core"]}
                assert core["marital_status"]["options"][1:] == ["Single", "Married", "Divorced", "Widowed"], core["marital_status"]
                assert req["custom_insurance_class"]["options"] == "Branch"
                assert req["custom_identity_number"].get("mirrors") == "alphax_iqama_number", req["custom_identity_number"]
                assert req["custom_nid_border_no"].get("mirrors") == "alphax_iqama_number", req["custom_nid_border_no"]
                assert core["marital_status"]["step"] == "personal" and req["custom_insurance_class"]["step"] == "personal", req
                steps = {c["fieldname"]: c["step"] for c in form["core"]}
                assert steps["department"] == "organization" and steps["alphax_contract_years"] == "contract", steps
                assert steps["alphax_iqama_number"] == "employee" and steps["iban"] == "bank", steps
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
                                              "alphax_iqama_number": unique_id, "passport_number": "P1234567"})
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
            try:  # 35 days used; 90 more would pass the 120-day sick-leave year (Art. 117)
                ess.apply_leave("Sick Leave", *leave_dates(100, 90))
                raise AssertionError("expected the 120-day limit")
            except frappe.ValidationError as exc:
                frappe.clear_messages(); assert "unpaid leave" in str(exc), str(exc)
            from alphax_hr.api import leave_ledger
            st = leave_ledger.summary()["sick"]
            assert st is not None and "tiers" in st
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

        def ledger_and_balances():
            from alphax_hr.api import leave_ledger
            frappe.set_user(f["emp"])
            mine = leave_ledger.summary()
            assert any(b["leave_type"] == "AXT Annual" for b in mine["balances"]), mine["balances"]
            alloc = [e for e in mine["ledger"] if e["leave_type"] == "AXT Annual" and e["transaction_type"] == "Leave Allocation"]
            assert alloc and "balance" in alloc[0], mine["ledger"][:3]
            expect_error(lambda: leave_ledger.summary(f["e_emp2"]), frappe.PermissionError)
            frappe.set_user(f["mgr"])
            assert leave_ledger.summary(f["e_emp"])["employee"] == f["e_emp"]  # the leave approver may look
            frappe.set_user(f["hr"])
            wf = leave_ledger.workforce()
            assert "AXT Annual" in wf["leave_types"] and any(r["employee"] == f["e_emp"] for r in wf["rows"])
            leave_ledger.export_workforce(file_format="xlsx")
            assert frappe.response["filecontent"][:2] == b"PK"
            frappe.response.pop("filecontent", None); frappe.response.pop("type", None)
        check("leave ledger with running balance; workforce balances + export; privacy", ledger_and_balances)

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
            leave_setup.update_annual_settings({"annual_senior_days": "", "annual_senior_after_years": None})  # blank = law, accepted
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
            hr.update_employee(f["e_emp2"], {"alphax_iqama_number": "2311112222", "passport_number": "P7654321"}, d["modified"])  # restore
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

        def hcs_style_site():
            """Regressions seen on hcs: a 'nationality' field and a mandatory checkbox."""
            from frappe.custom.doctype.property_setter.property_setter import make_property_setter
            frappe.set_user("Administrator")
            made_field = False
            if not frappe.get_meta("Employee").has_field("nationality"):
                frappe.get_doc({"doctype": "Custom Field", "dt": "Employee", "fieldname": "nationality", "label": "Nationality",
                                "fieldtype": "Data", "insert_after": "gender"}).insert(ignore_permissions=True)
                made_field = True
            make_property_setter("Employee", "alphax_is_saudi", "reqd", 1, "Check")
            frappe.clear_cache(doctype="Employee"); frappe.db.commit()
            try:
                frappe.set_user(f["hr"])
                ov = compliance.overview()
                assert any(c["key"] == "saudi_flag_mismatch" for c in ov["checks"]), ov["checks"]
                form = hr.new_employee_form()
                assert "alphax_is_saudi" not in {x["fieldname"] for x in form["required"]}
                assert "Saudi National" not in hr.employee(f["e_emp2"])["missing_required"]
            finally:
                frappe.set_user("Administrator")
                frappe.db.delete("Property Setter", {"doc_type": "Employee", "field_name": "alphax_is_saudi", "property": "reqd"})
                if made_field:
                    frappe.delete_doc("Custom Field", "Employee-nationality", ignore_permissions=True)
                frappe.clear_cache(doctype="Employee"); frappe.db.commit()
        check("hcs-style site: nationality check works; a mandatory checkbox is never 'missing'", hcs_style_site)

        def employee_v2_rules():
            import random
            from frappe.utils import add_months
            frappe.set_user(f["hr"])
            uid = lambda p: p + "".join(random.choice("0123456789") for _ in range(9))
            base = {"first_name": "Rules", "last_name": "Check", "gender": "Male", "date_of_birth": "1990-05-05",
                    "date_of_joining": "2026-01-01", "company": COMPANY, "alphax_contract_years": "2"}
            saudi = hr.create_employee({**base, "alphax_iqama_number": uid("1"), "alphax_employee_name_ar": "فحص القواعد"})
            row = frappe.db.get_value("Employee", saudi["name"], ["contract_end_date", "alphax_gosi_registration_date",
                                                                  "alphax_is_saudi", "alphax_employee_name_ar"], as_dict=True)
            assert str(row.contract_end_date) == "2027-12-31", row          # 2 years from 01-01-2026
            assert str(row.alphax_gosi_registration_date) == "2026-01-01" and row.alphax_is_saudi == 1, row
            assert row.alphax_employee_name_ar == "فحص القواعد"
            assert "passport_missing" not in saudi["issues"]                 # Saudis need no passport
            expect_error(lambda: hr.create_employee({**base, "first_name": "NoPassport", "alphax_iqama_number": uid("2")}),
                         frappe.ValidationError)
            foreign = hr.create_employee({**base, "first_name": "Expat", "alphax_iqama_number": uid("2"),
                                          "passport_number": "P" + uid("1")[:8], "alphax_contract_years": "Indefinite"})
            assert not frappe.db.get_value("Employee", foreign["name"], "contract_end_date")
            # photo: only a file attached to this employee is accepted
            frappe.set_user("Administrator")
            pic = frappe.get_doc({"doctype": "File", "file_name": "face.png", "content": b"\x89PNG fake", "is_private": 0,
                                  "attached_to_doctype": "Employee", "attached_to_name": saudi["name"]}).insert()
            frappe.set_user(f["hr"])
            assert hr.set_photo(saudi["name"], pic.file_url)["image"] == pic.file_url
            expect_error(lambda: hr.set_photo(foreign["name"], pic.file_url), frappe.ValidationError)
            hr.export_org_chart(file_format="csv")
            head = frappe.response["filecontent"].decode("utf-8-sig").splitlines()[0]
            assert "Reports to" in head and "Team size" in head, head
            frappe.response.pop("filecontent", None); frappe.response.pop("type", None)
            frappe.set_user("Administrator")
            for n in (saudi["name"], foreign["name"]):
                frappe.delete_doc("Employee", n, force=True, ignore_permissions=True)
            frappe.db.commit()
        check("contract period sets end date; Saudi defaults; passport only for non-Saudis; photo; org chart export", employee_v2_rules)

        def hcs_wizard():
            import random
            from frappe.custom.doctype.property_setter.property_setter import make_property_setter
            frappe.set_user("Administrator")
            fields = (("custom_contract_start_date", "Contract Start Date", "Date", None),
                      ("custom_contract_end_date", "Contract End Date", "Date", None),
                      ("custom_passport_attach", "Passport", "Attach", None),
                      ("custom_employee_nationality", "Employee Nationality", "Link", "Country"),
                      ("custom_identity_expiry_date", "Identity Expiry Date", "Date", None),
                      ("custom_identity_type", "Identity Type", "Select", "\nIdentity(Have ID/Iqama No)\nBorder Number"),
                      ("custom_odd_id", "Muqeem Ref", "Data", None))
            made = []
            for fn, label, ft, opt in fields:
                if not frappe.db.exists("Custom Field", "Employee-" + fn):
                    frappe.get_doc({"doctype": "Custom Field", "dt": "Employee", "fieldname": fn, "label": label, "fieldtype": ft,
                                    "options": opt, "reqd": 1, "insert_after": "gender"}).insert(ignore_permissions=True)
                made.append("Employee-" + fn)
            make_property_setter("Employee", "holiday_list", "reqd", 1, "Check")
            frappe.clear_cache(doctype="Employee"); frappe.db.commit()
            emp = None
            try:
                frappe.set_user(f["hr"])
                form = hr.new_employee_form()
                req = {x["fieldname"]: x for x in form["required"]}
                assert req["custom_contract_start_date"]["auto"] == "contract_start"
                assert req["custom_contract_end_date"]["auto"] == "contract_end"
                assert req["custom_employee_nationality"]["auto"] == "nationality"
                assert req["custom_employee_nationality"]["saudi_value"] == "Saudi Arabia", req["custom_employee_nationality"]
                assert req["custom_passport_attach"]["fieldtype"] == "Attach"
                assert req["custom_identity_type"].get("mirrors") == "alphax_iqama_number", req["custom_identity_type"]
                fm = hr.field_map()
                assert {m["fieldname"]: m["from"] for m in fm["mirrors"]}["custom_identity_expiry_date"] == "alphax_iqama_expiry"
                hr.link_field("custom_odd_id", "alphax_iqama_number")   # a site field AlphaX could not guess
                assert hr.new_employee_form()["required"] and {x["fieldname"]: x for x in hr.new_employee_form()["required"]}["custom_odd_id"].get("mirrors") == "alphax_iqama_number"
                payload = {"first_name": "Wizard", "last_name": "Check", "gender": "Male", "date_of_birth": "1990-01-01",
                           "date_of_joining": "2026-03-15", "company": COMPANY, "alphax_contract_years": "2",
                           "alphax_iqama_number": "1" + "".join(random.choice("0123456789") for _ in range(9)),
                           "custom_contract_start_date": "2026-03-15", "custom_contract_end_date": "2028-03-14",
                           "custom_employee_nationality": "Saudi Arabia"}
                payload["alphax_iqama_expiry"] = "2027-01-01"
                missing = {m["fieldname"] for m in hr.check_new_employee(payload)["missing"]}
                assert missing == {"custom_passport_attach"}, missing   # ID type, expiry, odd ID: filled; holiday list from company
                expect_error(lambda: hr.create_employee(payload), frappe.ValidationError)
                f_ = frappe.get_doc({"doctype": "File", "file_name": "passport.txt", "content": b"passport scan", "is_private": 1}).insert()
                created = hr.create_employee({**payload, "custom_passport_attach": f_.file_url,
                                              "custom_contract_end_date": "2030-01-01"})  # server recomputes from the period
                emp = created["name"]
                row = frappe.db.get_value("Employee", emp, ["custom_contract_start_date", "custom_contract_end_date",
                                                           "contract_end_date", "holiday_list"], as_dict=True)
                assert str(row.custom_contract_start_date) == "2026-03-15" and str(row.custom_contract_end_date) == "2028-03-14", row
                assert str(row.contract_end_date) == "2028-03-14" and row.holiday_list, row
                assert frappe.db.get_value("File", f_.name, "attached_to_name") == emp
                assert frappe.db.get_value("Employee", emp, "custom_identity_type") == "Identity(Have ID/Iqama No)"
                assert frappe.db.get_value("Employee", emp, "custom_odd_id") == payload["alphax_iqama_number"]
            finally:
                frappe.set_user("Administrator")
                if emp:
                    frappe.delete_doc("Employee", emp, force=True, ignore_permissions=True)
                for n in made:
                    frappe.delete_doc("Custom Field", n, ignore_permissions=True)
                frappe.db.delete("Property Setter", {"doc_type": "Employee", "field_name": "holiday_list", "property": "reqd"})
                conf = frappe.get_single("AlphaX HR Settings"); conf.set("field_links", []); conf.save()
                frappe.clear_cache(doctype="Employee"); frappe.db.commit()
        check("hcs-style wizard: contract dates from period, Saudi nationality, Passport attachment, company holiday list", hcs_wizard)

        def salary_package():
            import random
            from alphax_hr.api import salary
            frappe.set_user("Administrator")
            for comp, abbr, kind in (("Basic", "B", "Earning"), ("Housing Allowance", "HA", "Earning"),
                                     ("Transport Allowance", "TA", "Earning"), ("GOSI Employee", "GOSI", "Deduction")):
                if not frappe.db.exists("Salary Component", comp):
                    frappe.get_doc({"doctype": "Salary Component", "salary_component": comp, "salary_component_abbr": abbr,
                                    "type": kind}).insert(ignore_permissions=True)
            salary.seed_components()
            frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
            frappe.set_user(f["hr"])
            c = salary.config()
            assert c["ready"] and c["basic"] == "Basic" and c["gosi"] == "GOSI Employee", c
            p = salary.preview({"mode": "total", "total": 13500}, is_saudi=1, gosi_registration_date="2025-01-01", start_date="2026-01-01")
            amounts = {r["salary_component"]: r["amount"] for r in p["earnings"]}
            assert amounts == {"Basic": 10000, "Housing Allowance": 2500, "Transport Allowance": 1000}, amounts
            assert p["deductions"] and p["gosi"]["system"] == "New" and p["net"] < p["gross"], p
            assert not salary.preview({"mode": "components", "basic": 8000}, is_saudi=0)["deductions"]  # non-Saudi: no GOSI
            created = hr.create_employee({"first_name": "Salary", "last_name": "Check", "gender": "Female", "date_of_birth": "1991-01-01",
                                          "date_of_joining": "2026-02-01", "company": COMPANY, "alphax_contract_years": "1",
                                          "alphax_iqama_number": "1" + "".join(random.choice("0123456789") for _ in range(9)),
                                          "salary": {"mode": "total", "total": 13500}})
            cur = salary.current(created["name"])["current"]
            assert cur and cur["from_date"] == "2026-02-01" and cur["gross"] == 13500 and cur["total_deductions"] > 0, cur
            salary.set_salary(created["name"], {"mode": "components", "basic": 12000, "housing": 3000, "transport": 1200}, "2026-08-01")
            hist = salary.current(created["name"])
            assert hist["current"]["gross"] == 16200 and len(hist["history"]) == 2, hist
            frappe.set_user(f["emp"])
            expect_error(lambda: salary.preview({"mode": "total", "total": 1000}), frappe.PermissionError)
            frappe.set_user("Administrator")
            for a in frappe.get_all("Salary Structure Assignment", filters={"employee": created["name"], "docstatus": 1}, pluck="name"):
                frappe.get_doc("Salary Structure Assignment", a).cancel()
            frappe.delete_doc("Employee", created["name"], force=True, ignore_permissions=True)
            frappe.db.commit()
        check("salary package: split by %, GOSI for Saudis, own structure + assignment on create, change later", salary_package)

        def hidden_mandatory_fields():
            from frappe.custom.doctype.property_setter.property_setter import make_property_setter
            frappe.set_user("Administrator")
            try:
                if not frappe.db.exists("Custom Field", "Employee-custom_hidden_code"):
                    frappe.get_doc({"doctype": "Custom Field", "dt": "Employee", "fieldname": "custom_hidden_code", "label": "Hidden Code",
                                    "fieldtype": "Data", "reqd": 1, "insert_after": "gender"}).insert(ignore_permissions=True)
                # how such fields usually end up hidden on customer sites (Customize Form)
                make_property_setter("Employee", "custom_hidden_code", "hidden", 1, "Check", validate_fields_for_doctype=False)
                frappe.clear_cache(doctype="Employee"); frappe.db.commit()
                frappe.set_user(f["hr"])
                assert "custom_hidden_code" in {x["fieldname"] for x in hr.new_employee_form()["required"]}
                fm = hr.field_map()
                assert any(r["fieldname"] == "custom_hidden_code" and r["hidden"] for r in fm["required"])
                d = hr.employee(f["e_emp2"])
                assert "custom_hidden_code" in d["sections"]["company_required"], "fillable on the profile, so saving is possible"
                frappe.db.set_value("Employee", f["e_emp2"], "custom_hidden_code", None)
                d = hr.employee(f["e_emp2"])
                hr.update_employee(f["e_emp2"], {"custom_hidden_code": "X1"}, d["modified"])
            finally:
                frappe.set_user("Administrator")
                frappe.db.delete("Property Setter", {"doc_type": "Employee", "field_name": "custom_hidden_code"})
                if frappe.db.exists("Custom Field", "Employee-custom_hidden_code"):
                    frappe.delete_doc("Custom Field", "Employee-custom_hidden_code", ignore_permissions=True)
                frappe.clear_cache(doctype="Employee"); frappe.db.commit()
        check("hidden/read-only mandatory fields are asked for, so saving works", hidden_mandatory_fields)

        print("\n== Phase 2: shifts and attendance")
        from alphax_hr.api import attendance as att_api, shifts as shift_api

        def past_workday(min_back=3):
            d = getdate(add_days(nowdate(), -min_back))
            while d.weekday() == 4:  # Friday is the weekly off in the fixture
                d = getdate(add_days(d, -1))
            return d

        def shifts_and_roster():
            frappe.set_user("Administrator")
            st = ensure("Shift Type", {"name": "AXT Day"}, {"start_time": "08:00:00", "end_time": "17:00:00",
                                                            "late_entry_grace_period": 15, "early_exit_grace_period": 10})
            if not st.start_time:
                st = frappe.get_doc({"doctype": "Shift Type", "__newname": "AXT Day", "start_time": "08:00:00", "end_time": "17:00:00",
                                     "late_entry_grace_period": 15, "early_exit_grace_period": 10}).insert(ignore_permissions=True)
            # start clean: earlier runs leave assignments for this employee
            for name in frappe.get_all("Shift Assignment", filters={"employee": f["e_emp2"], "docstatus": 1}, pluck="name"):
                frappe.get_doc("Shift Assignment", name).cancel()
            frappe.db.commit()
            day = past_workday()
            start = getdate(get_first_day(day))
            frappe.set_user(f["emp"])
            expect_error(lambda: shift_api.roster(str(start)), frappe.PermissionError)
            frappe.set_user(f["hr"])
            month_end = str(get_last_day(day))
            res = shift_api.assign([f["e_emp2"], "HR-EMP-NOPE"], "AXT Day", str(start), month_end)
            assert len(res["created"]) == 1 and res["failed"][0]["employee"] == "HR-EMP-NOPE", res
            again = shift_api.assign([f["e_emp2"]], "AXT Day", str(start), month_end)
            assert not again["created"] and again["failed"], "overlapping assignment must be refused"
            grid = shift_api.roster(str(day), days=7)
            row = next(r for r in grid["rows"] if r["employee"] == f["e_emp2"])
            assert row["cells"][0]["shift"] == "AXT Day" and row["cells"][0]["assignment"] == res["created"][0], row["cells"][0]
            assert any(c["holiday"] for c in row["cells"]), "the weekly off (Friday) shows in a 7-day roster"
            return day
        check("shift assignment (overlaps refused per employee) and roster grid", shifts_and_roster)

        def roster_week_offs():
            from alphax_hr import week_off
            frappe.set_user("Administrator")
            emp = frappe.db.get_value("Employee", {"first_name": "Weekoff", "last_name": "Tester"}, "name")
            if not emp:
                emp = frappe.get_doc({"doctype": "Employee", "first_name": "Weekoff", "last_name": "Tester", "gender": "Female",
                                      "date_of_birth": "1992-02-02", "date_of_joining": "2024-01-01", "company": COMPANY,
                                      "status": "Active"}).insert(ignore_permissions=True).name
            base = frappe.db.get_value("Company", COMPANY, "default_holiday_list")
            frappe.db.set_value("Employee", emp, "holiday_list", base)  # start from the company list each run
            frappe.db.commit()
            start = getdate(add_days(nowdate(), 7))
            end = getdate(add_days(start, 27))
            frappe.set_user(f["hr"])
            res = shift_api.set_week_off([emp], [5], str(start), str(end))  # Saturdays
            assert not res["failed"] and res["done"][0]["added"] == 4, res
            personal = frappe.db.get_value("Employee", emp, "holiday_list")
            assert personal != base and frappe.db.get_value("Holiday List", personal, "alphax_base_list") == base
            hol = {str(h.holiday_date): h for h in frappe.get_all("Holiday", filters={"parent": personal}, fields=["holiday_date", "weekly_off"])}
            sat = next(d for d in week_off.dates_for([5], start, end))
            fri = next(d for d in week_off.dates_for([4], start, end))
            assert str(sat) in hol and str(fri) not in hol, "the chosen days replace the usual week-offs in the period"
            shift_api.set_week_off([emp], [4], str(start), str(end), replace=0)  # add Fridays back, keep Saturdays
            hol = {str(h.holiday_date) for h in frappe.get_all("Holiday", filters={"parent": personal}, fields=["holiday_date"])}
            assert str(sat) in hol and str(fri) in hol
            grid = shift_api.roster(str(start), days=7)
            row = next(r for r in grid["rows"] if r["employee"] == emp)
            assert any(c["holiday"] == "weekly_off" and c["date"] == str(sat) for c in row["cells"]), row["cells"]
            mon = next(d for d in week_off.dates_for([0], start, end))
            assert shift_api.toggle_week_off(emp, str(mon))["off"] is True
            assert shift_api.toggle_week_off(emp, str(mon))["off"] is False
            # replacing: Sundays instead of Saturdays
            shift_api.set_week_off([emp], [6], str(start), str(end))
            days = {getdate(d) for d in frappe.get_all("Holiday", filters={"parent": personal, "weekly_off": 1,
                                                                            "holiday_date": ["between", [start, end]]}, pluck="holiday_date")}
            assert sat not in days and any(d.weekday() == 6 for d in days), days
            # a public holiday added to the company list reaches the personal list
            frappe.set_user("Administrator")
            bl = frappe.get_doc("Holiday List", base)
            ph = next(d for d in week_off.dates_for([2], start, end))
            bl.append("holidays", {"holiday_date": ph, "description": "AXT Test Holiday", "weekly_off": 0}); bl.save()
            assert frappe.db.exists("Holiday", {"parent": personal, "holiday_date": ph, "weekly_off": 0})
            bl.reload(); bl.holidays = [h for h in bl.holidays if h.description != "AXT Test Holiday"]; bl.save()
            assert not frappe.db.exists("Holiday", {"parent": personal, "holiday_date": ph, "weekly_off": 0})
            # an outdated company list: the personal list grows to cover the request instead of skipping days
            frappe.set_user(f["hr"])
            far = getdate(add_days(frappe.db.get_value("Holiday List", base, "to_date"), 30))
            res = shift_api.set_week_off([emp], [5], str(far), str(add_days(far, 13)))
            assert res["done"][0]["added"] == 2 and res["done"][0]["beyond_company_list"], res
            assert getdate(frappe.db.get_value("Holiday List", personal, "to_date")) >= getdate(add_days(far, 13))
            frappe.db.commit()
        check("roster week-offs per employee via a personal holiday list (synced public holidays)", roster_week_offs)

        def register_late_and_overtime():
            frappe.set_user("Administrator")
            day = past_workday()
            frappe.db.delete("Employee Checkin", {"employee": f["e_emp2"], "time": ["between", [f"{day} 00:00:00", f"{day} 23:59:59"]]})
            for t, kind in (("08:40:00", "IN"), ("19:00:00", "OUT")):
                frappe.get_doc({"doctype": "Employee Checkin", "employee": f["e_emp2"], "time": f"{day} {t}", "log_type": kind}).insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.set_user(f["hr"])
            data = att_api.register(str(day))
            row = next(r for r in data["rows"] if r["employee"] == f["e_emp2"])
            cell = next(c for c in row["cells"] if c["date"] == str(day))
            assert cell["code"] in ("P", "L"), cell
            if cell["code"] == "P":
                assert cell["late"] == 40 and cell["overtime"] == 1.33, cell  # 40 min late; 10h20m worked vs 9h shift
                ot = att_api.overtime(str(day))
                mine = next(r for r in ot["rows"] if r["employee"] == f["e_emp2"])
                assert mine["hours"] >= 1.33 and str(day) in mine["days"], mine
            joined = getdate(frappe.db.get_value("Employee", f["e_emp2"], "date_of_joining"))
            before = [c for c in row["cells"] if getdate(c["date"]) < joined]
            assert all(c["code"] == "" for c in before), "days before joining are not absences"
            att_api.export_register(str(day), file_format="xlsx")
            assert frappe.response["filecontent"][:2] == b"PK"
            frappe.response.pop("filecontent", None); frappe.response.pop("type", None)
        check("attendance register: late minutes, overtime (Art. 107), Excel export", register_late_and_overtime)

        def employee_requests():
            frappe.set_user("Administrator")
            for sr in frappe.get_all("Shift Request", filters={"employee": f["e_emp2"], "docstatus": ["<", 2]}, fields=["name", "docstatus"]):
                for sa in frappe.get_all("Shift Assignment", filters={"shift_request": sr.name, "docstatus": 1}, pluck="name"):
                    frappe.get_doc("Shift Assignment", sa).cancel()
                doc = frappe.get_doc("Shift Request", sr.name)
                doc.cancel() if sr.docstatus == 1 else doc.delete()
            for ar in frappe.get_all("Attendance Request", filters={"employee": f["e_emp2"], "docstatus": ["<", 2]}, fields=["name", "docstatus"]):
                doc = frappe.get_doc("Attendance Request", ar.name)
                doc.cancel() if ar.docstatus == 1 else doc.delete()
            frappe.db.set_value("Employee", f["e_emp2"], "shift_request_approver", None)
            frappe.db.commit()
            frappe.set_user(f["emp2"])
            future = str(add_days(nowdate(), 40))
            expect_error(lambda: ess.request_shift("AXT Day", future), frappe.ValidationError)  # no approver yet
            frappe.set_user("Administrator")
            frappe.db.set_value("Employee", f["e_emp2"], "shift_request_approver", f["mgr"])
            frappe.db.commit()
            frappe.set_user(f["emp2"])
            sr = ess.request_shift("AXT Day", future, future)
            expect_error(lambda: ess.request_attendance(future, future, "On Duty", "x"), frappe.ValidationError)  # future
            expect_error(lambda: ess.request_attendance(str(past_workday(5)), str(past_workday(5)), "On Duty", ""), frappe.ValidationError)
            ar = ess.request_attendance(str(past_workday(5)), str(past_workday(5)), "On Duty", "Forgot to punch out")
            mine = {r["name"]: r for r in ess.my_requests()}
            assert sr["name"] in mine and ar["name"] in mine and mine[ar["name"]]["status"] == "Open", mine
            frappe.set_user(f["mgr"])
            inbox = approvals.inbox()
            names = {i["name"] for i in inbox["items"]} if isinstance(inbox, dict) else {i["name"] for i in inbox}
            assert sr["name"] in names, "shift request reaches the approver's inbox"
            approvals.act("Shift Request", sr["name"], "Approve", comment="OK for next month")
            assert frappe.db.exists("Shift Assignment", {"shift_request": sr["name"], "docstatus": 1})
            trail = approvals.activity("Shift Request", sr["name"])
            kinds = [e["kind"] for e in trail["events"]]
            assert kinds[0] == "created" and trail["events"][0]["user"] == f["emp2"], trail["events"][0]
            status_change = [e for e in trail["events"] if e["kind"] == "changed" and any(c["field"] == "status" for c in e["changes"])]
            assert status_change and status_change[-1]["user"] == f["mgr"], trail["events"]
            assert any(e["kind"] == "comment" and "next month" in e["text"] for e in trail["events"]), trail["events"]
            assert trail["desk_url"] == f"/app/shift-request/{sr['name']}" and not trail["pending_with"]
            assert sr["name"] in {d["name"] for d in approvals.decided()["items"]}
            frappe.set_user(f["emp"])
            expect_error(lambda: approvals.activity("Shift Request", sr["name"]), frappe.PermissionError)
        check("employee shift and attendance requests reach the approver; approval creates the assignment", employee_requests)

        def system_activity():
            from alphax_hr.api import activity
            frappe.set_user(f["hr"])
            d = hr.employee(f["e_emp2"])
            phone = "055" + frappe.generate_hash(length=10).translate(str.maketrans("abcdef", "123456"))[:7]
            phone = "".join(ch if ch.isdigit() else "7" for ch in phone)
            hr.update_employee(f["e_emp2"], {"cell_number": phone}, d["modified"])
            t = activity.trail("Employee", f["e_emp2"])
            hit = [e for e in t["events"] if e["kind"] == "changed" and any(c["field"] == "cell_number" and c["to"] == phone for c in e["changes"])]
            assert hit and hit[-1]["user"] == f["hr"], t["events"][-3:]
            feed = activity.feed(employee=f["e_emp2"])
            assert any(i["doctype"] == "Employee" and i["docname"] == f["e_emp2"] and i["exists"] for i in feed["items"]), feed["items"][:3]
            assert all(i["user"] == f["hr"] for i in activity.feed(user=f["hr"])["items"])
            frappe.set_user(f["emp"])
            expect_error(lambda: activity.feed(), frappe.PermissionError)
            expect_error(lambda: activity.trail("Employee", f["e_emp2"]), frappe.PermissionError)
            expect_error(lambda: activity.trail("User", f["emp"]), frappe.PermissionError)  # not an HR record type
        check("system-wide activity: record trail with field changes, HR feed with filters, privacy", system_activity)

        def row_size_guard():
            from alphax_hr import install
            frappe.set_user("Administrator")
            frappe.db.sql_ddl("ALTER TABLE `tabEmployee` MODIFY `alphax_gosi_number` varchar(140)")
            install.shrink_own_columns()
            col = {c.Field: c.Type for c in frappe.db.sql("SHOW COLUMNS FROM `tabEmployee`", as_dict=True)}
            assert col["alphax_gosi_number"] == "varchar(64)" and col["alphax_employee_name_ar"] == "text", col
            assert install.employee_row_size()["used"] < install.ROW_LIMIT
        check("row-size guard: AlphaX narrows its own Employee columns before migrate", row_size_guard)

        def setup_and_health():
            from alphax_hr.api import setup
            frappe.set_user(f["emp"])
            expect_error(setup.health, frappe.PermissionError)
            frappe.set_user(f["hr"])
            expect_error(setup.health, frappe.PermissionError)   # System Managers only
            frappe.set_user("Administrator")
            h = setup.health()
            assert {"scheduler", "workers", "employee_row_size"} <= {c["key"] for c in h["checks"]}
            frappe.set_user(f["hr"])
            hs = setup.hr_status()
            keys = {c["key"] for c in hs["checks"]}
            assert {"holiday_lists", "salary_mapping", "leave_approver", "documents_expiring", "mandatory_missing",
                    "no_salary", "approvals_waiting"} <= keys, keys
            assert "check_failed" not in keys, [c for c in hs["checks"] if c["key"] == "check_failed"]
            # bulk fix: give an employee without a shift approver one
            frappe.set_user("Administrator")
            frappe.db.set_value("Employee", f["e_emp"], "shift_request_approver", None); frappe.db.commit()
            frappe.set_user(f["hr"])
            aff = setup.affected("shift_approver")
            assert any(r["name"] == f["e_emp"] for r in aff["rows"]) and aff["set_field"] == "shift_request_approver"
            res = setup.bulk_fix("shift_approver", [f["e_emp"]], f["mgr"])
            assert res["done"] == [f["e_emp"]] and frappe.db.get_value("Employee", f["e_emp"], "shift_request_approver") == f["mgr"]
            expect_error(lambda: setup.bulk_fix("shift_approver", [f["e_emp"]], "nobody@nowhere"), frappe.ValidationError)
            for k in ("documents_expiring", "mandatory_missing", "no_salary", "user_account", "holiday_lists"):
                assert "rows" in setup.affected(k)
            frappe.set_user(f["emp"])
            expect_error(setup.hr_status, frappe.PermissionError)
            frappe.set_user(f["hr"])
            st = setup.get_settings()
            assert any(f_["fieldname"] == "probation_days" for sec in st["sections"] for f_ in sec["fields"])
            old = st["values"]["document_alert_days"]
            saved = setup.save_settings({"values": {"document_alert_days": 45, "leave_rules": []}, "component_map": st["component_map"]})
            assert saved["values"]["document_alert_days"] == 45 and saved["component_map"] == st["component_map"]
            setup.save_settings({"values": {"document_alert_days": old}})
        check("setup & health: checks run, settings save (HR only)", setup_and_health)

        def record_view():
            from alphax_hr.api import records
            frappe.set_user(f["emp"])
            name = frappe.get_all("Leave Application", filters={"employee": f["e_emp"]}, pluck="name", limit=1)[0]
            r = records.get("Leave Application", name)
            labels = {fl["label"] for sec in r["sections"] for fl in sec["fields"]}
            assert {"Leave Type", "From Date", "To Date"} <= labels, labels
            assert r["employee"] == f["e_emp"] and r["desk_url"] is None
            expect_error(lambda: records.get("User", f["emp"]), frappe.PermissionError)
            other = frappe.get_all("Leave Application", filters={"employee": f["e_emp2"]}, pluck="name", limit=1)
            if other:
                expect_error(lambda: records.get("Leave Application", other[0]), frappe.PermissionError)
            frappe.set_user(f["mgr"])
            assert isinstance(records.get("Leave Application", name)["actions"], list)
        check("in-app record view: all fields in the record's layout, permissions enforced", record_view)

        def employment_contract():
            from alphax_hr.api import contract
            frappe.set_user(f["hr"])
            h = contract.preview(f["e_emp"])["html"]
            assert "Employment Contract" in h and "عقد عمل" in h and frappe.db.get_value("Employee", f["e_emp"], "employee_name") in h
            contract.download(f["e_emp"])
            assert frappe.response["type"] == "pdf" and frappe.response["filecontent"][:4] == b"%PDF"
            assert contract.save(f["e_emp"])["file_url"]
            assert frappe.db.exists("File", {"attached_to_name": f["e_emp"], "file_name": ["like", "Employment-Contract-%"]})
            frappe.response.pop("filecontent", None); frappe.response.pop("type", None)
            frappe.set_user(f["emp"])
            expect_error(lambda: contract.html(f["e_emp"]), frappe.PermissionError)
        check("bilingual employment contract: HTML + PDF saved to the employee (HR only)", employment_contract)

        print("\n== Employee requests")
        def request_engine():
            from alphax_hr.api import requests as rq, approvals
            frappe.db.delete("AlphaX Request", {"employee": ["in", [f["e_emp"], f["e_emp2"]]]})
            frappe.set_user(f["emp"])
            names = {t["name"] for t in rq.types()}
            assert {"Salary Certificate", "Exit & Re-entry Visa", "Resignation"} <= names
            expect_error(lambda: rq.create("Salary Certificate", {"purpose": "Bank"}), frappe.ValidationError)  # addressed_to missing
            expect_error(lambda: rq.create("Business Trip", {"destination": "Jeddah", "from_date": "2026-05-10",
                                                             "to_date": "2026-05-01", "purpose": "x"}), frappe.ValidationError)
            # Letter: manager not needed -> HR approves -> PDF letter attached, completed
            r = rq.create("Salary Certificate", {"addressed_to": "Al Rajhi Bank", "purpose": "Bank"})
            assert r["status"] == "Pending HR", r
            # Visa: manager first, then HR
            v = rq.create("Exit & Re-entry Visa", {"visa_type": "Single", "from_date": add_days(nowdate(), 10),
                                                    "to_date": add_days(nowdate(), 30)})
            assert v["status"] == "Pending Manager"
            assert {x["name"] for x in rq.mine()} >= {r["name"], v["name"]}
            # Employee cannot approve own request or tamper through the REST layer
            expect_error(lambda: approvals.act("AlphaX Request", v["name"], "Approve"), frappe.PermissionError)
            d = frappe.get_doc("AlphaX Request", v["name"]); d.status = "Approved"
            expect_error(lambda: d.save(), frappe.PermissionError)
            # Another employee cannot read it
            frappe.set_user(f["emp2"])
            assert v["name"] not in {x.name for x in frappe.get_list("AlphaX Request")}
            expect_error(lambda: rq.all_requests(), frappe.PermissionError)
            # Manager sees it in the inbox and approves -> Pending HR
            frappe.set_user(f["mgr"])
            items = approvals.inbox("AlphaX Request")["items"]
            assert [i for i in items if i["name"] == v["name"]] and not [i for i in items if i["name"] == r["name"]]
            assert approvals.act("AlphaX Request", v["name"], "Approve", "ok")["status"] == "Pending HR"
            frappe.set_user(f["hr"])
            listing = rq.all_requests(status="open")
            assert {r["name"], v["name"]} <= {x["name"] for x in listing["rows"]}
            assert approvals.act("AlphaX Request", v["name"], "Approve")["status"] == "Approved"
            assert approvals.act("AlphaX Request", v["name"], "Complete", "Visa issued")["status"] == "Completed"
            out = approvals.act("AlphaX Request", r["name"], "Approve")
            doc = frappe.get_doc("AlphaX Request", r["name"])
            assert doc.status == "Completed" and doc.letter, (out, doc.status)
            fdoc = frappe.get_doc("File", {"file_url": doc.letter})
            assert fdoc.get_content()[:4] == b"%PDF"
            from alphax_hr.api.activity import trail
            assert trail("AlphaX Request", v["name"])["events"]
            # Non-Saudi-only type refused for a Saudi; resignation updates the employee
            frappe.set_user(f["mgr"])
            expect_error(lambda: rq.create("Iqama Renewal", {}), frappe.ValidationError)
            frappe.set_user(f["emp2"])
            res = rq.create("Resignation", {"last_working_day": add_days(nowdate(), 5)})
            assert "short_notice" in frappe.get_doc("AlphaX Request", res["name"]).details
            frappe.set_user(f["emp2"]); c = rq.create("General Request", {}, reason="test cancel")
            assert approvals.act("AlphaX Request", c["name"], "Cancel") if False else rq.decide(c["name"], "Cancel")["status"] == "Cancelled"
            frappe.set_user(f["mgr"]); approvals.act("AlphaX Request", res["name"], "Approve")
            frappe.set_user(f["hr"]); approvals.act("AlphaX Request", res["name"], "Approve")
            assert str(frappe.db.get_value("Employee", f["e_emp2"], "relieving_date")) == str(add_days(nowdate(), 5))
            frappe.db.set_value("Employee", f["e_emp2"], {"relieving_date": None, "resignation_letter_date": None})
            # HR configures a type
            t = rq.update_type("General Request", {"sla_days": 1, "fields": [{"fieldname": "topic", "label": "Topic", "type": "Data", "reqd": 1}]})
            assert t["fields"][0]["fieldname"] == "topic"
            expect_error(lambda: rq.update_type("General Request", {"fields": [{"fieldname": "x", "type": "Code"}]}), frappe.ValidationError)
            rq.update_type("General Request", {"sla_days": 3, "fields": []})
        check("employee requests: letters with PDF, manager -> HR flow, privacy, resignation, type settings", request_engine)

        print("\n== Penalties and warnings")
        def penalties_flow():
            from alphax_hr.api import penalties as pen, salary
            frappe.set_user("Administrator")
            for p_ in frappe.get_all("AlphaX Penalty", filters={"employee": f["e_emp2"]}, fields=["name", "additional_salary"]):
                if p_.additional_salary and frappe.db.get_value("Additional Salary", p_.additional_salary, "docstatus") == 1:
                    frappe.get_doc("Additional Salary", p_.additional_salary).cancel()
                frappe.delete_doc("AlphaX Penalty", p_.name, force=1, ignore_permissions=True)
            if not frappe.db.exists("Salary Structure Assignment", {"employee": f["e_emp2"], "docstatus": 1}):
                salary.assign(f["e_emp2"], {"mode": "total", "total": 9000}, "2025-03-01")
            daily = round(pen.monthly_wage(f["e_emp2"]) / 30, 2)
            assert daily > 0
            frappe.set_user(f["emp2"])
            expect_error(lambda: pen.create(f["e_emp2"], "Late arrival up to 15 minutes", nowdate(), "x"), frappe.PermissionError)
            frappe.set_user(f["hr"])
            names = {v["name"] for v in pen.violation_types()}
            assert "Absence without excuse (1 day)" in names and len(names) >= 9
            late = "Late arrival up to 15 minutes"
            a = pen.create(f["e_emp2"], late, add_days(nowdate(), -5), "Late 10 min", issue=1)
            assert a["action"] == "Warning" and a["amount"] == 0 and a["status"] == "Issued" and not a["additional_salary"], a
            b = pen.create(f["e_emp2"], late, add_days(nowdate(), -3), "Late 12 min", issue=1)
            assert b["occurrence"] == 2 and b["action"] == "Deduction" and abs(b["amount"] - round(daily * 0.05, 2)) < 0.01, b
            assert frappe.db.get_value("Additional Salary", b["additional_salary"], "docstatus") == 1
            ab = "Absence without excuse (1 day)"
            pen.create(f["e_emp2"], ab, add_days(nowdate(), -6), "Absent", issue=1)
            pen.create(f["e_emp2"], ab, add_days(nowdate(), -4), "Absent", issue=1)
            c = pen.preview(f["e_emp2"], ab, add_days(nowdate(), -2))
            # 1 + 2 + 0.05 already used this month -> only 1.95 of the 3 days fit under the 5-day cap
            assert c["occurrence"] == 3 and c["capped_note"] and abs(c["amount"] - round(daily * 1.95, 2)) < 0.02, c
            d = pen.create(f["e_emp2"], ab, add_days(nowdate(), -40), "Old", discovered_on=add_days(nowdate(), -40))
            expect_error(lambda: pen.issue_penalty(d["name"]), frappe.ValidationError)
            assert not pen.create(f["e_emp2"], late, add_days(nowdate(), -1), "draft only")["additional_salary"]
            expect_error(lambda: pen.create(f["e_emp2"], late, add_days(nowdate(), 2), "future"), frappe.ValidationError)
            # employee sees issued ones only, acknowledges / objects
            frappe.set_user(f["emp2"])
            mine = pen.mine()
            assert all(m["status"] != "Draft" for m in mine) and len(mine) == 4, [m["status"] for m in mine]
            assert pen.respond(a["name"], "Acknowledge")["status"] == "Acknowledged"
            expect_error(lambda: pen.respond(b["name"], "Object"), frappe.ValidationError)
            assert pen.respond(b["name"], "Object", "I had a permission from my manager")["status"] == "Objected"
            frappe.set_user(f["emp"])
            assert not frappe.get_list("AlphaX Penalty", filters={"employee": f["e_emp2"]})
            expect_error(lambda: pen.respond(a["name"], "Acknowledge"), frappe.PermissionError)
            frappe.set_user(f["hr"])
            expect_error(lambda: pen.cancel_penalty(b["name"], ""), frappe.ValidationError)
            assert pen.cancel_penalty(b["name"], "Permission confirmed")["status"] == "Cancelled"
            assert frappe.db.get_value("Additional Salary", b["additional_salary"], "docstatus") == 2
            assert isinstance(pen.suggestions(nowdate()), list)
            assert len(pen.penalties(employee=f["e_emp2"])) == 6
        check("penalties: repeat escalation, 5-day monthly cap, 30-day limit, payroll deduction, acknowledge/object, cancel", penalties_flow)

        print("\n== Payroll control and final settlement")
        def payroll_control_flow():
            from alphax_hr.api import payroll_control as pc
            month = str(frappe.utils.get_first_day(nowdate()))
            frappe.set_user("Administrator")
            for per in frappe.get_all("AlphaX Payroll Period", filters={"company": COMPANY}, fields=["name", "payroll_entry"]):
                if per.payroll_entry and frappe.db.exists("Payroll Entry", per.payroll_entry):
                    for sl in frappe.get_all("Salary Slip", filters={"payroll_entry": per.payroll_entry}, fields=["name", "docstatus"]):
                        if sl.docstatus == 1:
                            frappe.get_doc("Salary Slip", sl.name).cancel()
                        frappe.delete_doc("Salary Slip", sl.name, force=1, ignore_permissions=True)
                    pe = frappe.get_doc("Payroll Entry", per.payroll_entry)
                    if pe.docstatus == 1:
                        pe.flags.ignore_links = True
                        pe.cancel()
                    frappe.delete_doc("Payroll Entry", pe.name, force=1, ignore_permissions=True)
                frappe.delete_doc("AlphaX Payroll Period", per.name, force=1, ignore_permissions=True)
            for pe_name in frappe.get_all("Payroll Entry", filters={"company": COMPANY, "docstatus": 0}, pluck="name"):
                frappe.delete_doc("Payroll Entry", pe_name, force=1, ignore_permissions=True)
            frappe.set_user(f["emp"])
            expect_error(lambda: pc.period(COMPANY, month), frappe.PermissionError)
            frappe.set_user(f["hr"])
            p = pc.period(COMPANY, month)
            keys = {c["key"] for c in p["checklist"]["checks"]}
            assert {"pending_leave_application", "no_salary", "joiners", "leavers", "additional", "overtime"} <= keys, keys
            assert p["status"] == "Open" and p["checklist"]["employees"] > 0
            # a waiting leave request is a blocker
            lt = f["lt"]
            day = getdate(get_last_day(month))
            while day.weekday() in (4, 5):
                day = getdate(add_days(day, -1))
            la = frappe.get_doc({"doctype": "Leave Application", "employee": f["e_emp"], "leave_type": lt, "from_date": day,
                                 "to_date": day, "leave_approver": f["mgr"], "status": "Open"})
            la.flags.ignore_permissions = True
            la.insert()
            cl = pc.checklist(COMPANY, month)
            item = [c for c in cl["checks"] if c["key"] == "pending_leave_application"][0]
            assert item["severity"] == "blocker" and any(i["name"] == la.name for i in item["items"]), item
            expect_error(lambda: pc.advance(COMPANY, month, "prepare"), frappe.ValidationError)
            expect_error(lambda: pc.advance(COMPANY, month, "approve"), frappe.ValidationError)  # wrong order
            p = pc.advance(COMPANY, month, "prepare", "checked with finance", override=1)
            assert p["status"] == "Prepared" and p["prepared_by"] == f["hr"]
            p = pc.advance(COMPANY, month, "review")
            p = pc.advance(COMPANY, month, "approve", "ok", override=1)
            assert p["status"] == "Approved" and p["approved_by"] == f["hr"]
            assert any(e.get("kind") == "comment" for e in p["trail"]), p["trail"]
            p = pc.advance(COMPANY, month, "reopen", "redo")
            assert p["status"] == "Open" and not p["approved_by"]
            frappe.set_user("Administrator")
            frappe.delete_doc("Leave Application", la.name, force=1, ignore_permissions=True)
            frappe.set_user(f["hr"])
            for st in ("prepare", "review", "approve"):
                pc.advance(COMPANY, month, st, "go", override=1)
            try:
                p = pc.advance(COMPANY, month, "process", "run", override=1)
            except frappe.ValidationError as exc:
                # slip creation depends on every employee's payroll setup; the failure must be reported, not swallowed
                print("    payroll processing reported:", exc)
                pe = frappe.db.get_value("Payroll Entry", {"company": COMPANY, "start_date": month}, ["name", "status"], as_dict=True)
                assert pe and pe.status == "Failed" and pc.period(COMPANY, month)["status"] == "Approved", pe
            else:
                assert p["status"] == "Processed" and p["payroll_entry"], p
                assert frappe.db.get_value("Payroll Entry", p["payroll_entry"], "docstatus") == 1
                expect_error(lambda: pc.advance(COMPANY, month, "reopen"), frappe.ValidationError)
            assert isinstance(pc.add_overtime(COMPANY, month)["created"], list)
        check("payroll control: checklist with records, blockers + manager override, prepare/review/approve/process, reopen", payroll_control_flow)

        def final_settlement_flow():
            from alphax_hr.api import settlements as fs
            from alphax_hr.saudi import eosb as eosb_rules
            frappe.set_user("Administrator")
            for n in frappe.get_all("AlphaX Final Settlement", filters={"employee": f["e_emp"]}, fields=["name", "additional_salaries"]):
                for add in (n.additional_salaries or "").split():
                    if frappe.db.get_value("Additional Salary", add, "docstatus") == 1:
                        frappe.get_doc("Additional Salary", add).cancel()
                frappe.delete_doc("AlphaX Final Settlement", n.name, force=1, ignore_permissions=True)
            if not frappe.db.exists("Salary Structure Assignment", {"employee": f["e_emp"], "docstatus": 1}):
                from alphax_hr.api import salary
                salary.assign(f["e_emp"], {"mode": "total", "total": 12000}, "2021-01-10")
            frappe.set_user(f["emp"])
            expect_error(lambda: fs.prepare(f["e_emp"], nowdate(), "Resignation"), frappe.PermissionError)
            frappe.set_user(f["hr"])
            exit_on = add_days(nowdate(), 20)
            d = fs.prepare(f["e_emp"], exit_on, "Resignation", "With payroll", monthly_wage=12000, leave_days=10, other_deductions=500)
            exp = eosb_rules.calculate(getdate(frappe.db.get_value("Employee", f["e_emp"], "date_of_joining")), getdate(exit_on), 12000, "Resignation")
            assert abs(d["eosb_amount"] - float(exp.award)) < 0.01 and d["leave_amount"] == 4000 and d["status"] == "Draft", d
            assert abs(d["net_amount"] - (float(exp.award) + 4000 - 500 - d["advances"])) < 0.01
            expect_error(lambda: fs.prepare(f["e_emp"], exit_on, "Resignation"), frappe.ValidationError)  # one per employee
            d = fs.prepare(f["e_emp"], exit_on, "Termination by employer", "With payroll", monthly_wage=12000, leave_days=10, name=d["name"])
            assert d["eosb_factor"] == 1
            fs.statement(d["name"])
            assert frappe.response["type"] == "pdf" and frappe.response["filecontent"][:4] == b"%PDF"
            frappe.response.pop("filecontent", None); frappe.response.pop("type", None)
            a = fs.approve(d["name"])
            adds = a["additional_salaries"].split()
            assert a["status"] == "Approved" and len(adds) == 2, a
            assert {frappe.db.get_value("Additional Salary", x, "salary_component") for x in adds} == {"End of Service Benefit", "Leave Encashment"}
            assert str(frappe.db.get_value("Employee", f["e_emp"], "relieving_date")) == str(exit_on)
            fs.cancel(d["name"], "test")
            assert all(frappe.db.get_value("Additional Salary", x, "docstatus") == 2 for x in adds)
            assert [s for s in fs.settlements() if s["name"] == d["name"]][0]["status"] == "Cancelled"
            frappe.db.set_value("Employee", f["e_emp"], "relieving_date", None)
        check("final settlement: EOS award + leave encashment, with payroll (Additional Salary), statement PDF, cancel", final_settlement_flow)

        print("\n== Cut-over from CentralHRMS")
        def cutover_flow():
            from alphax_hr.api import cutover, appraisals
            frappe.set_user("Administrator")
            def legacy_dt(name, fields, submittable=0):
                if frappe.db.exists("DocType", name):
                    return
                frappe.get_doc({"doctype": "DocType", "name": name, "module": "HR", "custom": 1, "is_submittable": submittable,
                                "autoname": "hash", "fields": fields,
                                "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "submit": submittable,
                                                 "cancel": submittable}]}).insert(ignore_permissions=True)
            legacy_dt("Letters Request", [{"fieldname": "employee", "fieldtype": "Link", "options": "Employee", "label": "Employee"},
                                          {"fieldname": "reason", "fieldtype": "Small Text", "label": "Reason"},
                                          {"fieldname": "job_title", "fieldtype": "Data", "label": "Job Title"}], 1)
            legacy_dt("Warning Letter", [{"fieldname": "employee", "fieldtype": "Link", "options": "Employee", "label": "Employee"},
                                         {"fieldname": "warning_date", "fieldtype": "Date", "label": "Warning Date"},
                                         {"fieldname": "reason", "fieldtype": "Small Text", "label": "Reason"},
                                         {"fieldname": "number_of_warnings", "fieldtype": "Int", "label": "Warnings"}], 1)
            frappe.db.delete("AlphaX Request", {"legacy_ref": ["is", "set"]})
            frappe.db.delete("AlphaX Penalty", {"source_ref": ["like", "Warning Letter:%"]})
            frappe.db.delete("Letters Request"); frappe.db.delete("Warning Letter")
            a = frappe.get_doc({"doctype": "Letters Request", "employee": f["e_emp"], "reason": "Bank", "job_title": "Engineer"}).insert()
            a.submit()
            frappe.get_doc({"doctype": "Letters Request", "employee": f["e_emp2"], "reason": "Embassy"}).insert()
            w = frappe.get_doc({"doctype": "Warning Letter", "employee": f["e_emp2"], "warning_date": add_days(nowdate(), -100),
                                "reason": "Late", "number_of_warnings": 2}).insert()
            w.submit()
            frappe.set_user(f["emp"])
            expect_error(lambda: cutover.readiness(), frappe.PermissionError)
            frappe.set_user(f["hr"])
            r = cutover.readiness()
            req = [i for i in r["items"] if i["key"] == "requests"][0]
            assert req["status"] == "todo" and req["count"] == 2, req
            plan = cutover.import_legacy("requests", 1)
            assert plan["dry_run"] and plan["count"] == 2 and not frappe.db.count("AlphaX Request", {"legacy_ref": ["is", "set"]})
            assert cutover.import_legacy("requests", 0)["count"] == 2
            assert cutover.import_legacy("requests", 0)["count"] == 0  # idempotent
            imp = frappe.get_doc("AlphaX Request", {"legacy_ref": f"Letters Request:{a.name}"})
            assert imp.status == "Completed" and imp.request_type == "Employment Letter" and "Engineer" in imp.details and imp.reason == "Bank"
            assert frappe.db.get_value("AlphaX Request", {"legacy_ref": ["like", "Letters Request:%"], "employee": f["e_emp2"]}, "status") == "Pending HR"
            assert cutover.import_legacy("warnings", 0)["count"] == 1
            pw = frappe.get_doc("AlphaX Penalty", {"source_ref": f"Warning Letter:{w.name}"})
            assert pw.status == "Acknowledged" and pw.action == "Warning" and pw.occurrence == 2 and not pw.amount
            r = cutover.readiness()
            assert [i for i in r["items"] if i["key"] == "requests"][0]["status"] == "ok"
            assert [i for i in r["items"] if i["key"] == "warnings"][0]["status"] == "ok"
            assert cutover.import_legacy("identity", 1)["dry_run"]
            assert isinstance(appraisals.cycles()["cycles"], list) and isinstance(appraisals.appraisals(), list)
            frappe.set_user(f["emp"])
            assert isinstance(appraisals.mine(), list)
        check("cut-over: readiness, dry-run and idempotent import of legacy requests and warning letters; appraisals", cutover_flow)

        print("\n== ESS services, permissions, mobile app")
        def permissions_flow():
            from alphax_hr.api import requests as rq, approvals, attendance
            frappe.db.delete("AlphaX Request", {"employee": f["e_emp"], "request_type": ["in", ["Late Arrival Permission", "Early Exit Permission"]]})
            frappe.db.set_single_value("AlphaX HR Settings", "permissions_per_month", 2)
            frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
            frappe.set_user(f["emp"])
            day = add_days(nowdate(), 1)
            expect_error(lambda: rq.create("Late Arrival Permission", {"date": day, "time": "25:00"}), frappe.ValidationError)
            expect_error(lambda: rq.create("Late Arrival Permission", {"date": add_days(nowdate(), -20), "time": "09:00"}), frappe.ValidationError)
            a = rq.create("Late Arrival Permission", {"date": day, "time": "9:30"}, reason="Hospital appointment")
            assert a["status"] == "Pending Manager"
            assert frappe.parse_json(frappe.db.get_value("AlphaX Request", a["name"], "details"))["time"] == "09:30"
            expect_error(lambda: rq.create("Late Arrival Permission", {"date": day, "time": "10:00"}), frappe.ValidationError)  # same day
            b = rq.create("Early Exit Permission", {"date": day, "time": "15:00"})
            expect_error(lambda: rq.create("Early Exit Permission", {"date": add_days(day, 1), "time": "15:00"}), frappe.ValidationError)  # limit 2
            from alphax_hr.api import ess
            assert any(r["type"] == "Permission" for r in ess.my_requests())
            frappe.set_user(f["mgr"])
            assert approvals.act("AlphaX Request", a["name"], "Approve")["status"] == "Completed"  # no HR step
            frappe.set_user("Administrator")
            ex = rq.excused([f["e_emp"]], nowdate(), add_days(nowdate(), 5))
            assert ex[(f["e_emp"], getdate(day))] == {"late": "09:30"}, ex  # the early exit is not approved yet
            st = frappe._dict(start_time="08:00:00", end_time="17:00:00")
            assert attendance._permit_minutes(getdate(day), st, "09:30", True) == 90
            assert attendance._permit_minutes(getdate(day), st, "15:00", False) == 120
            assert attendance._permit_minutes(getdate(day), st, True, True) is None
            frappe.db.set_single_value("AlphaX HR Settings", "permissions_per_month", 3)
        check("late arrival / early exit permissions: limits, manager approval, excused minutes", permissions_flow)

        def ess_services():
            from alphax_hr.api import ess
            frappe.set_user("Administrator")
            payable = frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Payable", "is_group": 0})
            if not frappe.db.get_value("Company", COMPANY, "default_expense_claim_payable_account"):
                frappe.db.set_value("Company", COMPANY, "default_expense_claim_payable_account", payable)
            exp_acc = frappe.db.get_value("Account", {"company": COMPANY, "root_type": "Expense", "is_group": 0})
            if not frappe.db.exists("Expense Claim Type", "AXT Travel"):
                frappe.get_doc({"doctype": "Expense Claim Type", "expense_type": "AXT Travel",
                                "accounts": [{"company": COMPANY, "default_account": exp_acc}]}).insert(ignore_permissions=True)
            frappe.set_user(f["emp"])
            assert any(t.name == "AXT Travel" for t in ess.expense_types())
            expect_error(lambda: ess.submit_expense("AXT Travel", 0, nowdate()), frappe.ValidationError)
            expect_error(lambda: ess.submit_expense("AXT Travel", 50, add_days(nowdate(), 3)), frappe.ValidationError)
            r = ess.submit_expense("AXT Travel", 120.5, nowdate(), "Taxi to client")
            assert r["approver"] == f["mgr"], r
            assert any(c.name == r["name"] for c in ess.my_expense_claims())
            frappe.set_user(f["mgr"])
            from alphax_hr.api import approvals
            assert any(i["name"] == r["name"] for i in approvals.inbox("Expense Claim")["items"])
            frappe.set_user(f["emp2"])
            expect_error(lambda: ess.withdraw_expense(r["name"]), frappe.ValidationError)
            frappe.set_user(f["emp"])
            ess.withdraw_expense(r["name"])
            assert not frappe.db.exists("Expense Claim", r["name"])
            d = ess.my_documents()
            assert any(x["document"] == "Iqama / ID" for x in d["documents"]) and isinstance(d["files"], list)
            assert ess.my_team()["team"] == []
            frappe.set_user(f["mgr"])
            team = ess.my_team()
            assert {m["name"] for m in team["team"]} >= {f["e_emp"], f["e_emp2"]} and "in" in team["summary"], team
        check("ESS: expense claims to the approver, withdraw, my documents, my team", ess_services)

        def pwa_service_worker():
            from alphax_hr.api import pwa
            frappe.set_user("Guest")
            pwa.service_worker()
            assert "alphax-" in frappe.response["filecontent"] and frappe.response["type"] == "binary"
            frappe.response.pop("filecontent", None); frappe.response.pop("type", None)
            from werkzeug.wrappers import Response
            resp = Response("x", headers={"Content-Disposition": "attachment"})
            pwa.after_request(resp, frappe._dict(path="/api/method/alphax_hr.api.pwa.service_worker"))
            assert resp.mimetype == "application/javascript" and resp.headers["Service-Worker-Allowed"] == "/alphax"
            assert "Content-Disposition" not in resp.headers
        check("mobile app: service worker served as a script for the /alphax scope", pwa_service_worker)

        print("\n== Leave form, attendance policy, vacation plan")
        def leave_site_mandatory_fields():
            from alphax_hr.api import ess
            frappe.set_user("Administrator")
            for fn, label, ft, opts in (("first_day_report_to_work", "First Day Report to Work", "Date", None),
                                        ("custom_axt_leave_intent", "Leave Intent", "Select", "\nPlanned\nUnplanned")):
                if not frappe.db.exists("Custom Field", {"dt": "Leave Application", "fieldname": fn}):
                    frappe.get_doc({"doctype": "Custom Field", "dt": "Leave Application", "fieldname": fn, "label": label,
                                    "fieldtype": ft, "options": opts, "reqd": 1, "insert_after": "to_date"}).insert(ignore_permissions=True)
            frappe.clear_cache(doctype="Leave Application")
            try:
                frappe.set_user(f["emp"])
                form = ess.leave_form()
                assert [x["fieldname"] for x in form["fields"]] == ["custom_axt_leave_intent"], form
                assert form["auto"][0]["fieldname"] == "first_day_report_to_work"
                fd, td = next_working_pair(45)
                expect_error(lambda: ess.apply_leave(f["lt"], fd, td, "x"), frappe.ValidationError)
                r = ess.apply_leave(f["lt"], fd, td, "x", extra={"custom_axt_leave_intent": "Planned"})
                la = frappe.get_doc("Leave Application", r["name"])
                assert la.custom_axt_leave_intent == "Planned" and la.first_day_report_to_work > getdate(td), la.first_day_report_to_work
                ess.withdraw_leave(r["name"])
            finally:
                frappe.set_user("Administrator")
                for fn in ("first_day_report_to_work", "custom_axt_leave_intent"):
                    for cf in frappe.get_all("Custom Field", filters={"dt": "Leave Application", "fieldname": fn}, pluck="name"):
                        frappe.delete_doc("Custom Field", cf, ignore_permissions=True)
                frappe.clear_cache(doctype="Leave Application")
        check("leave request asks for the site's own mandatory fields; return-to-work date filled automatically", leave_site_mandatory_fields)

        def attendance_policy_flow():
            from alphax_hr.api import attendance_policy as ap, attendance, requests as rq
            frappe.set_user("Administrator")
            frappe.db.delete("AlphaX Attendance Policy")
            dept = frappe.db.get_value("Employee", f["e_emp"], "department")
            frappe.set_user(f["emp"])
            expect_error(lambda: ap.save({"policy_name": "x", "applies_to": "Everyone"}), frappe.PermissionError)
            frappe.set_user(f["hr"])
            expect_error(lambda: ap.save({"policy_name": "Bad", "applies_to": "Department"}), frappe.ValidationError)
            expect_error(lambda: ap.save({"policy_name": "Bad", "applies_to": "Everyone", "late_grace_minutes": "ten"}), frappe.ValidationError)
            ap.save({"policy_name": "AXT Ops", "applies_to": "Department", "department": dept, "late_grace_minutes": "20", "monthly_late_allowance": 30})
            ap.save({"policy_name": "AXT Exempt Omar", "applies_to": "Employee", "employee": f["e_emp2"], "exempt": 1, "permissions_per_month": "1"})
            expect_error(lambda: ap.save({"policy_name": "Dup", "applies_to": "Employee", "employee": f["e_emp2"]}), frappe.ValidationError)
            assert ap.for_employee(f["e_emp2"]).policy_name == "AXT Exempt Omar"
            assert ap.for_employee(f["e_emp"]).policy_name == "AXT Ops"
            assert {p["name"]: p["covers"] for p in ap.policies()}["AXT Exempt Omar"] == 1
            cells = [{"late": 10}, {"late": 0}, {"late": 25}]
            assert ap.apply_allowance(cells, 30) == 30 and cells[2]["late"] == 5
            data = attendance.month_data(nowdate())
            omar = next(r for r in data["rows"] if r["employee"] == f["e_emp2"])
            assert omar["policy"] == "AXT Exempt Omar" and omar["no_penalties"]
            assert not any(c["code"] in ("A", "M") for c in omar["cells"]), [c["code"] for c in omar["cells"]]
            frappe.db.delete("AlphaX Request", {"employee": f["e_emp2"], "request_type": ["in", ["Late Arrival Permission", "Early Exit Permission"]]})
            frappe.set_user(f["emp2"])
            rq.create("Late Arrival Permission", {"date": add_days(nowdate(), 2), "time": "09:00"})
            expect_error(lambda: rq.create("Late Arrival Permission", {"date": add_days(nowdate(), 3), "time": "09:00"}), frappe.ValidationError)
            frappe.set_user(f["hr"])
            ap.delete("AXT Exempt Omar"); ap.delete("AXT Ops")
        check("attendance exceptions policy: most specific wins, exempt, grace, free late minutes, permission limit", attendance_policy_flow)

        def vacation_plan_flow():
            from alphax_hr.api import leave_plan as lp, approvals
            frappe.set_user("Administrator")
            frappe.db.delete("AlphaX Leave Plan Period", {"parent": ["in", frappe.get_all("AlphaX Leave Plan", filters={"employee": ["in", [f["e_emp"], f["e_emp2"]]]}, pluck="name") or [""]]})
            frappe.db.delete("AlphaX Leave Plan", {"employee": ["in", [f["e_emp"], f["e_emp2"]]]})
            frappe.db.set_single_value("AlphaX HR Settings", "plan_min_block_days", 5)
            frappe.db.set_value("Employee", f["e_emp2"], "department", frappe.db.get_value("Employee", f["e_emp"], "department"))
            frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
            year = getdate(nowdate()).year
            frappe.set_user(f["emp2"])
            lp.save_my_plan(year, [{"from_date": f"{year}-12-20", "to_date": f"{year}-12-24"}])
            lp.submit_my_plan(year)
            frappe.set_user(f["emp"])
            p = lp.my_plan(year)
            assert p["status"] == "Draft" and p["entitlement"] > 0 and not p["name"]
            expect_error(lambda: lp.save_my_plan(year, [{"from_date": f"{year}-12-20", "to_date": f"{year}-12-22"},
                                                        {"from_date": f"{year}-12-22", "to_date": f"{year}-12-23"}]), frappe.ValidationError)
            p = lp.save_my_plan(year, [{"from_date": f"{year}-12-21", "to_date": f"{year}-12-22", "note": "short"}])
            assert p["periods"][0]["days"] > 0 and p["conflicts"][0]["max_off"] == 2 and p["conflicts"][0]["colleagues"], p["conflicts"]
            expect_error(lambda: lp.submit_my_plan(year), frappe.ValidationError)  # needs a 5-day block
            p = lp.save_my_plan(year, [{"from_date": f"{year}-12-20", "to_date": f"{year}-12-24"}])
            assert lp.submit_my_plan(year)["status"] == "Submitted"
            expect_error(lambda: lp.save_my_plan(year, []), frappe.ValidationError)
            frappe.set_user(f["mgr"])
            items = [i for i in approvals.inbox("AlphaX Leave Plan")["items"]]
            mine = next(i for i in items if i["employee"] == f["e_emp"])
            assert "Request changes" in mine["actions"]
            expect_error(lambda: approvals.act("AlphaX Leave Plan", mine["name"], "Request changes"), frappe.ValidationError)
            pl = lp.planner(year)
            assert any(w["by_department"] and any(v["off"] == 2 for v in w["by_department"].values()) for w in pl["weeks"]), "coverage"
            assert approvals.act("AlphaX Leave Plan", mine["name"], "Approve", "ok")["status"] == "Approved"
            frappe.set_user(f["emp2"])
            expect_error(lambda: approvals.act("AlphaX Leave Plan", mine["name"], "Approve"), frappe.PermissionError)
            assert not [x for x in frappe.get_list("AlphaX Leave Plan", filters={"employee": f["e_emp"]})]
            frappe.set_user(f["emp"])
            try:
                r = lp.apply_period(year, 1)
                assert frappe.db.get_value("Leave Application", r["name"], "from_date") == getdate(f"{year}-12-20")
                expect_error(lambda: lp.apply_period(year, 1), frappe.ValidationError)
                from alphax_hr.api import ess
                ess.withdraw_leave(r["name"])
            except frappe.ValidationError as exc:
                print("    apply from plan reported:", exc)  # e.g. no allocation for that leave type on a fresh site
            frappe.set_user("Administrator")
            frappe.db.set_single_value("AlphaX HR Settings", "plan_min_block_days", 0)
        check("vacation plan: periods, overlap, block rule, coverage with colleagues, approve via inbox, apply from plan", vacation_plan_flow)

        def broken_links_fix():
            from alphax_hr.api import setup
            frappe.set_user("Administrator")
            if not frappe.db.exists("DocType", "AXT Nationality"):
                frappe.get_doc({"doctype": "DocType", "name": "AXT Nationality", "module": "HR", "custom": 1, "autoname": "field:nationality",
                                "fields": [{"fieldname": "nationality", "fieldtype": "Data", "label": "Nationality", "reqd": 1, "unique": 1}],
                                "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1},
                                                {"role": "HR Manager", "read": 1, "write": 1, "create": 1}]}).insert(ignore_permissions=True)
            if not frappe.db.exists("Custom Field", {"dt": "Employee", "fieldname": "custom_axt_nationality"}):
                frappe.get_doc({"doctype": "Custom Field", "dt": "Employee", "fieldname": "custom_axt_nationality", "label": "AXT Nationality",
                                "fieldtype": "Link", "options": "AXT Nationality", "insert_after": "gender"}).insert(ignore_permissions=True)
            frappe.db.delete("AXT Nationality", {"name": "Tanzanian"})
            frappe.db.set_value("Employee", f["e_emp2"], "custom_axt_nationality", "Tanzanian")  # value removed from its list
            try:
                frappe.set_user(f["hr"])
                b = [x for x in setup.broken_employee_links() if x["field"] == "custom_axt_nationality"][0]
                assert b["values"] == ["Tanzanian"] and f["e_emp2"] in b["employees"] and b["creatable"], b
                chk = next(c for c in setup.hr_status()["checks"] if c["key"] == "broken_links")
                assert chk["status"] == "warn" and chk["fix"] == "create_missing_links" and "Tanzanian" in chk["detail"]
                r = setup.bulk_fix("reports_to", [f["e_emp2"]], f["e_mgr"])  # other stale links no longer block the fix
                assert r["done"] == [f["e_emp2"]], r
                assert setup.create_missing_links()["created"] == ["AXT Nationality: Tanzanian"]
                assert not [x for x in setup.broken_employee_links() if x["field"] == "custom_axt_nationality"]
                frappe.set_user(f["emp"])
                expect_error(setup.create_missing_links, frappe.PermissionError)
            finally:
                frappe.set_user("Administrator")
                frappe.db.set_value("Employee", f["e_emp2"], {"custom_axt_nationality": None, "reports_to": None})
        check("employee values missing from their lists: flagged, bulk fix not blocked, missing values created", broken_links_fix)

        print("\n== Employee profile, HR conversation, home")
        def profile_update_flow():
            from alphax_hr.api import ess, requests as rq, approvals, appraisals
            frappe.set_user("Administrator")
            frappe.db.delete("AlphaX Request", {"employee": f["e_emp"], "request_type": "Profile Update"})
            frappe.db.set_value("Employee", f["e_emp"], {"passport_number": "P0000001", "valid_upto": add_days(nowdate(), 400)})
            frappe.set_user(f["emp"])
            assert isinstance(appraisals.mine(), list)  # no role access to Appraisal needed for own scores
            ess.update_my_contact({"cell_number": "+966500000001"})
            form = ess.profile_change_form()
            fields = {x["fieldname"]: x for x in form["fields"]}
            assert form["enabled"] and "passport_number" in fields and fields["passport_number"]["document"]
            expect_error(lambda: ess.request_profile_change({"date_of_joining": "2020-01-01"}), frappe.ValidationError)
            expect_error(lambda: ess.request_profile_change({"passport_number": fields["passport_number"]["value"]}), frappe.ValidationError)
            expect_error(lambda: rq.create("Profile Update", {}), frappe.ValidationError)  # only through the profile
            r = ess.request_profile_change({"passport_number": "PNEW1234", "valid_upto": add_days(nowdate(), 3650)}, "Renewed")
            assert r["status"] == "Pending HR" and r["needs_document"]
            expect_error(lambda: ess.request_profile_change({"marital_status": "Married"}), frappe.ValidationError)  # one at a time
            assert ess.profile_change_form()["pending"]["name"] == r["name"]
            msgs = rq.post_message(r["name"], "Scan attached shortly")
            assert msgs[-1]["mine"] and msgs[-1]["from_employee"]
            frappe.set_user(f["emp2"])
            expect_error(lambda: rq.messages(r["name"]), frappe.PermissionError)
            frappe.set_user(f["hr"])
            row = next(x for x in rq.all_requests(status="open")["rows"] if x["name"] == r["name"])
            assert row["messages"] == 1 and row["last_from_employee"]
            expect_error(lambda: approvals.act("AlphaX Request", r["name"], "Approve"), frappe.ValidationError)  # needs the document
            rq.post_message(r["name"], "Please attach the new passport page")
            assert frappe.db.exists("Notification Log", {"for_user": f["emp"], "document_name": r["name"]})
            frappe.get_doc({"doctype": "File", "file_name": "passport.txt", "content": b"scan", "is_private": 1,
                            "attached_to_doctype": "AlphaX Request", "attached_to_name": r["name"]}).insert(ignore_permissions=True)
            assert approvals.act("AlphaX Request", r["name"], "Approve")["status"] == "Completed"
            emp = frappe.get_doc("Employee", f["e_emp"])
            assert emp.passport_number == "PNEW1234" and str(emp.valid_upto) == str(add_days(nowdate(), 3650))
            assert frappe.db.exists("File", {"attached_to_doctype": "Employee", "attached_to_name": f["e_emp"], "file_name": "passport.txt"})
        check("profile update: employee asks, HR talks and approves with the document, record and files updated", profile_update_flow)

        def home_announcements_activity():
            from alphax_hr.api import announcements as an, ess
            frappe.set_user("Administrator")
            frappe.db.delete("AlphaX Announcement")
            frappe.set_user(f["emp"])
            expect_error(lambda: an.save({"title": "x", "body": "y"}), frappe.PermissionError)
            frappe.set_user(f["hr"])
            dept = frappe.db.get_value("Employee", f["e_emp"], "department")
            an.save({"title": "Eid holiday", "body": "Office closed", "audience": "Everyone", "pinned": 1})
            an.save({"title": "Ops only", "body": "Shift change", "audience": "Department", "department": dept})
            an.save({"title": "Future", "body": "Later", "publish_on": add_days(nowdate(), 5)})
            expect_error(lambda: an.save({"title": "Bad", "body": "x", "audience": "Department"}), frappe.ValidationError)
            frappe.set_user(f["emp"])
            titles = [a["title"] for a in an.active()]
            assert titles[0] == "Eid holiday" and "Ops only" in titles and "Future" not in titles, titles
            frappe.db.set_value("Employee", f["e_emp2"], "department", None)
            frappe.set_user(f["emp2"])
            assert "Ops only" not in [a["title"] for a in an.active()]
            frappe.set_user(f["emp"])
            acts = ess.my_activity()
            assert acts and {"kind", "title", "at", "link"} <= set(acts[0]), acts[:1]
        check("home: HR announcements by audience and date, recent activity", home_announcements_activity)

        def print_images_check():
            from alphax_hr.api import setup
            frappe.set_user("Administrator")
            name = "AXT Broken Logo"
            if not frappe.db.exists("Letter Head", name):
                frappe.get_doc({"doctype": "Letter Head", "letter_head_name": name, "source": "HTML",
                                "content": '<img src="/files/axt-missing-logo.png">'}).insert(ignore_permissions=True)
            try:
                frappe.set_user(f["hr"])
                b = [x for x in setup.broken_print_images() if x["url"] == "/files/axt-missing-logo.png"]
                assert b and name in b[0]["where"], setup.broken_print_images()
                chk = next(c for c in setup.hr_status()["checks"] if c["key"] == "print_images")
                assert chk["status"] == "warn" and "axt-missing-logo" in chk["detail"]
            finally:
                frappe.set_user("Administrator")
                frappe.delete_doc("Letter Head", name, ignore_permissions=True, force=1)
        check("HR status finds letter-head / payslip images that point to missing files", print_images_check)

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
