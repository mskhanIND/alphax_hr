# AlphaX HR — Privacy Policy

_Last updated: 3 November 2026_

AlphaX HR is an open-source Frappe app published by Neotec Integrated Solutions ("Neotec", "we"). It is installed on
your own Frappe / ERPNext / Frappe HRMS site, either on your own servers or on Frappe Cloud. This policy explains what
the app does with personal data.

## Who controls the data

The organisation that runs the site (the employer) is the data controller. AlphaX HR is software running inside that
site. **Neotec does not receive, host or have access to any data in your site** unless you separately ask us for
support and grant us access.

## What the app stores, and where

All data stays in your site's own database and files, in the standard Frappe, ERPNext and HRMS records (Employee, Leave
Application, Attendance, Salary Slip, Expense Claim, Journal Entry and others) plus a few AlphaX records (requests,
loans, penalties, final settlements, accrual runs, settings). This includes employee personal and employment details
such as names, national ID / Iqama numbers, contact details, bank and IBAN, salary, attendance and leave.

The app does not add any analytics, tracking pixels, advertising or third-party scripts.

## Data the app sends out of your site

Only when you turn the feature on, and only to the parties you configure:

| Feature | What is sent | To whom |
|---|---|---|
| E-mail notifications | The notification text (e.g. a leave decision) | Your site's own outgoing e-mail account |
| Phone / browser push notifications | Title, short text and a link | The browser vendor's push service used by the employee's device (Google, Apple, Mozilla, Microsoft), through the standard Web Push protocol, encrypted end to end |
| Check-in with location | The device's GPS position at the moment of check-in | Stored in your site only (Employee Checkin) |
| Bank salary file (WPS) | Nothing is sent: HR downloads the file and uploads it to the bank | — |

## Access control

Every AlphaX API checks the signed-in user's roles on the server. Employees see only their own records; managers see
their team's requests; HR sees what their Frappe roles and User Permissions allow. The sign-in page uses Frappe's own
login, password policy, rate limiting and two-factor authentication.

## Retention and deletion

Records follow your site's own retention. Deleting or anonymising an employee is done with Frappe's standard tools
(including *Personal Data Deletion Request*). Uninstalling the app leaves the standard ERPNext / HRMS records in place.

## Your rights

Employees should contact their employer (the site owner) to access, correct or delete their personal data, for
example under the Saudi Personal Data Protection Law (PDPL).

## Contact

Questions about this policy or about the app: **support@neotec.ai** —
issues: https://github.com/mskhanIND/alphax_hr/issues
