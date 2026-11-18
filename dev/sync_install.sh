set -e
source /tmp/proxyenv.sh
export HOME=/home/claude PATH=/home/claude/benchenv/bin:/opt/node22/bin:/usr/local/bin:/usr/bin:/bin
cd /home/claude/frappe-bench
if [ ! -d apps/alphax_hr ]; then
  rsync -a --exclude node_modules --exclude .git /home/claude/alphax_hr/ apps/alphax_hr/
  ./env/bin/python -m pip install -q -e apps/alphax_hr
  grep -qx alphax_hr sites/apps.txt || echo alphax_hr >> sites/apps.txt
  bench --site hr.test install-app alphax_hr
else
  rsync -a --delete --exclude node_modules --exclude .git --exclude '*.egg-info' /home/claude/alphax_hr/ apps/alphax_hr/
  bench --site hr.test migrate
fi
bench --site hr.test clear-cache
