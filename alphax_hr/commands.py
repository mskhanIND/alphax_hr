"""`bench alphax-update`: update AlphaX HR in one step and check that it really took.

After `git pull` the screens change at once, but the server keeps running the old code until it is restarted, and new
fields exist only after `migrate`. This command does every step in order and then asks the running web server which
version it serves, so a missed restart is reported instead of discovered by users.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import click

APP = "alphax_hr"


def _bench_path():
	from frappe.utils import get_bench_path

	return get_bench_path()


def _run(cmd, cwd, dry=False, check=True):
	click.secho("$ " + " ".join(cmd), fg="cyan")
	if dry:
		return 0, ""
	p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
	out = (p.stdout or "") + (p.stderr or "")
	if out.strip():
		click.echo(out.strip()[-4000:])
	if check and p.returncode:
		raise click.ClickException(f"Step failed ({p.returncode}): {' '.join(cmd)}")
	return p.returncode, out


def _code_version(bench):
	text = open(os.path.join(bench, "apps", APP, APP, "__init__.py")).read()
	m = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
	return m.group(1) if m else None


def _sites_with_app(bench):
	sites_dir = os.path.join(bench, "sites")
	out = []
	for name in sorted(os.listdir(sites_dir)):
		if os.path.isfile(os.path.join(sites_dir, name, "site_config.json")):
			out.append(name)
	return out


def _site_has_app(bench, site):
	code, out = _run(["bench", "--site", site, "list-apps"], bench, check=False)
	return code == 0 and re.search(rf"^\s*{APP}\b", out, re.M) is not None


def _served_version(bench, site):
	"""Ask the running web server (not this process) which version it serves."""
	conf = {}
	try:
		conf = json.load(open(os.path.join(bench, "sites", "common_site_config.json")))
	except Exception:  # noqa: BLE001
		pass
	port = conf.get("webserver_port") or 8000
	for url, host in ((f"http://127.0.0.1:{port}", site), (f"https://{site}", None), (f"http://{site}", None)):
		try:
			req = urllib.request.Request(f"{url}/api/method/alphax_hr.api.ops.version", headers={"Host": host} if host else {})
			with urllib.request.urlopen(req, timeout=8) as r:
				return json.loads(r.read().decode()).get("message", {}).get("version")
		except Exception:  # noqa: BLE001
			continue
	return None


@click.command("alphax-update")
@click.option("--site", "sites", multiple=True, help="Site(s) to migrate. Default: every site with AlphaX HR.")
@click.option("--no-pull", is_flag=True, help="Use the code already in apps/alphax_hr.")
@click.option("--no-restart", is_flag=True, help="Do not restart (e.g. Docker: restart the containers yourself).")
@click.option("--dry-run", is_flag=True, help="Show the steps without running them.")
def alphax_update(sites, no_pull, no_restart, dry_run):
	"""Update AlphaX HR: pull, migrate, build, restart, then check the running version."""
	bench = _bench_path()
	app_dir = os.path.join(bench, "apps", APP)
	before = _code_version(bench)
	click.secho(f"AlphaX HR {before} in {app_dir}", bold=True)
	if not no_pull:
		_run(["git", "-C", app_dir, "pull", "--ff-only"], bench, dry_run)
	after = before if dry_run else _code_version(bench)
	click.secho(f"Code version now {after}", bold=True)
	_run([os.path.join(bench, "env", "bin", "pip"), "install", "-q", "-e", app_dir], bench, dry_run, check=False)
	targets = list(sites) or [s for s in _sites_with_app(bench) if dry_run or _site_has_app(bench, s)]
	if not targets:
		raise click.ClickException("No site with AlphaX HR found. Use --site.")
	for s in targets:
		_run(["bench", "--site", s, "migrate"], bench, dry_run)
	code, _out = _run(["bench", "build", "--app", APP], bench, dry_run, check=False)
	if code:
		click.secho("Asset build did not finish. AlphaX screens ship ready-built, so this is usually harmless; run "
					"'bench build' later if desk pages look old.", fg="yellow")
	if no_restart:
		click.secho("Not restarted (--no-restart): restart the web and worker processes now.", fg="yellow")
	else:
		code, _out = _run(["bench", "restart"], bench, dry_run, check=False)
		if code:
			click.secho("bench restart failed. Try: sudo supervisorctl restart all  (or restart your containers / "
						"systemd services)", fg="yellow")
	if dry_run:
		return
	time.sleep(4)
	bad = []
	for s in targets:
		served = _served_version(bench, s)
		if served == after:
			click.secho(f"✓ {s} serves {served}", fg="green")
		elif served is None:
			click.secho(f"? {s}: could not reach the web server to check; open the site and look for the update banner.", fg="yellow")
		else:
			bad.append(s)
			click.secho(f"✗ {s} still serves {served}, expected {after}: the web server was not restarted.", fg="red")
	if bad:
		sys.exit(1)


commands = [alphax_update]
