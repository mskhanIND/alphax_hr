// Thin client for Frappe whitelisted methods (same-origin, session cookie + CSRF).

export interface Boot {
  user: string
  csrf_token: string
  lang: 'en' | 'ar'
  title: string
  version: string
  site: string
}

declare global {
  interface Window {
    ALPHAX_BOOT?: Boot
  }
}

export const boot: Boot = (typeof window !== 'undefined' && window.ALPHAX_BOOT) || {
  user: 'dev',
  csrf_token: '',
  lang: 'en',
  title: 'AlphaX HR (dev)',
  version: 'dev',
  site: 'dev',
}

export interface LeaveRule {
  kind: string
  max_days: number | null
  gender: string | null
  requires_event_date: boolean
  event_label: string | null
  relations: string[]
  requires_attachment: boolean
  min_service_days: number | null
  lifetime_limit: number | null
}
export interface LeaveTypeOption { leave_type: string; rule: LeaveRule | null }

export class ApiError extends Error {
  status: number
  type?: string
  constructor(message: string, status: number, type?: string) {
    super(message)
    this.status = status
    this.type = type
  }
}

function stripHtml(s: string) {
  return s.replace(/<[^>]+>/g, ' ').replace(/[ \t]+/g, ' ').replace(/ *\n */g, '\n').trim()
}

/** Turn a Frappe error response into one human message. */
export function extractError(body: any, status: number): ApiError {
  let message = ''
  try {
    if (body?._server_messages) {
      const msgs: string[] = JSON.parse(body._server_messages)
      message = msgs
        .map((m) => {
          try {
            return JSON.parse(m).message
          } catch {
            return m
          }
        })
        .join('\n')
    }
  } catch {
    /* ignore */
  }
  if (!message && body?.exception) message = String(body.exception).split(':').slice(1).join(':') || body.exception
  if (!message) message = status === 403 ? 'You do not have permission for this.' : `Request failed (${status})`
  return new ApiError(stripHtml(message), status, body?.exc_type)
}

export async function call<T = any>(method: string, args: Record<string, unknown> = {}): Promise<T> {
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'X-Frappe-CSRF-Token': boot.csrf_token,
    },
    body: JSON.stringify(args),
  })
  let body: any = null
  try {
    body = await res.json()
  } catch {
    /* non-JSON */
  }
  if (res.status === 401 || (res.status === 403 && body?.exc_type === 'AuthenticationError')) {
    window.location.href = '/login?redirect-to=' + encodeURIComponent(window.location.pathname)
  }
  if (!res.ok) throw extractError(body, res.status)
  return body?.message as T
}

const A = 'alphax_hr.api.'
export const api = {
  boot: () => call(A + 'session.boot'),
  setLanguage: (lang: string) => call(A + 'session.set_language', { lang }),
  // self-service
  profile: () => call(A + 'ess.my_profile'),
  updateContact: (data: Record<string, unknown>) => call(A + 'ess.update_my_contact', { data }),
  balances: () => call(A + 'ess.my_leave_balances'),
  myLeaves: () => call(A + 'ess.my_leave_applications'),
  leaveTypes: () => call<LeaveTypeOption[]>(A + 'ess.leave_types'),
  applyLeave: (args: Record<string, unknown>) => call(A + 'ess.apply_leave', args),
  withdrawLeave: (name: string) => call(A + 'ess.withdraw_leave', { name }),
  myAttendance: (month: string) => call(A + 'ess.my_attendance', { month }),
  shiftTypes: () => call<any[]>(A + 'ess.shift_types'),
  requestShift: (args: Record<string, unknown>) => call(A + 'ess.request_shift', args),
  requestAttendance: (args: Record<string, unknown>) => call(A + 'ess.request_attendance', args),
  myRequests: () => call<any[]>(A + 'ess.my_requests'),
  activity: (doctype: string, name: string) => call(A + 'approvals.activity', { doctype, name }),
  decided: () => call(A + 'approvals.decided'),
  health: () => call(A + 'setup.health'),
  hrStatus: () => call(A + 'setup.hr_status'),
  affected: (key: string) => call(A + 'setup.affected', { key }),
  bulkFix: (key: string, employees: string[], value: string) => call(A + 'setup.bulk_fix', { key, employees, value }),
  allowStatutory: () => call(A + 'setup.allow_statutory_without_allocation'),
  contractHtml: (employee: string) => call(A + 'contract.preview', { employee }),
  saveContract: (employee: string) => call(A + 'contract.save', { employee }),
  record: (doctype: string, name: string) => call(A + 'records.get', { doctype, name }),
  fieldMap: () => call(A + 'hr.field_map'),
  linkField: (site_field: string, same_as?: string) => call(A + 'hr.link_field', { site_field, same_as }),
  salaryConfig: (company?: string) => call(A + 'salary.config', company ? { company } : {}),
  salaryPreview: (args: Record<string, unknown>) => call(A + 'salary.preview', args),
  setSalary: (employee: string, pkg: Record<string, unknown>, from_date: string) => call(A + 'salary.set_salary', { employee, package: pkg, from_date }),
  currentSalary: (employee: string) => call(A + 'salary.current', { employee }),
  getSettings: () => call(A + 'setup.get_settings'),
  saveSettings: (data: Record<string, unknown>) => call(A + 'setup.save_settings', { data }),
  trail: (doctype: string, name: string) => call(A + 'activity.trail', { doctype, name }),
  activityFeed: (args: Record<string, unknown>) => call(A + 'activity.feed', args),
  leaveSummary: (employee?: string) => call(A + 'leave_ledger.summary', employee ? { employee } : {}),
  leaveWorkforce: (args: Record<string, unknown>) => call(A + 'leave_ledger.workforce', args),
  roster: (args: Record<string, unknown>) => call(A + 'shifts.roster', args),
  assignShift: (args: Record<string, unknown>) => call(A + 'shifts.assign', args),
  setWeekOff: (args: Record<string, unknown>) => call(A + 'shifts.set_week_off', args),
  toggleWeekOff: (employee: string, date: string) => call(A + 'shifts.toggle_week_off', { employee, date }),
  endAssignment: (name: string, end_date?: string) => call(A + 'shifts.end_assignment', { name, end_date }),
  attendanceRegister: (args: Record<string, unknown>) => call(A + 'attendance.register', args),
  overtime: (args: Record<string, unknown>) => call(A + 'attendance.overtime', args),
  todayStatus: () => call(A + 'ess.today_status'),
  checkIn: (log_type: 'IN' | 'OUT', latitude?: number, longitude?: number) =>
    call(A + 'ess.check_in', { log_type, latitude, longitude }),
  payslips: () => call(A + 'ess.my_payslips'),
  payslip: (name: string) => call(A + 'ess.payslip', { name }),
  holidays: () => call(A + 'ess.upcoming_holidays'),
  expenses: () => call(A + 'ess.my_expense_claims'),
  // approvals
  inbox: () => call(A + 'approvals.inbox'),
  act: (doctype: string, name: string, action: string, comment?: string) =>
    call(A + 'approvals.act', { doctype, name, action, comment }),
  teamCalendar: (start: string, end: string) => call(A + 'approvals.team_leave_calendar', { start, end }),
  // hr
  employees: (args: Record<string, unknown>) => call(A + 'hr.employees', args),
  employee: (name: string) => call(A + 'hr.employee', { name }),
  updateEmployee: (name: string, data: Record<string, unknown>, modified: string) =>
    call(A + 'hr.update_employee', { name, data, modified }),
  createEmployee: (data: Record<string, unknown>) => call(A + 'hr.create_employee', { data }),
  newEmployeeForm: () => call(A + 'hr.new_employee_form'),
  checkNewEmployee: (data: Record<string, unknown>) => call<{ missing: any[] }>(A + 'hr.check_new_employee', { data }),
  lookup: (doctype: string, txt: string) => call<{ value: string; description?: string; label?: string }[]>(A + 'hr.lookup', { doctype, txt }),
  orgSummary: () => call(A + 'hr.org_summary'),
  setPhoto: (name: string, file_url: string) => call(A + 'hr.set_photo', { name, file_url }),
  orgChart: (args: Record<string, unknown> = {}) => call(A + 'hr.org_chart', args),
  // payroll & compliance
  payrollRuns: (year: number, month?: string) => call(A + 'payroll.payroll_runs', month ? { month } : { year }),
  slipSummary: (month: string) => call(A + 'payroll.slip_summary', { month }),
  gosiRegister: (month: string) => call(A + 'payroll.gosi_register', { month }),
  eosb: (args: Record<string, unknown>) => call(A + 'payroll.eosb', args),
  compliance: () => call(A + 'compliance.overview'),
  leaveSetup: () => call(A + 'leave_setup.overview'),
  createStatutoryLeaveTypes: () => call(A + 'leave_setup.create_statutory_leave_types'),
  allowWithoutAllocation: (leave_type: string) => call(A + 'leave_setup.allow_without_allocation', { leave_type }),
  updateLeaveRule: (name: string, data: Record<string, unknown>) => call(A + 'leave_setup.update_rule', { name, data }),
  setupAnnualLeaveType: () => call(A + 'leave_setup.setup_annual_leave_type'),
  updateAnnualSettings: (data: Record<string, unknown>) => call(A + 'leave_setup.update_annual_settings', { data }),
  alertSettings: () => call<any>(A + 'alerts.settings'),
  saveAlertSettings: (rules: any[]) => call<any>(A + 'alerts.save_settings', { rules }),
  myNotifications: () => call<{ items: any[]; unread: number }>(A + 'alerts.inbox'),
  markNotificationsRead: (name?: string) => call<{ items: any[]; unread: number }>(A + 'alerts.mark_read', name ? { name } : {}),
  approvalDelays: () => call<any>(A + 'delays.report'),
  countingRules: () => call<any>(A + 'leave_setup.counting_rules'),
  saveCountingRule: (data: Record<string, unknown>) => call(A + 'leave_setup.save_counting_rule', { data }),
  deleteCountingRule: (name: string) => call(A + 'leave_setup.delete_counting_rule', { name }),
  leaveDays: (args: Record<string, unknown>) => call<{ days: number | null; text?: string | null; policy: boolean; must_start_working_day?: boolean; emergency?: boolean; min_notice_days?: number | null; max_days?: number | null }>(A + 'ess.leave_days', args),
  annualAllocation: (apply = 0) => call(A + 'leave_setup.annual_allocation', { apply }),
  expiring: (days: number) => call(A + 'compliance.expiring_documents', { days }),
  // employee requests
  requestTypes: (include_disabled = 0) => call<RequestType[]>(A + 'requests.types', { include_disabled }),
  createRequest: (request_type: string, details: Record<string, unknown>, reason?: string, employee?: string) =>
    call<{ name: string; status: string }>(A + 'requests.create', { request_type, details, reason, employee }),
  myAlphaxRequests: () => call<any[]>(A + 'requests.mine'),
  cancelRequest: (name: string) => call(A + 'requests.cancel', { name }),
  allRequests: (args: Record<string, unknown>) => call<{ rows: any[]; counts: Record<string, number> }>(A + 'requests.all_requests', args),
  updateRequestType: (name: string, data: Record<string, unknown>) => call<RequestType>(A + 'requests.update_type', { name, data }),
  // penalties
  violationTypes: (include_disabled = 0) => call<any[]>(A + 'penalties.violation_types', { include_disabled }),
  saveViolationType: (name: string, data: Record<string, unknown>) => call(A + 'penalties.save_violation_type', { name, data }),
  penaltyPreview: (args: Record<string, unknown>) => call<any>(A + 'penalties.preview', args),
  createPenalty: (args: Record<string, unknown>) => call<any>(A + 'penalties.create', args),
  issuePenalty: (name: string) => call<any>(A + 'penalties.issue_penalty', { name }),
  cancelPenalty: (name: string, reason: string) => call<any>(A + 'penalties.cancel_penalty', { name, reason }),
  penalties: (args: Record<string, unknown>) => call<any[]>(A + 'penalties.penalties', args),
  penaltySuggestions: (month: string) => call<any[]>(A + 'penalties.suggestions', { month }),
  myPenalties: () => call<any[]>(A + 'penalties.mine'),
  respondPenalty: (name: string, action: string, reply?: string) => call<any>(A + 'penalties.respond', { name, action, reply }),
  // payroll control & final settlement
  payrollCompanies: () => call<string[]>(A + 'payroll_control.companies'),
  payrollPeriod: (company: string, month: string) => call<any>(A + 'payroll_control.period', { company, month }),
  payrollAdvance: (company: string, month: string, step: string, note?: string, override = 0) =>
    call<any>(A + 'payroll_control.advance', { company, month, step, note, override }),
  payrollSubmitSlips: (company: string, month: string) => call<any>(A + 'payroll_control.submit_slips', { company, month }),
  payrollAddOvertime: (company: string, month: string) => call<any>(A + 'payroll_control.add_overtime', { company, month }),
  settlements: (status?: string) => call<any[]>(A + 'settlements.settlements', { status }),
  prepareSettlement: (args: Record<string, unknown>) => call<any>(A + 'settlements.prepare', args),
  approveSettlement: (name: string) => call<any>(A + 'settlements.approve', { name }),
  paySettlement: (name: string, paid_on?: string) => call<any>(A + 'settlements.mark_paid', { name, paid_on }),
  cancelSettlement: (name: string, reason: string) => call<any>(A + 'settlements.cancel', { name, reason }),
  // appraisals & cut-over
  appraisalCycles: () => call<any>(A + 'appraisals.cycles'),
  appraisals: (cycle?: string) => call<any[]>(A + 'appraisals.appraisals', { cycle }),
  myAppraisals: () => call<any[]>(A + 'appraisals.mine'),
  leaveForm: () => call<{ fields: any[]; auto: { fieldname: string; label: string; kind: string }[] }>(A + 'ess.leave_form'),
  essLookup: (doctype: string, txt: string) => call<{ value: string; description?: string; label?: string }[]>(A + 'ess.lookup', { doctype, txt }),
  attendancePolicies: () => call<any[]>(A + 'attendance_policy.policies'),
  saveAttendancePolicy: (data: Record<string, unknown>, name?: string) => call<any>(A + 'attendance_policy.save', { data, name }),
  deleteAttendancePolicy: (name: string) => call(A + 'attendance_policy.delete', { name }),
  myAttendancePolicy: () => call<any>(A + 'attendance_policy.my_policy'),
  myVacationPlan: (year?: number) => call<any>(A + 'leave_plan.my_plan', { year }),
  saveVacationPlan: (year: number, periods: any[]) => call<any>(A + 'leave_plan.save_my_plan', { year, periods }),
  submitVacationPlan: (year: number) => call<any>(A + 'leave_plan.submit_my_plan', { year }),
  applyPlannedPeriod: (year: number, idx: number) => call<any>(A + 'leave_plan.apply_period', { year, idx }),
  vacationPlanner: (year?: number, department?: string) => call<any>(A + 'leave_plan.planner', { year, department }),
  createMissingLinks: () => call<{ created: string[]; skipped: string[] }>(A + 'setup.create_missing_links'),
  profileChangeForm: () => call<any>(A + 'ess.profile_change_form'),
  requestProfileChange: (changes: Record<string, string>, reason?: string) => call<any>(A + 'ess.request_profile_change', { changes, reason }),
  myActivity: () => call<any[]>(A + 'ess.my_activity'),
  requestMessages: (name: string) => call<any[]>(A + 'requests.messages', { name }),
  postRequestMessage: (name: string, text: string) => call<any[]>(A + 'requests.post_message', { name, text }),
  announcements: () => call<any[]>(A + 'announcements.active'),
  allAnnouncements: () => call<any[]>(A + 'announcements.all_announcements'),
  saveAnnouncement: (data: Record<string, unknown>, name?: string) => call<any>(A + 'announcements.save', { data, name }),
  deleteAnnouncement: (name: string) => call(A + 'announcements.delete', { name }),
  latestSlip: () => call<string | null>(A + 'payslip.latest_slip'),
  payslipPreview: (name: string) => call<{ html: string }>(A + 'payslip.preview', { name }),
  installPayslipFormat: () => call(A + 'payslip.install_print_format', { make_default: 1 }),
  liveCheckins: (date?: string, department?: string) => call<any>(A + 'attendance.live', { date, department }),
  workLocations: () => call<any[]>(A + 'attendance.work_locations'),
  saveWorkLocation: (data: Record<string, unknown>, name?: string) => call(A + 'attendance.save_work_location', { data, name }),
  deleteWorkLocation: (name: string) => call(A + 'attendance.delete_work_location', { name }),
  helpArticles: (search?: string, category?: string) => call<any>(A + 'knowledge.articles', { search, category }),
  helpArticle: (name: string) => call<any>(A + 'knowledge.article', { name }),
  helpFeedback: (name: string, helpful: number) => call(A + 'knowledge.feedback', { name, helpful }),
  allHelpArticles: () => call<any[]>(A + 'knowledge.all_articles'),
  saveHelpArticle: (data: Record<string, unknown>, name?: string) => call(A + 'knowledge.save', { data, name }),
  deleteHelpArticle: (name: string) => call(A + 'knowledge.delete', { name }),
  payrollSlips: (company: string, month: string) => call<any>(A + 'payroll_control.slips', { company, month }),
  recalcSlip: (name: string) => call(A + 'payroll_control.recalculate_slip', { name }),
  removeSlip: (name: string, reason: string) => call(A + 'payroll_control.remove_slip', { name, reason }),
  addSlipEmployee: (company: string, month: string, employee: string) => call(A + 'payroll_control.add_employee', { company, month, employee }),
  adjustPay: (args: Record<string, unknown>) => call(A + 'payroll_control.adjust', args),
  redoSlip: (name: string, reason: string) => call(A + 'payroll_control.redo_slip', { name, reason }),
  salaryComponents: () => call<any[]>(A + 'payroll_control.components'),
  expenseTypes: () => call<any[]>(A + 'ess.expense_types'),
  submitExpense: (args: Record<string, unknown>) => call<{ name: string; approver?: string }>(A + 'ess.submit_expense', args),
  withdrawExpense: (name: string) => call(A + 'ess.withdraw_expense', { name }),
  myDocuments: () => call<any>(A + 'ess.my_documents'),
  myTeam: () => call<any>(A + 'ess.my_team'),
  cutoverReadiness: () => call<any>(A + 'cutover.readiness'),
  importLegacy: (kind: string, dry_run: number) => call<any>(A + 'cutover.import_legacy', { kind, dry_run }),
}

export interface RequestField { fieldname: string; label: string; label_ar?: string; type: string; reqd?: number; options?: string[] }
export interface RequestType {
  name: string; title: string; title_ar?: string; category: string; description?: string; needs_manager: number; needs_hr: number
  requires_attachment: number; non_saudi_only: number; sla_days: number; output?: string; enabled: number; fields: RequestField[]; special?: boolean
}

/** Attach a file to a document through Frappe's standard (permission-checked) upload. */
export async function uploadFile(doctype: string, docname: string, file: File, isPrivate = true) {
  const form = new FormData()
  form.append('file', file, file.name)
  if (doctype && docname) {  // without them the file is uploaded unattached (attached when the record is created)
    form.append('doctype', doctype)
    form.append('docname', docname)
  }
  form.append('is_private', isPrivate ? '1' : '0')
  const res = await fetch('/api/method/upload_file', {
    method: 'POST', credentials: 'same-origin', headers: { 'X-Frappe-CSRF-Token': boot.csrf_token }, body: form,
  })
  let body: any = null
  try { body = await res.json() } catch { /* non-JSON */ }
  if (!res.ok) throw extractError(body, res.status)
  return body?.message
}

/** Browser download of a whitelisted method that returns a file (GET keeps it a normal download). */
/** Download a file without leaving the app (a plain link replaces the page, and the installed app has no back button). */
export async function downloadFile(url: string, filename: string) {
  const res = await fetch(url, { credentials: 'same-origin' })
  if (!res.ok) {
    let body: any = null
    try { body = await res.json() } catch { /* not JSON */ }
    throw extractError(body, res.status)
  }
  const blob = await res.blob()
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(href), 10_000)
}

export function downloadUrl(method: string, args: Record<string, unknown>) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  return `/api/method/${A}${method}?${qs.toString()}`
}
