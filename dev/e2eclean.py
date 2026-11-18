import frappe
def run():
    for n in frappe.get_all("AlphaX Request", filters={"request_type": ["like", "%Permission%"], "employee": "HR-EMP-00004"}, pluck="name"):
        frappe.delete_doc("AlphaX Request", n, force=True, ignore_permissions=True)
    for n in frappe.get_all("AlphaX Attendance Device", filters={"device_name": ["like", "E2E Gate%"]}, pluck="name"):
        frappe.delete_doc("AlphaX Attendance Device", n, force=True)
    for n in frappe.get_all("AlphaX Approval Policy", filters={"policy_name": ["like", "E2E Policy%"]}, pluck="name"):
        frappe.delete_doc("AlphaX Approval Policy", n, force=True)
    frappe.db.commit()
