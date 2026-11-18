set -ex
source /tmp/proxyenv.sh
export PATH=/home/claude/benchenv/bin:/opt/node22/bin:/usr/local/bin:/usr/bin:/bin
export HOME=/home/claude
which yarn || npm i -g --prefix /home/claude/.npm-global yarn
export PATH=/home/claude/.npm-global/bin:$PATH
cd /home/claude
bench init --frappe-branch version-15 --skip-redis-config-generation --skip-assets --python /usr/bin/python3.12 frappe-bench
cd /home/claude/frappe-bench
bench set-config -g redis_cache redis://127.0.0.1:6379
bench set-config -g redis_queue redis://127.0.0.1:6379
bench set-config -g redis_socketio redis://127.0.0.1:6379
bench get-app --branch version-15 --skip-assets erpnext
bench get-app --branch version-15 --skip-assets hrms
bench new-site hr.test --db-root-password "${DB_ROOT_PASSWORD:?set DB_ROOT_PASSWORD}" --admin-password "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}" --install-app erpnext
bench --site hr.test install-app hrms
echo BENCH_DONE
