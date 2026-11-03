# Frappe Cloud Marketplace listing — AlphaX HR

Copy these values into the app's listing on Frappe Cloud (Dashboard → Apps → AlphaX HR → Listing).

| Field | Value |
|---|---|
| App name (unique) | `alphax_hr` |
| Title | AlphaX HR |
| Category | Human Resources |
| Logo | `docs/marketplace/logo.png` (512 × 512, square, no text) |
| Short description (40–80 chars) | Saudi-ready HR self-service, leave, payroll and attendance for Frappe HRMS |
| Repository | https://github.com/mskhanIND/alphax_hr |
| Branch for v15 | `version-15` |
| Supported versions | Frappe / ERPNext / HRMS v15 |
| Website | https://neotec.ai |
| Support | https://github.com/mskhanIND/alphax_hr/issues |
| Documentation | https://github.com/mskhanIND/alphax_hr#readme |
| Privacy policy | https://github.com/mskhanIND/alphax_hr/blob/main/PRIVACY.md |
| Terms of service | https://github.com/mskhanIND/alphax_hr/blob/main/license.txt (MIT) |
| Contact e-mail | support@neotec.ai |
| Demo video | _record and upload a 2–4 minute walkthrough (see the script below)_ |

The short description is 74 characters.

## Long description

AlphaX HR gives employees, managers and HR one modern, bilingual (English / Arabic) workspace on top of Frappe HRMS
and ERPNext. Everything is stored in the standard HRMS and ERPNext records — leave applications, attendance, salary
slips, expense claims, journal entries — so reports, workflows and permissions keep working.

**For employees (web and phone app)**
- Apply for leave and see the counted days and balance before applying
- Check in and out with location rules, request attendance corrections and late/early permissions
- Payslips as PDF, loans and salary advances, expense claims with receipt photos
- Letters, document requests and profile updates through HR, with a message thread
- Phone and browser notifications; installable as an app on Android and iPhone

**For managers**
- One approvals inbox for leave, expenses, attendance, shifts and requests
- Team view: who is in, late or on leave today; team calendar; vacation planner

**For HR**
- People directory, organisation chart, new-employee wizard and bulk updates
- Leave policies: counting rules, sandwich rule, statutory Saudi leave types, annual allocation
- Shifts, roster, attendance register and overtime (Art. 107)
- Payroll control centre by company, department, branch or employee, with checklists and a bank salary file (WPS)
- Loans, advances, bonuses and deductions within Saudi Labor Law limits (Art. 91–93)
- Penalties based on the labour-law violation schedule
- End-of-service calculation (Art. 84/85/87) and final settlements
- Monthly accruals for end of service and annual leave posted as a journal entry
- Appraisals by performance cycle or on request, with management approval
- GOSI contributions (legacy and new system), Iqama and document expiry, Nitaqat estimate
- Your own app name and logo; choose which pages each role sees

**Portal mode (optional).** Keep employees and HR out of the Desk: they always land in AlphaX, while accounting and
system users keep the Desk. An optional branded sign-in page is available.

Requires Frappe, ERPNext and Frappe HRMS v15. No other apps are needed.

## Screenshots (upload in this order)

1. `docs/screenshots/09-hr-home.png` — HR home
2. `docs/screenshots/01-employee-home.png` — employee home
3. `docs/screenshots/05-arabic-phone-home.png` — Arabic on a phone
4. `docs/screenshots/07-approvals.png` — approvals inbox
5. `docs/screenshots/23-payroll-control.png` — payroll control centre
6. `docs/screenshots/35-accruals.png` — monthly accruals
7. `docs/screenshots/23d-loans.png` — loans
8. `docs/screenshots/34-checkins.png` — check-ins and movements
9. `docs/screenshots/ar-compliance.png` — compliance in Arabic
10. `docs/screenshots/36-sign-in.png` — sign-in page

## Demo video script (2–4 minutes)

1. Sign-in page, switch to Arabic and back (10 s)
2. Employee: check in, apply for leave (counted days shown), open a payslip (40 s)
3. Manager: approve the leave from the inbox, team view (30 s)
4. HR: people list and org chart, leave setup, payroll control centre for one department, bank salary file (60 s)
5. HR: accruals for the month, final settlement for a leaver (30 s)
6. Settings: app name and logo, portal mode, page access (20 s)

## Pre-submission checklist

- [x] Open source (MIT) on GitHub, unique app name `alphax_hr`
- [x] Installs on a fresh site with only frappe, erpnext and hrms (CI does exactly this)
- [x] CI passing: `.github/workflows/ci.yml` (unit, integration, browser E2E) and `linters.yml` (Frappe Semgrep rules, ruff, dependency audit)
- [x] Settings DocType (*AlphaX HR Settings*)
- [x] Does not override Frappe's `/login`: the AlphaX sign-in page lives at `/alphax-login` and replacing `/login` is an opt-in setting, off by default
- [x] Square logo without text, screenshots, short and long description, privacy policy, support link
- [ ] Demo video recorded and uploaded
- [ ] Frappe Cloud developer account, app added from GitHub, `version-15` source linked, release published for review
