# Changelog

All notable changes to AlphaX HR. Versions follow `alphax_hr/__init__.py`.

## 0.22.0 — 2026-11-05

- **Settings, easier:** sections in a side menu (Company & branding, Portal & pages, Employees & salary, Attendance, Leave, Payroll/GOSI/loans, Accruals, Payslips, Notifications, More setup), a short guide on each, *Find a setting*, changed fields highlighted, a sticky bar listing every unsaved change with Save / Discard, and a warning before leaving with unsaved changes.
- **My Attendance calendar** is compact (date-picker size) with the chosen day's status, hours, shift and late/early flags beside it.

## 0.21.1 — 2026-11-05

- **Data issues on the employee profile are fixable in place:** set the suggested holiday list (company default or the current one) or leave approver (the reporting manager) in one click, create the employee's login from their e-mail (Employee role, welcome e-mail to set a password), or jump to the right section.

## 0.21.0 — 2026-11-05

- **Fix:** migrate no longer stops when a bank in the built-in list already exists under another name with the same SWIFT code (e.g. SABB / Saudi Awwal Bank); reference data problems are logged and skipped.
- **Request checks:** sensible dates for every request (no trips longer than 90 days, passports kept at most 180 days, no travel in the past, nothing years ahead); one open resignation / final exit / loan / advance at a time; the same request cannot be sent twice; loans and advances checked against the Saudi Labor Law limits when submitted.
- **Overlap control:** a business trip cannot overlap leave or another trip; leave cannot be taken on trip days; no late/early permission or attendance request on a day of leave or travel.
- **Loan postponement** lists the employee's loans being repaid; it is unavailable when there is none.
- **Help before asking:** while writing a request, matching help-centre answers are suggested; "This answered my question" closes the form.
- **Request details** show as labelled values instead of JSON.
- **Bulk update:** every employee field (including your company's required fields), "only where empty", and a new *Fill missing required fields* tab that fills several fields at once and lists what is still missing.
- **Notifications:** the bell shows only HR notifications (setting to show all); per event and per service, add departments, branches, designations, roles, employees or users — or exclude them.
- **Fix:** record history showed the oldest 1,000 changes instead of the newest.

## 0.20.1 — 2026-11-05

- Fix "cannot import name N_" on older Frappe v15 releases; service worker "body already used" error; team appraisals crash for users without an employee record; wide org charts scale to the PDF page and teams without sub-teams are listed in a column.

## 0.20.0 — 2026-11-04

- **Organisation chart views**: *Chart* (top-down boxes with reporting lines), *Tree* (indented, expand/collapse) and *By department* (one card per department, managers first). The chosen view is remembered.
- **Org chart export**: PDF as chart, tree or by department; Word (.docx) as a reporting-lines outline or by department; Excel. No extra Python packages needed.
- **Delete employees** (HR Manager): from the quick view or several at once from the People list/table. Each employee is checked on its own — anyone with attendance, leave, payroll or a team reporting to them is kept, with the reason; the salary assignment AlphaX made at creation is removed when there is no payroll yet.
- **System health and the employee field map moved to the Desk**: *AlphaX HR Settings → Tools* (System health for System Managers, Employee field map for HR/System Managers). The AlphaX *HR status & setup* page keeps only *HR status* and *Settings*.

## 0.19.0 — 2026-11-03

- **Portal mode**: HR and employee-self-service users always land in AlphaX and are redirected away from the Desk; roles that keep the Desk (accounts, system) are set in Settings. Sets *System Settings → Default App* to AlphaX HR while on.
- **Sign-in page** at `/alphax-login`: bilingual, branded with the app name and logo, password reset, two-factor falls back to Frappe's login. Using it for `/login` is opt-in (off by default); Frappe's own login is never replaced.
- **Page access**: HR managers hide pages for everyone or show them only to chosen roles; menus, phone tabs and direct links follow it.
- **Monthly accruals** for end of service (Art. 84 full award, or Art. 85 resignation basis) and annual leave (unused days × daily wage): re-measured each month per employee, only the difference is posted as one journal entry by cost center; ordered cancel; warnings when the settlement components do not post to the provision accounts.
- **Bank salary file (WPS)** from a payroll run: Excel with ID/Iqama, bank, SWIFT, IBAN, basic, housing, other earnings, deductions and net.
- Marketplace readiness: type hints on every API method (validated by Frappe at runtime), Frappe Semgrep rules, ruff and dependency audit in a new *Linters* workflow, translations resolved per request instead of at import, scheduled jobs no longer commit manually, payslip image paths confined to the site's files, privacy policy and listing.
- HR managers can pick ledger accounts in Settings without an Accounts role.

## 0.18.0 — 2026-11-03

- Payroll component catalogue, Saudi banks, salary history, bulk update, check-in exceptions

## 0.17.2 — 2026-11-03

- Clean up after removing CentralHRMS / irsaa HR apps

## 0.17.1 — 2026-11-03

- Sign-out works on Frappe v15, quiet loan preview, stale employee save reloads

## 0.17.0 — 2026-11-03

- Loans & advances, bonuses/deductions within Saudi limits, labour-law articles, white-label

## 0.16.0 — 2026-11-03

- Payroll runs by group or employee, appraisals in AlphaX, management approval

## 0.15.0 — 2026-11-03

- Leave counting policy, notifications by event, approval delay control

## 0.14.0 — 2026-11-03

- Payroll totals and per-employee corrections inside AlphaX

## 0.13.2 — 2026-11-03

- Stamp/signature uploads attach to AlphaX HR Settings so every HR user can see them

## 0.13.1 — 2026-11-03

- Withdrawing a leave made from a vacation plan works (period goes back to planned); CI site gets a fiscal year

## 0.13.0 — 2026-11-03

- Payslip with stamp & signature, check-in rules and movements, phone notifications, help centre

## 0.12.1 — 2026-11-03

- Phone home fits the screen; HR status finds missing print images

## 0.12.0 — 2026-11-03

- Employee file and home, HR conversation, profile updates through HR, fixes

## 0.11.1 — 2026-11-02

- Stale employee links no longer block fixes; contract preview/download fixed

## 0.11.0 — 2026-11-02

- Leave form follows site-mandatory fields, attendance exceptions policy, annual vacation planning

## 0.10.0 — 2026-11-02

- ESS services hub, late/early permissions, expenses, documents, my team, mobile app

## 0.9.0 — 2026-11-02

- Employee requests, penalties, payroll control centre, final settlement, appraisals, cut-over

## 0.8.0 — 2026-11-02

- One Iqama field everywhere; bilingual employment contract

## 0.7.0 — 2026-11-02

- Salary step, bank, in-app record view, HR status with fixes

## 0.6.0 — 2026-11-02

- Setup & health, grouped sidebar, wizard fixes from hcs

## 0.5.1 — 2026-11-02

- Fix migrate on sites with a full Employee table (MariaDB 1118)

## 0.5.0 — 2026-11-02

- Activity trail, week-offs, leave ledger, wizard v2, fixes from hcs

## 0.4.0 — 2026-11-02

- Shifts, roster, attendance register, overtime, employee requests

## 0.3.0 — 2026-11-02

- People views, export, org chart; new employee wizard; seniority date

## 0.2.1 — 2026-11-02

- Annual leave by company policy and contract; fixed leave type names

## 0.2.0 — 2026-11-02

- Saudi leave engine and employee rules (CentralHRMS Phase 1)

## 0.1.0

- First release: React frontend at `/alphax`, Saudi rules engine (GOSI, end of service, leave, Nitaqat).
