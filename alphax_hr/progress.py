"""Progress of long HR jobs (assign shifts and import, update past days, read missing punches) so the screen can show
what is happening: step, how far, elapsed, and whether it seems stuck.

A job is kept in the cache under its key for a day: {status, title, step, done, total, started, beat, finished, result,
error}. ``beat`` is renewed on every update; the screen warns when it has not moved for a while.
"""
from __future__ import annotations

import frappe
from frappe.utils import now_datetime

TTL = 24 * 3600


def _key(job):
	return f"alphax:job:{job}"


def get(job):
	return frappe.cache().get_value(_key(job), expires=True)  # always from Redis: other processes write it


def _put(job, data):
	frappe.cache().set_value(_key(job), data, expires_in_sec=TTL)


def start(job, title, total=0, step=None, user=None):
	now = str(now_datetime())
	_put(job, {"job": job, "title": title, "status": "queued", "step": step, "done": 0, "total": total, "started": now,
			   "beat": now, "finished": None, "result": None, "error": None, "user": user or frappe.session.user})


def update(job, step=None, done=None, total=None, status="running"):
	data = get(job) or {"job": job, "title": job, "started": str(now_datetime())}
	data.update({"status": status, "beat": str(now_datetime())})
	if step is not None:
		data["step"] = step
	if done is not None:
		data["done"] = done
	if total is not None:
		data["total"] = total
	_put(job, data)


def finish(job, result=None, error=None):
	data = get(job) or {"job": job, "title": job, "started": str(now_datetime())}
	now = str(now_datetime())
	data.update({"status": "failed" if error else "done", "finished": now, "beat": now, "result": result,
				 "error": (str(error)[:500] if error else None)})
	if not error and data.get("total"):
		data["done"] = data["total"]
	_put(job, data)


def run(job, fn, *args, **kwargs):
	"""Run ``fn`` reporting into ``job``; used as the background entry point."""
	update(job, status="running")
	try:
		result = fn(*args, progress=lambda step=None, done=None, total=None: update(job, step, done, total), **kwargs)
		frappe.db.commit()
		finish(job, result=result)
		return result
	except Exception as exc:  # noqa: BLE001
		frappe.db.rollback()
		frappe.log_error(title=f"AlphaX job {job}")
		finish(job, error=frappe.utils.strip_html(str(exc)) or type(exc).__name__)
		raise


def launch(job, title, method, total=0, background=True, **kwargs):
	"""Start a job in the background (or now, when ``background`` is false) and return its first state."""
	current = get(job)
	if current and current.get("status") in ("queued", "running") and background:
		return current  # already going: the screen follows the same job
	start(job, title, total)
	if not background or frappe.flags.in_test:
		fn = frappe.get_attr(method)
		run(job, fn, **kwargs)
		return get(job)
	try:  # "target", not "method": enqueue() has its own "method" argument
		frappe.enqueue("alphax_hr.progress.run_method", queue="long", timeout=7200, job_id=f"alphax-{job}", deduplicate=True,
					   enqueue_after_commit=True, job=job, target=method, params=kwargs)
	except Exception as exc:  # noqa: BLE001  never leave a job "waiting" that will not run
		finish(job, error=frappe.utils.strip_html(str(exc)))
		raise
	return get(job)


def run_method(job, target, params=None):
	return run(job, frappe.get_attr(target), **(params or {}))


@frappe.whitelist()
def status(job: str):
	from alphax_hr.api._common import require_hr

	require_hr()
	data = get(job)
	if data:  # seconds worked out here, so the browser's time zone does not matter
		from frappe.utils import get_datetime

		now = now_datetime()
		end = get_datetime(data["finished"]) if data.get("finished") else now
		data["elapsed"] = max(0, int((end - get_datetime(data["started"])).total_seconds()))
		data["quiet"] = max(0, int((now - get_datetime(data.get("beat") or data["started"])).total_seconds()))
		data["waiting"] = data["elapsed"] if data.get("status") == "queued" else 0
	return data
