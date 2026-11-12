app_name = "alphax_hr"
app_title = "AlphaX HR"
app_publisher = "Neotec Integrated Solutions"
app_description = "AlphaX HR — a modern Saudi HR experience on Frappe HRMS and ERPNext"
app_email = "support@neotec.ai"
app_license = "MIT"

# Frappe HRMS + ERPNext remain the system of record. This app never duplicates
# their data: it adds an API layer, Saudi rules and the /hr web experience.
required_apps = ["erpnext", "hrms"]

add_to_apps_screen = [
	{
		"name": "alphax_hr",
		"logo": "/assets/alphax_hr/frontend/logo.svg",
		"title": "AlphaX HR",
		"route": "/alphax",
		"has_permission": "alphax_hr.api.session.has_app_permission",
	}
]

website_route_rules = [
	{"from_route": "/alphax/<path:app_path>", "to_route": "alphax"},
	{"from_route": "/alphax-login", "to_route": "alphax_login"},
]

after_install = "alphax_hr.install.after_install"
before_migrate = "alphax_hr.install.before_migrate"
after_migrate = "alphax_hr.install.after_migrate"

doc_events = {
	"Employee": {"validate": ["alphax_hr.employee_rules.validate", "alphax_hr.saudization.validate_employee"],
				 "on_update": "alphax_hr.logins.on_employee_saved"},
	"Holiday List": {"on_update": "alphax_hr.week_off.sync_public_holidays"},
	"Leave Type": {
		"before_rename": "alphax_hr.leave_engine.block_rename",
		"on_trash": "alphax_hr.leave_engine.block_delete",
	},
	"Leave Application": {
		"validate": "alphax_hr.leave_engine.validate_leave_application",
		"before_submit": "alphax_hr.leave_engine.before_submit_leave_application",
		"after_insert": ["alphax_hr.approval_policy.on_leave_insert", "alphax_hr.api.notify.on_leave_insert"],
		"on_submit": "alphax_hr.api.notify.on_leave_decided",
		"on_cancel": "alphax_hr.approval_policy.on_leave_cancel",
		"on_trash": "alphax_hr.approval_policy.on_leave_cancel",
	},
	"Attendance Request": {"validate": "alphax_hr.request_rules.validate_attendance_request"},
	"Notification Log": {"after_insert": "alphax_hr.api.notify.on_notification_log"},
	"Employee Checkin": {"after_insert": "alphax_hr.api.notify.on_checkin"},
	"Shift Assignment": {"on_submit": "alphax_hr.devices.on_shift_assignment"},
}

scheduler_events = {
	"daily": [
		"alphax_hr.tasks.notify_expiring_documents",
		"alphax_hr.leave_engine.daily_annual_allocation",
		"alphax_hr.api.notify.daily_announcements",
		"alphax_hr.api.loans.daily_post_due",
		"alphax_hr.api.requests.accept_overdue_resignations",
		"alphax_hr.absence_warnings.daily",
		"alphax_hr.probation.daily",
	],
	"hourly": ["alphax_hr.api.delays.escalate_pending_approvals"],
	"cron": {"*/15 * * * *": ["alphax_hr.api.alerts.missing_checkins"], "*/5 * * * *": ["alphax_hr.devices.scheduled"],
			 "30 1 * * *": ["alphax_hr.attendance_marking.daily"]},
}

permission_query_conditions = {"AlphaX Request": "alphax_hr.api.requests.query_conditions",
							   "AlphaX Penalty": "alphax_hr.api.penalties.query_conditions",
							   "AlphaX Leave Plan": "alphax_hr.api.leave_plan.query_conditions"}
has_permission = {"AlphaX Request": "alphax_hr.api.requests.has_permission",
				  "AlphaX Penalty": "alphax_hr.api.penalties.has_permission",
				  "AlphaX Leave Plan": "alphax_hr.api.leave_plan.has_permission"}

# Delivery records never stop a request from being deleted or cancelled.
ignore_links_on_delete = ["AlphaX Approval Reminder"]

after_request = ["alphax_hr.api.pwa.after_request", "alphax_hr.portal.after_request"]

# ZKTeco ADMS / iClock push: /iclock/cdata, /iclock/getrequest, /iclock/devicecmd (plain text for the device firmware)
page_renderer = ["alphax_hr.adms.ADMSRenderer"]

jinja = {"methods": ["alphax_hr.api.payslip.alphax_payslip"]}
