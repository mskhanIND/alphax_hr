# Development and test tools

Scripts used to build the local test bench and run the test suites. Kept here so the setup can be rebuilt
after a machine or workspace reset. Paths assume the code at `/home/claude/alphax_hr` and the bench at
`/home/claude/frappe-bench`; adjust if different.

| Script | Purpose |
|---|---|
| `setup_bench.sh` (+2, +3) | Build a Frappe v15 bench with ERPNext + HRMS and the site `hr.test`. Needs `DB_ROOT_PASSWORD` and `ADMIN_PASSWORD` set in the environment (local throwaway values). |
| `sync_install.sh` | Copy this repo into the bench and install the app on `hr.test`. |
| `up.sh` | Start MariaDB, Redis and the bench web server after a restart. |
| `itest.sh [lines]` | Sync, migrate and run `tests/integration/run_frappe_tests.py` (server tests). |
| `e2e.sh` | Sync, clean leftovers (`e2eclean.py`), run the Playwright browser tests in `tests/e2e/smoke.mjs`. Run `npm run build` in `frontend/` first. |
| `seed_demo.py` | Demo data. |
| `add_ar.py file.json` | Add Arabic strings to `frontend/src/lib/i18n.tsx`. |
| `gen_doctypes.py`, `inventory.py` | Generators and inventory helpers used while building DocTypes. |
| `hint_scan.py`, `add_hints.py`, `wl_scan.py`, `nosemgrep.py` | Code scans (hints, whitelisted methods, semgrep exceptions). |

Release routine: bump `alphax_hr/__init__.py` and `frontend/package.json`, CHANGELOG entry, `npm run build`,
both suites green, commit, tag `vX.Y.Z`, push `main` and `main:version-15` and the tag.
