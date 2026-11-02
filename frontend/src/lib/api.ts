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
  leaveTypes: () => call<string[]>(A + 'ess.leave_types'),
  applyLeave: (args: Record<string, unknown>) => call(A + 'ess.apply_leave', args),
  withdrawLeave: (name: string) => call(A + 'ess.withdraw_leave', { name }),
  myAttendance: (month: string) => call(A + 'ess.my_attendance', { month }),
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
  lookup: (doctype: string, txt: string) => call<{ value: string; description?: string; label?: string }[]>(A + 'hr.lookup', { doctype, txt }),
  orgSummary: () => call(A + 'hr.org_summary'),
  // payroll & compliance
  payrollRuns: (year: number) => call(A + 'payroll.payroll_runs', { year }),
  slipSummary: (month: string) => call(A + 'payroll.slip_summary', { month }),
  gosiRegister: (month: string) => call(A + 'payroll.gosi_register', { month }),
  eosb: (args: Record<string, unknown>) => call(A + 'payroll.eosb', args),
  compliance: () => call(A + 'compliance.overview'),
  expiring: (days: number) => call(A + 'compliance.expiring_documents', { days }),
}
