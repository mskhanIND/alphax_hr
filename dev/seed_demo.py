"""Seed realistic (fictional) demo data on the test site for the AlphaX HR walkthrough."""
import random
import sys

import frappe
from frappe.utils import add_days, add_months, get_first_day, get_last_day, nowdate

COMPANY, ABBR = "AlphaX Test Co", "AXT"
random.seed(7)
frappe.init(site="hr.test", sites_path="/home/claude/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")


def ensure(dt, filters, values=None, submit=False):
    name = frappe.db.exists(dt, filters)
    if name:
        return frappe.get_doc(dt, name)
    doc = frappe.get_doc({"doctype": dt, **filters, **(values or {})}).insert(ignore_permissions=True)
    if submit:
        doc.submit()
    return doc


depts = {}
for d in ("Human Resources", "Finance", "Operations", "Sales", "IT"):
    depts[d] = ensure("Department", {"department_name": d, "company": COMPANY}).name
for d in ("HR Manager", "Accountant", "Operations Supervisor", "Sales Executive", "Software Engineer",
          "Site Engineer", "Driver", "Customer Service Agent"):
    ensure("Designation", {"designation_name": d})

# Give the existing fixture users nicer roles in the story
frappe.db.set_value("Employee", {"user_id": "hr@axt.test"}, {"department": depts["Human Resources"], "designation": "HR Manager"})
frappe.db.set_value("Employee", {"user_id": "mgr@axt.test"}, {"department": depts["Operations"], "designation": "Operations Supervisor"})
frappe.db.set_value("Employee", {"user_id": "emp@axt.test"}, {"department": depts["Operations"], "designation": "Site Engineer", "reports_to": frappe.db.get_value("Employee", {"user_id": "mgr@axt.test"})})
frappe.db.set_value("Employee", {"user_id": "emp2@axt.test"}, {"department": depts["Sales"], "designation": "Sales Executive"})

hl = frappe.db.get_value("Holiday List", {"holiday_list_name": ["like", "AXT%"]})
mgr_emp = frappe.db.get_value("Employee", {"user_id": "mgr@axt.test"})
people = [
    ("Abdullah", "Al-Qahtani", "Male", 1, "Finance", "Accountant", "2019-03-10", "2019-03-01", 14000),
    ("Sara", "Al-Otaibi", "Female", 1, "Human Resources", "HR Manager", "2024-09-15", "2024-09-15", 12000),
    ("Faisal", "Al-Harbi", "Male", 1, "Sales", "Sales Executive", "2025-02-01", "2025-02-01", 9000),
    ("Noura", "Al-Shehri", "Female", 1, "IT", "Software Engineer", "2022-06-01", "2016-08-01", 16000),
    ("Turki", "Al-Dossary", "Male", 1, "Operations", "Operations Supervisor", "2026-01-12", None, 3500),
    ("Ahmed", "Hassan", "Male", 0, "Operations", "Site Engineer", "2018-01-07", None, 11000),
    ("Ravi", "Kumar", "Male", 0, "IT", "Software Engineer", "2021-04-18", None, 13000),
    ("Maria", "Santos", "Female", 0, "Sales", "Customer Service Agent", "2023-11-05", None, 6000),
    ("Imran", "Ali", "Male", 0, "Operations", "Driver", "2017-05-20", None, 4500),
    ("Khaled", "Mahmoud", "Male", 0, "Finance", "Accountant", "2020-10-01", None, 10500),
    ("Joseph", "Mathew", "Male", 0, "Operations", "Site Engineer", "2024-03-03", None, 9500),
    ("Fatima", "Zahra", "Female", 0, "Human Resources", "HR Manager", "2022-12-12", None, 8500),
]
iqama_offsets = [-12, 9, 21, 45, 75, 200, None]
created = []
for i, (fn, ln, g, saudi, dept, desig, doj, gosi_reg, wage) in enumerate(people):
    name = frappe.db.get_value("Employee", {"first_name": fn, "last_name": ln, "company": COMPANY})
    if not name:
        off = iqama_offsets[i % len(iqama_offsets)] if not saudi else None
        doc = frappe.get_doc({
            "doctype": "Employee", "first_name": fn, "last_name": ln, "gender": g, "company": COMPANY,
            "date_of_birth": f"{1980 + i}-0{1 + i % 9}-1{i % 9}", "date_of_joining": doj, "status": "Active",
            "department": depts[dept], "designation": desig, "holiday_list": hl if i % 5 else None,
            "leave_approver": "mgr@axt.test" if i % 4 else None, "reports_to": mgr_emp if dept == "Operations" else None,
            "alphax_is_saudi": saudi, "alphax_gosi_registration_date": gosi_reg,
            "alphax_iqama_number": None if saudi else f"2{random.randint(100000000, 999999999)}",
            "alphax_iqama_expiry": add_days(nowdate(), off) if off is not None else None,
            "alphax_work_permit_expiry": add_days(nowdate(), off + 5) if off is not None else None,
            "contract_end_date": add_days(nowdate(), 40) if i == 2 else None,
            "cell_number": f"05{random.randint(10000000, 99999999)}",
        }).insert(ignore_permissions=True)
        name = doc.name
    created.append((name, wage))

# ---- Payroll: components, structure, assignments, October slips -------------
def account(name, parent_like, root):
    acc = frappe.db.get_value("Account", {"account_name": name, "company": COMPANY})
    if acc:
        return acc
    parent = frappe.db.get_value("Account", {"company": COMPANY, "is_group": 1, "root_type": root, "account_name": ["like", parent_like]})
    return frappe.get_doc({"doctype": "Account", "account_name": name, "company": COMPANY, "parent_account": parent}).insert(ignore_permissions=True).name

payable = account("Payroll Payable", "%Current Liabilities%", "Liability")
frappe.db.set_value("Company", COMPANY, "default_payroll_payable_account", payable)
for comp, abbr in (("Basic", "B"), ("Housing Allowance", "HA"), ("Transport Allowance", "TA")):
    ensure("Salary Component", {"salary_component": comp}, {"salary_component_abbr": abbr, "type": "Earning"})
ensure("Salary Component", {"salary_component": "GOSI Employee"}, {"salary_component_abbr": "GOSI", "type": "Deduction", "depends_on_payment_days": 0})

ss_name = "AXT Standard"
if not frappe.db.exists("Salary Structure", ss_name):
    ss = frappe.get_doc({
        "doctype": "Salary Structure", "name": ss_name, "__newname": ss_name, "company": COMPANY, "is_active": "Yes",
        "payroll_frequency": "Monthly", "currency": "SAR", "salary_slip_based_on_timesheet": 0,
        "earnings": [
            {"salary_component": "Basic", "abbr": "B", "amount_based_on_formula": 1, "formula": "base"},
            {"salary_component": "Housing Allowance", "abbr": "HA", "amount_based_on_formula": 1, "formula": "base * 0.25"},
            {"salary_component": "Transport Allowance", "abbr": "TA", "amount_based_on_formula": 1, "formula": "base * 0.10"},
        ],
        "deductions": [{"salary_component": "GOSI Employee", "abbr": "GOSI", "amount_based_on_formula": 1, "formula": "(B + HA) * 0.0975"}],
    })
    ss.insert(ignore_permissions=True)
    ss.submit()

frappe.db.commit()
all_emps = frappe.get_all("Employee", filters={"company": COMPANY, "status": "Active"}, fields=["name", "date_of_joining", "employee_name"])
wages = dict(created)
for e in all_emps:
    base = wages.get(e.name, 10000)
    if not frappe.db.exists("Salary Structure Assignment", {"employee": e.name, "docstatus": 1}):
        frappe.get_doc({"doctype": "Salary Structure Assignment", "employee": e.name, "salary_structure": ss_name,
                        "company": COMPANY, "from_date": max(str(e.date_of_joining), "2026-01-01"), "base": base,
                        "payroll_payable_account": payable, "currency": "SAR"}).insert(ignore_permissions=True).submit()
frappe.db.commit()

for fy_year in (year_now := int(nowdate()[:4]), year_now + 1):
    fy = ensure("Fiscal Year", {"year": str(fy_year)}, {"year_start_date": f"{fy_year}-01-01", "year_end_date": f"{fy_year}-12-31"})
    if not any(c.company == COMPANY for c in fy.get("companies", [])):
        fy.append("companies", {"company": COMPANY})
        fy.save(ignore_permissions=True)
frappe.db.commit()
oct_start = get_first_day(add_months(nowdate(), -1))
for e in all_emps:
    if frappe.db.exists("Salary Slip", {"employee": e.name, "start_date": oct_start, "docstatus": 1}):
        continue
    frappe.db.savepoint("slip")
    try:
        slip = frappe.get_doc({"doctype": "Salary Slip", "employee": e.name, "employee_name": e.employee_name,
                               "date_of_joining": e.date_of_joining, "start_date": oct_start,
                               "end_date": get_last_day(oct_start), "posting_date": get_last_day(oct_start),
                               "payroll_frequency": "Monthly", "company": COMPANY})
        slip.insert(ignore_permissions=True)
        slip.submit()
    except Exception as ex:  # noqa: BLE001
        print("slip skipped", e.name, str(ex)[:120])
        frappe.db.rollback(save_point="slip")
frappe.db.commit()

frappe.db.commit()
settings = frappe.get_single("AlphaX HR Settings")
settings.default_company = COMPANY
settings.nitaqat_target_percent = 35
settings.set("component_map", [])
for comp, purpose in (("Basic", "GOSI Basic"), ("Housing Allowance", "GOSI Housing"), ("Basic", "EOSB Wage"),
                      ("Housing Allowance", "EOSB Wage"), ("Transport Allowance", "EOSB Wage"), ("Basic", "Nitaqat Wage")):
    settings.append("component_map", {"salary_component": comp, "purpose": purpose})
settings.save(ignore_permissions=True)

# ---- Leave: allocations + pending requests for the manager's inbox ----------
lt = "AXT Annual"
year = int(nowdate()[:4])
for e in all_emps:
    if not frappe.db.exists("Leave Allocation", {"employee": e.name, "leave_type": lt, "docstatus": 1}):
        frappe.db.savepoint("alloc")
        try:
            frappe.get_doc({"doctype": "Leave Allocation", "employee": e.name, "leave_type": lt,
                            "from_date": f"{year}-01-01", "to_date": f"{year}-12-31",
                            "new_leaves_allocated": random.choice([21, 21, 30])}).insert(ignore_permissions=True).submit()
        except Exception as ex:  # noqa: BLE001
            print("alloc skipped", e.name, str(ex)[:100])
            frappe.db.rollback(save_point="alloc")

reasons = ["Family visit to Abha", "Umrah", "Child's school event", "Medical appointment", "Wedding in Jeddah"]
pending = 0
for i, (name, _w) in enumerate(created):
    if frappe.db.get_value("Employee", name, "leave_approver") != "mgr@axt.test":
        continue
    if frappe.db.exists("Leave Application", {"employee": name, "docstatus": 0}):
        pending += 1
        continue
    start = add_days(nowdate(), 7 + i * 3)
    while frappe.utils.getdate(start).weekday() == 4:
        start = add_days(start, 1)
    frappe.db.savepoint("leave_sp")
    try:
        frappe.get_doc({"doctype": "Leave Application", "employee": name, "leave_type": lt, "company": COMPANY,
                        "from_date": start, "to_date": add_days(start, 1 + i % 3), "posting_date": nowdate(),
                        "leave_approver": "mgr@axt.test", "description": reasons[i % len(reasons)],
                        "status": "Open"}).insert(ignore_permissions=True)
        pending += 1
    except Exception as ex:  # noqa: BLE001
        print("leave skipped", name, str(ex)[:100])
        frappe.db.rollback(save_point="leave_sp")

# Attendance history for Eman (the employee persona) for a nicer calendar
eman = frappe.db.get_value("Employee", {"user_id": "emp@axt.test"})
d = get_first_day(nowdate())
while str(d) < nowdate():
    if frappe.utils.getdate(d).weekday() not in (4, 5) and not frappe.db.exists("Attendance", {"employee": eman, "attendance_date": d}):
        status = "Present" if random.random() > 0.08 else "Absent"
        att = frappe.get_doc({"doctype": "Attendance", "employee": eman, "attendance_date": d, "status": status,
                              "company": COMPANY, "late_entry": 1 if status == "Present" and random.random() < 0.2 else 0,
                              "working_hours": round(random.uniform(7.5, 9.2), 2) if status == "Present" else 0})
        att.insert(ignore_permissions=True)
        att.submit()
    d = add_days(d, 1)
for m in range(1, 3):
    ms = get_first_day(add_months(nowdate(), -m))
    d = ms
    while d <= get_last_day(ms):
        if frappe.utils.getdate(d).weekday() not in (4, 5) and not frappe.db.exists("Attendance", {"employee": eman, "attendance_date": d}):
            frappe.get_doc({"doctype": "Attendance", "employee": eman, "attendance_date": d, "status": "Present",
                            "company": COMPANY, "working_hours": 8.5}).insert(ignore_permissions=True).submit()
        d = add_days(d, 1)

frappe.db.commit()
print("employees", len(all_emps), "pending leaves", pending,
      "slips", frappe.db.count("Salary Slip", {"start_date": oct_start, "docstatus": 1}))
frappe.destroy()
