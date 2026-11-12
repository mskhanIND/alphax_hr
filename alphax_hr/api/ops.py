"""Version and update status: which code runs, whether migrate ran, whether a newer version exists, and (only where the
server owner allowed it in site_config with "alphax_web_update": 1) starting `bench alphax-update` from the app."""
from __future__ import annotations

import os
import re
import subprocess
import urllib.request

import frappe
from frappe import _

import alphax_hr

REPO_RAW = "https://raw.githubusercontent.com/mskhanIND/alphax_hr/{branch}/alphax_hr/__init__.py"
LOG = "alphax-update.log"


@frappe.whitelist(allow_guest=True, methods=["GET"])
def version():
	"""The version this web server runs (used by `bench alphax-update` to confirm a restart). Version only."""
	return {"version": alphax_hr.__version__}


def _migrated():
	return frappe.db.get_value("Installed Application", {"app_name": "alphax_hr"}, "app_version")


def _parse(v):
	return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def latest(force=False):
	"""The newest version on the update branch (cached 6 hours; None when it cannot be checked)."""
	key = "alphax:latest_version"
	if not force:
		hit = frappe.cache().get_value(key)
		if hit is not None:
			return hit or None
	branch = frappe.conf.get("alphax_update_branch") or "version-15"
	found = ""
	try:
		with urllib.request.urlopen(REPO_RAW.format(branch=branch), timeout=6) as r:
			m = re.search(r'__version__\s*=\s*["\']([^"\']+)', r.read().decode())
			found = m.group(1) if m else ""
	except Exception:  # noqa: BLE001  offline servers just do not get the hint
		found = ""
	frappe.cache().set_value(key, found, expires_in_sec=6 * 3600)
	return found or None


@frappe.whitelist()
def status():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can see update status."), frappe.PermissionError)
	running, migrated, newest = alphax_hr.__version__, _migrated(), latest()
	return {"running": running, "migrated": migrated, "latest": newest,
			"migrate_pending": bool(migrated and migrated != running),
			"update_available": bool(newest and _parse(newest) > _parse(running)),
			"web_update": bool(frappe.conf.get("alphax_web_update")), "log": _tail(),
			"command": f"bench alphax-update --site {frappe.local.site}"}


def _log_path():
	from frappe.utils import get_bench_path

	return os.path.join(get_bench_path(), "logs", LOG)


def _tail(lines=40):
	try:
		with open(_log_path()) as f:
			return "".join(f.readlines()[-lines:])
	except Exception:  # noqa: BLE001
		return None


@frappe.whitelist(methods=["POST"])
def start_update():
	"""Run `bench alphax-update` for this site in the background, if the server owner allowed it."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can update the app."), frappe.PermissionError)
	if not frappe.conf.get("alphax_web_update"):
		frappe.throw(_("Updating from the app is turned off on this server. Run {0} on the server, or add "
					   '"alphax_web_update": 1 to site_config.json to allow it.').format(
			f"bench alphax-update --site {frappe.local.site}"))
	from frappe.utils import get_bench_path

	bench = get_bench_path()
	with open(_log_path(), "w") as log:
		log.write(f"Update started by {frappe.session.user} at {frappe.utils.now()}\n")
	# detached, so the restart at the end does not stop it
	subprocess.Popen(f"bench alphax-update --site {frappe.local.site} >> {_log_path()} 2>&1", shell=True, cwd=bench,
					 start_new_session=True, stdin=subprocess.DEVNULL)  # nosec  # fixed command, site name from Frappe
	return {"started": True}
