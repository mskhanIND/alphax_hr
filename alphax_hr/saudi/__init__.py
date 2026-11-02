"""Saudi HR rules engine.

Pure Python: no Frappe imports, so every rule can be unit-tested in isolation
and reused by the API layer, scheduled jobs and reports.

Every rule that changes over time is *date-effective*: callers always pass the
date the rule applies to (payroll period end, exit date, leave date ...).
Statutory values are defaults only — the site can override them through
AlphaX HR Settings / GOSI Contribution Rate records.
"""
