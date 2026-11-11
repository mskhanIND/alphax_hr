# Changelog

All notable changes to AlphaX HR. Versions follow `alphax_hr/__init__.py`.

## 0.32.1 — 2026-11-11

- Fix: the Setup & health page failed to open after 0.32.0 (tile filter set up in the wrong order).

## 0.32.0 — 2026-11-11

- **Number tiles are filters.** Click a tile to see the employees or records behind it; click it again (or *Show all*) to go back. A bar shows what is filtered and how many.
  - Attendance register: Absent days, Late arrivals, Missing punches, Leave days, Overtime hours. Only employees with that measure, most first, with their matching days highlighted. Plus an employee search.
  - Check-ins & movements: Checked in, Checked out, Not checked in, On leave, Outside a work location (also as buttons), plus search.
  - My team: Checked in / Not checked in / On leave; *Leave requests waiting* opens Approvals.
  - Approval delays: Waiting / Reminded / Overdue / Escalated.
  - Loans: Being repaid / Approved, to pay out. Designations: all / standardized / suggestions / Saudis-only issues. Vacation planner: plan status. Setup: healthy / warnings / problems. GOSI: Needs attention.

## 0.31.0 — 2026-11-11

- **Punches refused for a missing shift.** When the site refuses check-ins without a shift assignment, Attendance devices now shows how many employees and punches are waiting. *Assign shifts* lists them (department, refused punches since, default shift, current shift) and assigns one shift, or each employee's default shift, from the first refused day with no end date. Their punches are imported at once.
- **Any shift assignment imports waiting punches.** Submitting a Shift Assignment (from AlphaX, the roster or desk) retries that employee's punches refused for a missing shift in its period.
- **Try again** on refused punches (Punches → Error). A retried punch keeps the employee it was matched to.

## 0.30.2 — 2026-11-11

- **Match employees links without overwriting.** The link (attendance user → employee) is kept on the connection, so employees whose Device ID or Iqama already holds another value (for example a national ID from an earlier system) are linked instead of refused; empty fields are still filled in. Punches match through the link from then on.
- Suggestion by device ID also compares the source's employee number.

## 0.30.1 — 2026-11-11

- **"Update not finished" banner.** After `git pull` the new screens are live at once, but the server code changes only after a restart. When they differ, AlphaX now shows which versions are running and the command to finish the update (`bench --site … migrate && bench restart`), instead of failing with "has no attribute".

## 0.30.0 — 2026-11-11

- **Terminals are added automatically.** Saving a database connection lists its terminals at once, and the regular pull refreshes the list every 6 hours: new devices appear with their name, IP address, location and model from the source's devices table (detail columns recognised by name, or set in Tables & columns). Automatic names are replaced by the source's device names; a location HR typed is kept. *Find terminals* is now only for an immediate refresh.
- **Match employees.** Lists everyone in the attendance database (name, national ID, user ID, employee number, waiting punches) with the AlphaX employee they match, or a suggestion by Iqama, employee number, device ID or name. Pick or correct, tick and *Link selected*: a national ID becomes the employee's Iqama, anyone without one is linked by device user ID, and waiting punches from all terminals are imported. Conflicts (an employee already holding another Iqama or device ID) are listed, not overwritten.
- With *Match by National ID / Iqama*, people with no national ID in the source now match by attendance device ID.
- People table: optional employee number column (ADMS: EmpNo).

## 0.29.0 — 2026-11-11

- **Tables & columns, read from the database.** On a database connection, *Tables & columns* lists the database's tables and proposes the punch table (user, time, IN/OUT, device serial), the people table (ID, value to match by, name) and the devices table (serial, name, active), with a *suggest* chip wherever your choice differs. Works for any attendance software, not only the presets.
- **IN / OUT values and preview.** Set which values mean IN and OUT (the values found in the data are shown), then see the latest punches exactly as AlphaX will read them: IN/OUT, terminal and the employee matched.
- **Devices table.** *Find terminals* takes each device's name and active flag from the source. Inactive devices start excluded, and each terminal has an *Include* switch. Punches of excluded terminals are not imported.
- **Sync status and backfill.** Per connection: how far AlphaX has read, the last successful read, connection state and the oldest punch in the database. For any period it shows punches in the database vs. in AlphaX and what is missing, per terminal, and *Read the missing punches* fills the gap (in the background for large periods) without moving the regular pull or doubling a punch.
- **Names for unmatched punches.** Names come from the people table. With *Match by: National ID / Iqama*, linking an unmatched person sets the Iqama on the employee and imports their waiting punches from all terminals of the connection.
- Reading rules (IN/OUT, matching, clock offset) set on a connection now apply to all its terminals.

## 0.28.1 — 2026-11-11

- **Attendance database health.** Each failed read is recorded with its reason, the time it started failing and how many attempts have failed in a row. The card shows **Connection failed** with the reason, and the database's terminals show **Source not reachable**. HR is told once when it stays down past the alert hours (with the reason), and told again when it connects. Punches wait safely in the attendance database and are read when it is back. A terminal that is quiet (closed site, weekend) raises no alert; only its database is watched.
- **Connect attendance database** button: opens the form prefilled for an ADMS SQL Server database.

## 0.28.0 — 2026-11-11

- Database connection errors now say what to check (port / firewall, login, database name) instead of the raw driver message.

- **One database connection for many devices.** Companies whose devices all write to one attendance server (an ADMS server, BioTime, ZKTime / ZKAccess, local or cloud) add that database once. *Find terminals* lists every device in it by serial number, with punch count and last punch, and punches are filed under the device they were made on. Each terminal shows its own status and takes its own branch and location. Terminals appear without a second login, and new devices are added as they show up in the data.
- **ADMS server preset** (CheckInOut + EmpDetails): users are matched by the national ID in EmpDetails (Match by: National ID / Iqama). Punches of users missing from EmpDetails still arrive, under their device user ID, for HR to link.
- National ID matching also reads the older `iqama_national_id` employee field.
- The Host field accepts `server:port` or `server,port` (SQL Server style). *Test connection* also reports how many terminals the database holds.

## 0.27.0 — 2026-11-11

- **Punches become HRMS attendance.** Every night (and when a device sends punches for earlier days) the register's result for employees who punch is submitted as Attendance: present (late entry / early exit flagged), half day or absent by the shift's hour thresholds, absent on a working day with no punch, a missing punch left open for correction within the re-check window. Attendance from HR, attendance requests or leave is never changed; AlphaX's own records are corrected when punches arrive late (the old one cancelled with a comment). Settings → Attendance & check-in; *Mark now* and last run on Attendance devices.
- **Fix: absences were paid.** With payroll based on leave, absent days were not deducted. The payroll checklist now says so and *Deduct absent days* switches payroll to attendance (days nobody marked stay paid). On attendance-based payroll it warns about absent days not yet recorded.
- **Fix: punches without IN/OUT were ignored** by the register (devices on "Alternate", or staff not pressing the keys). Such days are read as first punch IN, last punch OUT, repeated taps counted once. New device setting *First IN, last OUT (ignore the keys)*; a device sending every punch as IN gets a hint to use it.
- **Device controls:** HR is told when a device is offline for the set hours (once per outage); a device can belong to a branch and punches by other branches' employees are flagged; *Users on the device* lists employees who left but are still on it (remove them in one click), employees without a device ID and those not on the device; delete one user; clear device logs only after every punch is imported.

## 0.26.0 — 2026-11-05

- **Designations & Saudization** (new HR page, *People*):
  - Standard profession catalogue (Saudi occupational classification titles, Arabic names, other titles) and every designation mapped to one; suggestions by matching the designation name (English or Arabic); accept one or all; merge duplicate designations (all records move); create designations from standard professions.
  - Dated Saudization rules by profession group, shipped as checked on 05-11-2026 and editable: administrative support 100% (HR, personnel, secretarial, translation, data entry …), tourism front office 100%, marketing 60% (SAR 5,500), sales 60%, procurement 70%, project management 70% (from 14-02-2027), accounting 40% → 50% → 60% → 70%, engineering 30%, technical engineering 30%, pharmacy, dentistry — each with its start date, worker threshold and the wage from which a Saudi counts.
  - Control: a non-Saudi cannot be given a Saudis-only profession (Block / Warn / Allow); existing cases are listed. *Counts as Saudi (Nitaqat)* on the employee for mothers of Saudis and children of Saudi women.
  - Saudization by profession: workers, Saudis counted, required %, how many more Saudis are needed now and at the next phase.
- **Nitaqat estimate:** follows the official schedule — Saudis count fully from SAR 4,000, SAR 5,000 from 25-04-2027 and SAR 6,000 from 25-04-2028; below SAR 3,000 a Saudi no longer counts (it was counted as half). Compliance shows who stops counting fully at each date, the ratio afterwards and the monthly cost of raising them.
- **Resignations** are never rejected automatically by an approval policy; one left unanswered for 30 days is accepted automatically, as the law treats it.
- **Article 80 watch:** absences without a valid reason from the attendance register; at 10 days in a row or 20 in the contract year a draft written warning is prepared and HR and the manager are told; past 15 / 30 HR is told whether a dismissal without award is possible (only if the warning was issued). Shown on *Warnings & penalties*.
- **Final settlement:** notice under Art. 75 (30 days employee / 60 employer, indefinite contracts), notice pay under Art. 76 either way (the resignation request counts as the written notice), and Art. 77 compensation for ending a contract without a valid reason (15 days' wage per year, the rest of a fixed term, at least two months, or the amount set in the contract); on the statement PDF.

## 0.25.0 — 2026-11-05

- **Holiday lists in AlphaX** (*Time & attendance → Holiday lists*), no desk needed:
  - Each list with its status (current, ends soon, ended), weekly off days, public holidays, employees and company defaults; problems explained in plain words with the fix next to them.
  - **Extend** a list into next year in one click: same weekly offs and the Saudi public holidays; employees stay on the list and their own week-off lists (roster) are extended too.
  - **New list** for a year with the weekly off days and the Saudi public holidays filled in (Founding Day, Eid al-Fitr, Day of Arafah, Eid al-Adha, National Day); Eid dates are estimates and can be moved when announced; set it as company default or on employees in the same step.
  - Edit public holidays (weekly offs kept); set a list on employees or as company default.
  - HR status: each employee's holiday-list problem is spelled out (ended on …, ends in N days, no list and no company default), with a link to Holiday lists instead of the desk.
- **Employee profile:** gaps in other sections no longer block saving a section (no more jumping between sections); an edit that empties a mandatory field is still refused. *Fill now* opens one form with every missing mandatory field and saves them together.

## 0.24.0 — 2026-11-05

- **Approval policies** (new HR page, *Administration → Approval policies*), switched on per policy, for all approvals or only some (requests, leave, expenses, attendance corrections, shift changes, compensatory leave, vacation plans), and optionally only for a request or leave type, company, department, branch, designation, amount or number of days. The most specific enabled policy wins; without one, the reminder/escalation hours in Settings apply as before.
  - **Waiting times in working days** (employee's holiday list): the approver's time, then **escalation to HR** (and the approver's manager), then an **HR reminder** to the approver, then — if switched on — **automatic rejection** with HR's comment. The employee sees the reason and can **raise the request again** (leave: *Apply again*). Each approval level gets its own time.
  - **Remind** button on *Approval delays* (HR): the automatic-rejection clock then counts from that reminder; the page shows each item's next step and its automatic-rejection date.
  - **Multi-level approval** for requests and leave, off by default: levels by reporting manager, manager's manager, a named user, HR or management; a level can apply only from an amount or number of days; levels with nobody to ask are skipped. The chain is shown on the request, the leave and in Approvals.
  - **After a rejection**, the policy decides whether the request raised again **starts from the first level** or **resumes at the level that rejected** (earlier approvals kept and marked).
  - *Try it*: which policy applies to an employee and who approves, level by level. Two switched-off examples are added.
- Rejecting asks for a reason; the employee sees it on the request.
- **Fix:** managers whose user is limited to their own Employee record (HRMS default) now see their team's AlphaX requests in Approvals.

## 0.23.0 — 2026-11-05

- **Attendance devices** (new page for HR): connect fingerprint and face devices of any brand.
  - **ZKTeco and other ADMS/iClock devices** send punches straight to AlphaX (Cloud Server setting on the device); unknown devices wait for HR approval; optional allowed IP addresses; device users, model and last contact shown; commands: upload all logs again, send employees to the device, read device info, reboot.
  - **Push API** with a per-device token for Hikvision event push, Suprema, Anviz, Dahua or a local bridge.
  - **Database pull** from ZKTeco BioTime, ZKTime / ZKAccess or your own table (MySQL/MariaDB, PostgreSQL, SQL Server), every few minutes, with *Test connection* and *Pull now*.
  - **Log file import** (attlog.dat from USB, CSV).
  - Every punch is kept as a device log, matched by attendance device ID, Employee ID or Iqama, turned into an Employee Checkin (IN/OUT from the device or by rule, time offset per device), duplicates skipped; *Unmatched users* links a device user to an employee in one click and imports their punches.
- **Fix:** "no loan being repaid" hint shown in Arabic.

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
