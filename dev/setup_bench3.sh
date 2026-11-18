set -ex
source /tmp/proxyenv.sh
export HOME=/home/claude PATH=/home/claude/benchenv/bin:/home/claude/.npm-global/bin:/opt/node22/bin:/usr/local/bin:/usr/bin:/bin
cd /home/claude/frappe-bench
ls sites/apps.txt 2>/dev/null || printf 'frappe\n' > sites/apps.txt
[ -f sites/common_site_config.json ] || echo '{}' > sites/common_site_config.json
bench set-config -g redis_cache redis://127.0.0.1:6379
bench set-config -g redis_queue redis://127.0.0.1:6379
bench set-config -g redis_socketio redis://127.0.0.1:6379
bench set-config -g socketio_port 9000
bench set-config -g webserver_port 8000
for app in erpnext hrms; do
  [ -d apps/$app ] || git clone --depth 1 --branch version-15 https://github.com/frappe/$app apps/$app
  ./env/bin/python -m pip install -q -e apps/$app
  grep -qx $app sites/apps.txt || echo $app >> sites/apps.txt
done
bench new-site hr.test --db-root-password "${DB_ROOT_PASSWORD:?set DB_ROOT_PASSWORD}" --admin-password "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}" --install-app erpnext
bench --site hr.test install-app hrms
bench --site hr.test set-config developer_mode 1
echo BENCH_DONE
