# Report a problem: connecting a site

Every AlphaX HR page has a **Report a problem** button. Reports are always saved on the site
(AlphaX Feedback, visible to HR managers under Services → My reports → Everyone).

To also send each report to the development team as a ticket (with the screenshot), connect the
site to a **private** GitHub repository once.

## 1. Repository and key (once)

1. On GitHub create a private repository, e.g. `alphax-hr-feedback` (empty is fine; tick *Add a README*).
2. GitHub → Settings → Developer settings → Fine-grained tokens → *Generate new token*:
   - Repository access: **Only select repositories** → `alphax-hr-feedback`
   - Permissions: **Issues: Read and write**, **Contents: Read and write** (nothing else)
   - Expiry: as your policy allows (renew it before it expires).

The key can only touch that one repository. It cannot read or change the AlphaX HR code.

## 2. Each test site (on the server)

```bash
cd ~/frappe-bench
bench --site <site> set-config alphax_feedback_repo "mskhanIND/alphax-hr-feedback"
bench --site <site> set-config alphax_feedback_token "<paste the token here>"
```

Type the token only on the server. Do not put it in chat, e-mail or the code.

Nothing else is needed: new reports are sent at once, older ones within the hour.

## Replying (development team)

On the GitHub issue: write a comment (it appears in the tester's *My reports*) and set a label:
`question` (tester can answer), `in-progress`, `retest` (shows *Fixed - please check* with Pass / Fail),
`not-a-bug` (Answered). Close the issue when done. A tester's Pass closes it; a Fail reopens it
with the label `reopened`.

## Privacy

Screenshots show what was on the user's screen. Users can untick the picture before sending.
Keep the repository private and limit who can see it.
