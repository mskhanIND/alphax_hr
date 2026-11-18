#!/bin/bash
# sync, clean leftovers, run the browser tests, clean again
sudo rsync -a --exclude node_modules --exclude .git --exclude '*.egg-info' /home/claude/alphax_hr/ /home/claude/frappe-bench/apps/alphax_hr/ && sudo chown -R claude:claude /home/claude/frappe-bench/apps/alphax_hr
cd /home/claude/frappe-bench
sudo cp /home/claude/alphax_hr/dev/e2eclean.py apps/alphax_hr/alphax_hr/dbg.py && sudo chown claude apps/alphax_hr/alphax_hr/dbg.py
sudo -u claude -H bash /home/claude/tools/b.sh bench --site hr.test execute alphax_hr.dbg.run >/dev/null 2>&1
sudo rm -rf /tmp/screens
sudo -u claude -H bash -c 'cd /home/claude/frappe-bench && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers NODE_PATH=$(npm root -g) timeout 1000 node apps/alphax_hr/tests/e2e/smoke.mjs http://hr.test:8000 /tmp/screens' 2>&1 | grep -E "FAIL|passed|failed" | tail -8
sudo -u claude -H bash /home/claude/tools/b.sh bench --site hr.test execute alphax_hr.dbg.run >/dev/null 2>&1
sudo rm -f apps/alphax_hr/alphax_hr/dbg.py
