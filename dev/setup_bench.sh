set -x
export DEBIAN_FRONTEND=noninteractive
sudo apt-get install -y -qq mariadb-server mariadb-client libmariadb-dev pkg-config wkhtmltopdf cron >/dev/null 2>&1 || sudo apt-get install -y -qq mariadb-server mariadb-client libmariadb-dev pkg-config
sudo bash -c 'cat > /etc/mysql/mariadb.conf.d/99-frappe.cnf <<CNF
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
[mysql]
default-character-set = utf8mb4
CNF'
sudo service mariadb start || (sudo mysqld_safe >/dev/null 2>&1 &) ; sleep 5
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'root'; FLUSH PRIVILEGES;" || sudo mysql -uroot -proot -e "select 1"
(redis-server --daemonize yes --port 6379)
npm i -g yarn >/dev/null 2>&1
python3 -m venv /home/claude/benchenv && /home/claude/benchenv/bin/pip install -q frappe-bench
export PATH=/home/claude/benchenv/bin:$PATH
cd /home/claude && bench init --frappe-branch version-15 --skip-redis-config-generation --skip-assets --python $(which python3.12 || which python3.11 || which python3) frappe-bench
cd /home/claude/frappe-bench
bench set-config -g redis_cache redis://127.0.0.1:6379
bench set-config -g redis_queue redis://127.0.0.1:6379
bench set-config -g redis_socketio redis://127.0.0.1:6379
bench get-app --branch version-15 --skip-assets erpnext
bench get-app --branch version-15 --skip-assets hrms
bench new-site hr.test --db-root-password "${DB_ROOT_PASSWORD:?set DB_ROOT_PASSWORD}" --admin-password "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}" --install-app erpnext
bench --site hr.test install-app hrms
echo BENCH_DONE
