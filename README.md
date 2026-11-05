# AlphaX HR

A modern, bilingual (English / العربية) HR experience for Saudi companies, built in React on top of **Frappe HRMS + ERPNext**.

* **One system of record.** Every employee, leave, attendance, payroll and expense record lives in ERPNext/HRMS. AlphaX adds no parallel tables for them.
* **Own route, no Desk for users.** The app lives at `/alphax` (Frappe HRMS already uses `/hr/*` for its Roster).
* **No Desk for users.** Employees, managers and HR work entirely in `/alphax`. Desk stays for administrators.
* **Saudi rules built in.** GOSI (date-effective, Legacy vs New system), end-of-service (Articles 84/85/87/80), annual and sick leave, Iqama and document expiry, Nitaqat estimate. These replace the CentralHRMS features for new KSA customers.

```
React SPA (/alphax)  ──►  alphax_hr API (permission-checked)  ──►  Frappe HRMS + ERPNext (data)
                       └─ alphax_hr.saudi (pure rules engine, unit-tested)
```

| HR home | Compliance (Arabic) | Employee on phone (Arabic) |
|---|---|---|
| ![HR home](docs/screenshots/09-hr-home.png) | ![Compliance](docs/screenshots/ar-compliance.png) | ![Phone](docs/screenshots/05-arabic-phone-home.png) |

| Sign-in | Accruals | Payroll control |
|---|---|---|
| ![Sign-in](docs/screenshots/36-sign-in.png) | ![Accruals](docs/screenshots/35-accruals.png) | ![Payroll](docs/screenshots/23-payroll-control.png) |

## Modules (v0.25)

| Area | Who | What |
|---|---|---|
| Self-service | Every employee | Leave requests adapt to the site's own mandatory Leave Application fields (asked in the form; the return-to-work date is filled automatically); Services hub (every request in one place); check in/out (with location); leave balance and requests; attendance month view with corrections, shift changes and late-arrival / early-exit permissions (manager approves, monthly limit in settings, excused minutes drop out of lateness and penalties); expense claims with receipt photo to the expense approver; my documents (ID/passport/contract expiry, files, letters); payslips with PDF; my warnings; my performance; profile and contact updates; upcoming holidays |
| Employee file & home | Every employee, HR | Sidebar in three groups (self service, my pay, my file; profile also from the avatar); home shows HR announcements (by company/department, scheduled, pinned, Arabic text) and recent activity; employees ask HR to update passport, Iqama, work permit, marital status, Arabic name or bank details with a copy of the document — HR approves and the employee file and document are updated; every request has a message thread with HR; letters, documents and passport release go straight to HR without the manager |
| Payslip | Employees, HR | Bilingual AlphaX payslip (attendance days, earnings, deductions with penalties shown apart, annual leave left, warnings of the period) with company stamp, authorised signature, signatory and footer notes chosen by HR in Settings; images embedded so PDFs never fail on broken image links; one click makes it ERPNext's default Salary Slip print format |
| Check-in rules & movements | HR, managers | Location rule per company or policy group (anywhere / location required / inside a work location with radius), minimum minutes between punches; work locations with "use my current location"; live check-ins & movements board (in, out, not in, on leave, outside a location, map links) for HR and for managers' teams |
| Leave counting policy | HR | Per leave type, decided by HR in Leave setup: count calendar days, working days only, or skip only public holidays / only weekends; sandwich rule (a weekend between two leave days counts — inside one request, or also across separate requests taken before and after it; optionally public holidays too); must start and end on a working day (e.g. marriage leave = 5 working days); minimum notice; maximum counted days per request; emergency leave types. The employee sees the counted days before applying; the balance is checked on the counted days |
| Notifications by event | HR decides, every user receives | Email and in-app/phone alerts for leave requests and decisions, emergency leave (manager and HR at once), requests submitted and decided, check-in/out confirmation, late arrival, missing check-in (scheduled every 15 minutes), approval reminders and escalations, announcements — each event on/off with its channels and recipients (employee, manager/approver, HR) in Notifications; a bell with unread count in the header |
| Approval policies | HR (edit: HR Manager) | Per kind of approval and optionally per request/leave type, company, department, branch, designation, amount or days: working-day waiting times — escalation to HR, HR reminder, automatic rejection with a comment (the employee raises it again); optional multi-level approval for requests and leave (reporting manager, manager's manager, named user, HR, management; levels by amount or days), restarting from the first level or resuming at the level that rejected; *Try it* on an employee |
| Approval delay control | HR, managers | One reminder to the approver after the reminder hours and one escalation to the approver's manager and HR after the escalation hours, for every approval type (leave, expense, attendance, shift, compensatory, AlphaX requests, vacation plans); Approval delays page with every waiting item by age and stage (on time, reminded, overdue, escalated), and per approver the pending count, oldest item and average decision time over 90 days |
| Notifications | Every user | Phone/browser push (installed app on Android and iPhone 16.4+, desktop browsers): new approvals for managers, decisions on leave and requests, messages from HR, warnings, announcements; built-in Web Push (VAPID), no extra service |
| Help centre | Employees, HR | Searchable HR articles (Arabic/English, categories, attachments, helpful votes); "Ask HR" conversations tied to a topic, answered in a private thread and resolved by HR |
| Mobile app | Every user | Installable on Android and iPhone from the browser (Install app button / Add to Home Screen): app icon, full-screen, bottom tab bar, home shortcuts (check in, leave, services), opens offline to the last loaded screen. Needs the site on HTTPS |
| Attendance exceptions | HR (rules shown to the employee) | Policies per company, department, designation or employee (most specific wins): exempt from attendance tracking, own late / early-exit grace, free late minutes per month, single punch counts as present, own permission limit, no penalty suggestions; applied in the attendance register, payroll checklist and penalties |
| Annual vacation planning | Employees, approvers, HR | Employees plan the year's vacation (working days counted on their holiday list, entitlement shown, optional minimum continuous block and deadline); they see colleagues already away; managers approve, request changes or reject from the inbox or the planner with a weekly per-department heatmap (red above the allowed share); approved periods become leave requests in one tap; annual leave outside the approved plan is flagged |
| Managers | Approvers | My team: who is checked in, not in yet or on leave today, with call buttons; approvals inbox; team leave calendar |
| Approvals | Leave/expense approvers, HR | One inbox for Leave, Expense, Attendance, Shift and Compensatory requests; follows active Workflows; team leave calendar |
| HR core | HR User / HR Manager | People as list, table or organisation chart (from *Reports to*: top-down chart, tree or by department; PDF, Word or Excel export); delete one or many employees (HR Manager; employees with history are kept and the reason shown); department/status/nationality filters; quick view; Excel/CSV export; full profile with Print/PDF; missing mandatory fields highlighted with a popup; new employee as a step-by-step wizard (one ID field — the site's other ID fields are filled from it; Saudi/non-Saudi read from the ID) |
| Shifts & attendance | HR, every employee | Roster grid with per-employee week-offs (stored in the employee's own holiday list, so leave, attendance and payroll follow them) (week/2/4 weeks) with bulk shift assignment (overlaps refused per employee); monthly attendance register from check-ins, attendance, leave and holidays (present, absent, late with minutes, missing punch, overtime) with Excel export; overtime per Art. 107 (hourly wage + 50% of hourly basic); employees request attendance corrections and shift changes, approved in the AlphaX inbox |
| Leave balances & ledger | HR, employees, approvers | Balance per leave type for every employee (Excel export); per-employee ledger with running balance; Art. 117 sick-leave year (120 days from the first sick day, tiers full/75%/unpaid) — requests beyond it are refused |
| Activity trail | HR (and record readers) | Every change to HR records — field old → new, who, when, comments, workflow steps, attachments — per record (profile, any request) and as an HR-wide Activity log with filters |
| HR status & setup | HR Managers (System tab: System Managers) | Overall HR status — data gaps, expired/expiring documents, employees without salary or mandatory data, approvals waiting, leave and payroll setup — each with a Fix panel (bulk-set approver, manager, holiday list); all AlphaX settings; the site's Employee field map |
| Salary | HR | New-employee Salary step (total package split into basic/housing/transport by %, or component amounts; GOSI employee share for Saudis) creating the employee's own Salary Structure + Assignment (CentralHRMS approach); Change salary from a date on the profile |
| Record view | Everyone (per permissions) | Any HR record opens inside AlphaX (/alphax/r/DocType/name) with every field, tables, attachments, workflow actions and activity — no Frappe desk needed |
| Employee requests | Every employee, managers, HR | One engine for letters (salary certificate, employment, experience — bilingual PDF issued on approval), exit & re-entry / final exit visas, Iqama renewal, salary advance, business trip, assets, passport release, resignation (sets the relieving date) and general requests; each type has its own fields, manager and/or HR approval, target days and attachment rule; HR can raise requests for employees; requests flow through the Approvals inbox |
| Warnings & penalties | HR, every employee | Violations schedule (MHRSD model regulations as a starting point) with the penalty growing on each repeat within 180 days; 5 days' wage per violation and per month caps; no penalty for violations discovered more than 30 days earlier; deductions go to payroll as Additional Salary; suggestions from the attendance register; employees acknowledge or object within 15 days; cancelling reverses the deduction |
| Loans & salary advances | Employees, HR (pay out / settle: HR Manager) | Loan and salary-advance requests (manager → HR), or entered by HR; repayment schedule with Saudi limits checked month by month (installment at most 10% of the wage without written consent, Art. 92; total deductions at most half the wage, Art. 93); paid by cash or bank transfer through an HRMS Employee Advance and Journal Entry; installments go into payroll automatically as Additional Salary against the advance; postpone an installment (also by employee request); one-time settlement by cash, bank transfer or one salary; balances flow into the final settlement |
| Bonuses, deductions & increments | HR | Bonus / one-time payment / arrears for one employee, many or a department (amount or % of wage); HR deductions by legal basis — damage or loss spread at five days' wage a month (Art. 91), deductions needing written consent, court orders (a quarter of the wage) — refused when a limit would be broken; deduction meter per employee and month; bulk salary increments (% of salary, % of basic or amount) from a date |
| Payroll components & banks | HR | Standard Saudi components created once and mapped (basic, housing, transport, other, food, phone, overtime, bonus, commission, arrears, leave encashment, end-of-service, EOS and leave provisions as accruals, GOSI employee/employer, absence, penalty, loan, HR deduction); existing components with common names are reused; wage mapping for GOSI / EOSB / Nitaqat. Saudi banks with abbreviation, SAMA IBAN code and SWIFT; the bank is set from the IBAN |
| Bulk update & exceptions | HR (apply: HR Manager) | Set one field for many employees (department, branch, approvers, holiday list, shift, cost center, bank, salary mode, annual leave days…) or a check-in / attendance rule; per-employee check-in and attendance exception on the profile |
| Saudi Labor Law library | Every employee | 16 standard help-centre articles in English and Arabic (working hours, overtime, all leave types, holidays, probation, notice, end of service, penalties, salary deductions, loans, wages, Art. 80, GOSI), reflecting the 2025 amendments; HR can edit them or restore missing ones |
| Payroll control centre | HR (approval: HR Manager) | Payroll runs per month for the whole company, or one department, branch, business line (Employee field set in Settings or found automatically), cost center (salary expense booked to it) or chosen employees — one employee is single-salary processing, several is bulk; an employee can be in only one run per month. Each run: Prepare → Review → Approve → Process (HRMS Payroll Entry + salary slips) → Close, with who/when and a checklist behind every step — pending leave/attendance/shift/advance requests, attendance gaps, absences, unpaid and reduced sick pay, penalties, overtime (add Art. 107 pay in one click), bonuses/deductions, advances and loans, joiners and leavers, missing salary/bank/GOSI data, appraisals; blocking items need fixing or an HR Manager override with a note |
| Payroll corrections | HR (remove / redo: HR Manager) | Salary slips table in the control centre with GOSI, loans, deductions and net per employee and totals for the month; fix one employee without re-running payroll: add an earning/deduction this month (slip recalculated) or next month, recalculate after fixing attendance/leave/salary, remove from the run (salary on hold) and add back, add employees missing from the run, redo a submitted slip while its accounting entry is not posted; every change is logged |
| Final settlement | HR (approval: HR Manager) | End-of-service award (Art. 84/85/87/80), unused-leave encashment, final salary, advances and other items; paid with the final payroll (Additional Salary) or separately; bilingual statement PDF |
| Payroll reports | HR | GOSI register, end-of-service calculator |
| Appraisals | HR, managers, employees, management | Two ways. **Performance cycle**: HR builds templates (weighted goals and rating criteria, linked to designations) and starts a cycle; employees rate themselves (stars + reflection) in My performance; the reporting manager scores the goals and rates the criteria in Team appraisals; HR finalises (scores computed by HRMS) and completes the cycle. **Appraisal request** (increment, promotion, confirmation, bonus): raised by the employee (reporting manager → HR → management) or by the reporting manager for a direct report (HR → management). Management approvers are a role HR assigns (e.g. CEO/GM), not the reporting line |
| Cut-over | HR Manager | Readiness page before uninstalling CentralHRMS: legacy requests, warning letters and Iqama data to import (dry run, then once), legacy fields that still hold data, active workflows, and what AlphaX needs to run alone |
| Saudi leave engine | HR, every employee | Statutory leave rules checked on every request (maternity 84, paternity 3, marriage 5, bereavement 5/3, Iddah 130/15, exam, Hajj once after 2 years), sick-leave pay tiers 30/60/30 with certificate before approval, annual leave 21/30 days allocated per service year, escalation of leave requests left pending |
| Employee rules | HR | National ID / Iqama / border number checks (Saudi flag set from the ID), duplicate IDs, Saudi IBAN check, minimum age, probation end date |
| Portal & sign-in | HR Manager | *Portal mode*: HR and self-service users always land in `/alphax` and cannot open the Desk; roles that keep the Desk are listed in Settings (default System Manager, Accounts Manager, Accounts User). Branded bilingual sign-in page at `/alphax-login` (optionally used for `/login`). *Pages*: hide any page for everyone or show it only to chosen roles |
| Accruals | HR Manager, Accounts Manager | Each month the end-of-service obligation (Art. 84 full award, or Art. 85 resignation basis) and the unused-annual-leave obligation (days × daily wage) are measured again per employee and only the difference is posted — one journal entry, Dr expense / Cr provision by cost center. Later months must be cancelled first. Warnings until the End of Service Benefit and Leave Encashment components post to the provision accounts, so final settlements use the provision |
| Bank salary file | HR | Excel salary transfer file from a submitted payroll run (ID/Iqama, bank, SWIFT, IBAN, basic, housing, other earnings, deductions, net) for the bank's WPS upload |
| Holiday lists | HR (edit: HR Manager) | Lists with status and the employees on them; extend into next year in one click (weekly offs, Saudi public holidays, roster week-off lists follow); new list with Saudi public holidays filled in; move Eid dates when announced; set on employees or as company default — no desk needed |
| Attendance devices | HR (set up: HR Manager) | Fingerprint and face devices of any brand. **ZKTeco** (and other ADMS/iClock firmwares) push punches straight to AlphaX: point the device's *Cloud Server* to the site — no software on a PC; a device that connects before it is added waits for HR to enable it; users on the device, model and last contact are shown; commands to the device (upload all logs again, send employees, read info, reboot). **Other brands** (Hikvision event push, Suprema, Anviz, Dahua or a local bridge) post to the push API with a per-device token. **Attendance software** (ZKTeco BioTime, ZKTime/ZKAccess or own tables on MySQL, PostgreSQL or SQL Server) is read every few minutes. **Log files** (attlog.dat from USB, CSV) can be imported. Every punch is kept as a device log, matched to the employee by attendance device ID, Employee ID or Iqama, and becomes an Employee Checkin (duplicates skipped); unknown device users are linked to an employee in one click and their punches imported |
| Compliance | HR | Nitaqat estimate, Iqama/work permit/passport/contract expiry, data-readiness checks (holiday lists, approvers, GOSI dates, Iqama data …) |

## Install

Requirements: Frappe/ERPNext/HRMS v15 (v16 targeted), Node 18+ only if you rebuild the frontend.

**Standalone.** AlphaX HR needs only Frappe, ERPNext and Frappe HRMS (HRMS itself requires ERPNext). It does not use
CentralHRMS, the Lending app or any other custom app; CI installs exactly these four apps on a fresh site.

```bash
cd frappe-bench
bench get-app --branch version-15 erpnext
bench get-app --branch version-15 hrms
bench get-app --branch version-15 https://github.com/mskhanIND/alphax_hr
bench new-site YOUR_SITE --install-app erpnext
bench --site YOUR_SITE install-app hrms
bench --site YOUR_SITE install-app alphax_hr
```

**Your own name and logo.** HR status & setup → Settings → General: *App name*, *Tagline*, *Logo*, *App icon* and
*Use the name and logo on the sign-in page too*. They are used in the menu, browser tab, installed phone app,
notification e-mails and the sign-in page (uploads are made public automatically).

The built frontend is committed under `alphax_hr/public/frontend`, so no Node build is needed on servers. Open `https://YOUR_SITE/alphax`.

**Portal mode.** HR status & setup → Settings → *HR portal and sign-in*: tick *Keep HR, managers and employees in AlphaX (no desk)*. Everyone without one
of the *Roles that may still use the desk* is sent from `/app` to `/alphax`, and *Default App* becomes AlphaX HR. Administrator
always keeps the Desk. *Use the AlphaX sign-in page for /login* (off by default) sends `/login` to `/alphax-login`;
`/login?standard=1` always shows Frappe's own page (two-factor and social logins use it automatically).

**Desk tools.** *AlphaX HR Settings* in the Desk → *Tools*: *System health* (scheduler, workers, failed jobs, broken server scripts, leftover mandatory fields) and *Employee field map* (site fields AlphaX fills automatically; link more in *Employee Field Links*).

**Pages.** Settings → *Pages*: hide a page for everyone, or list the roles that may open it.

**Accruals (month end).** Settings → *Accruals*: basis, and the EOS / leave expense and provision accounts. Set the
*End of Service Benefit* and *Leave Encashment* salary components to post to the same provision accounts. Then
Payroll → *Accruals*: pick the month, check the lines, *Post accruals*. Companies reporting under full IFRS should still
have the end-of-service obligation valued by an actuary each year (IAS 19) and post the difference.

**Attendance devices.** `/alphax` → *Attendance devices* → *Add device*, then choose how it connects:

* *Device push (ZKTeco ADMS / iClock)* — on the device: Menu → Comm. → Cloud Server Setting. Server address = the site
  domain, port 443 with HTTPS on (or 80), and enter the device's serial number in AlphaX. The reverse proxy must pass
  `/iclock/` to Frappe (the standard bench nginx config does). Older firmwares without HTTPS need plain HTTP on port 80.
  Optionally limit the device to its public IP address.
* *Push API* — create a token on the device card; the bridge or device posts to
  `/api/method/alphax_hr.api.devices.push` with the header `X-AlphaX-Device-Token`.
* *Database pull* — host, port, database and a read-only user of the attendance software; choose BioTime, ZKTime or
  your own table and columns. SQL Server needs `pip install pymssql` in the bench.
* *Log file* — import attlog.dat or a CSV on the device card.

Set each employee's *Attendance Device ID* to the user number on the device (or match by Employee ID or Iqama).

**Make /alphax the landing page.** Set *System Settings → Default App* (or a user's *Default App*) to **AlphaX HR**. Users then land on `/alphax` after login.

### First setup (5 minutes)

1. **AlphaX HR Settings:** default company; map salary components to *GOSI Basic*, *GOSI Housing* and *EOSB Wage*; optional Saudization target.
2. **GOSI Contribution Rate:** statutory rows are seeded (Legacy; New system 9% → 11% stepping each July 2025–2028; Non-Saudi 2% hazard). Edit them when GOSI publishes changes.
3. **Employees → Saudi Compliance tab:** *Saudi National*, *First GOSI Registration Date* (decides Legacy vs New; not the hire date), Iqama number/expiry for non-Saudis.
4. Open **Compliance** in `/alphax` and clear the data-readiness list.
5. Open **Leave setup** in `/alphax`:
   - **Create statutory leave types** adds any missing ones and links them to their rules. Existing leave types with matching names are linked automatically on install.
   - **Allow without allocation** on any statutory type flagged as needing an allocation (for example HRMS's own *Sick Leave*); the rule caps those leaves instead.
   - **Annual leave:** click **Set up Annual Leave** once (it links an existing *Annual Leave* type or creates it). Leave type names used by AlphaX are then fixed: they cannot be renamed or deleted.
   - Optional **Count seniority from** date: years for a company's senior entitlement are counted from that date (or the joining date, if later). The legal 30 days after 5 years from joining always applies.
   - Pick the **company policy**: *Saudi Labor Law* (21 days, 30 after 5 years) or *Fixed for all employees* (e.g. 30 days, as at IRSAA). An employee whose contract says otherwise gets *Annual Leave Days (contract)* on their profile. The legal minimum always applies.
   - Check the **allocation plan** (it shows what each number is based on), then **Create allocations** or tick *Allocate automatically every night*.

Settings for probation days, minimum age and IBAN checking are in *AlphaX HR Settings*.

### Coming from CentralHRMS

HR Manager → **Administration → Cut-over readiness**. Preview and import legacy requests (Letters, Exit Re-Entry, Final Exit, Business Travel, Assets, Housing Advance, Contract Termination, Iqama and other requests become AlphaX requests), Warning Letters (become acknowledged warnings) and Iqama/ID values (only blanks are filled). Imports are idempotent and never change the old app. When every item is green, CentralHRMS can be uninstalled.

## Security model

* Only these are public: the sign-in page, the web app manifest, the service worker script, and the device endpoints (`/iclock/…` answers only enabled devices with a known serial number and, if set, allowed IP; the push API needs the device's token). Every API checks login, then server-side roles (never a role sent by the browser).
* Every API argument is type-annotated and checked by Frappe; CI runs Frappe's Semgrep security rules.
* Reads use permission-aware `frappe.get_list` / `check_permission`; writes go through `insert/save/submit`, so HRMS validations, Workflows and User Permissions remain authoritative.
* Employee self-service is always scoped to the employee linked to the signed-in user.
* Employee edits use optimistic locking (`modified`).

## Develop

```bash
# backend rules engine tests (no Frappe needed)
python -m unittest discover -s tests

# frontend
cd frontend
npm install
VITE_FRAPPE_URL=http://hr.test:8000 npm run dev   # proxies /api to your bench
npm run build                                      # outputs to alphax_hr/public/frontend
```

For local dev against a bench, sign in at the bench URL first and set `"ignore_csrf": 1` in that **development** site's `site_config.json`.

## Tests

| Suite | What | Run |
|---|---|---|
| Rules engine | 18 tests: GOSI Legacy/New/Non-Saudi rates by period, cap, EOSB Art. 84/85/87/80, annual and sick leave, Nitaqat, document buckets | `python -m unittest discover -s tests` |
| API integration | 79 tests on a real Frappe + ERPNext + HRMS site, as Guest, Employee, second Employee, Manager and HR: data isolation, role checks, approvals (incl. a Workflow action literally named "Submit"), stale-write rejection, GOSI/EOSB, compliance | `tests/integration/run_frappe_tests.py SITE` |
| Browser E2E | 52 checks driving `/alphax` in Chromium: sign-in page, apply → approve leave, attendance, people, payroll, loans, accruals, compliance, GOSI, EOSB, Arabic RTL on a phone, no console errors | `node tests/e2e/smoke.mjs URL` |
| Frontend | Riyadh-time dates, and every UI string has an Arabic translation | `cd frontend && npx vitest run` |

All four run in GitHub Actions (`.github/workflows/ci.yml`); `linters.yml` runs Frappe's Semgrep rules, ruff and a dependency audit.

## Layout

```
alphax_hr/
  api/            whitelisted API (session, ess, approvals, hr, payroll, compliance)
  saudi/          pure-Python Saudi rules (gosi, eosb, leave, nitaqat, documents)
  alphax_hr/      DocTypes (AlphaX HR Settings, GOSI Contribution Rate) + Employee custom fields
  www/alphax.*    serves the SPA at /alphax
  public/frontend built React app
frontend/         React 19 + TypeScript + Vite + TanStack Query + Tailwind
tests/            rules-engine tests and Frappe integration tests
```

Nitaqat figures are an internal estimate; Qiwa remains the official source.

Changes: [CHANGELOG.md](CHANGELOG.md) · Privacy: [PRIVACY.md](PRIVACY.md) · Support: [issues](https://github.com/mskhanIND/alphax_hr/issues) or support@neotec.ai

License: MIT
