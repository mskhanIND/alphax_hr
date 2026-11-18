sudo rsync -a --exclude node_modules --exclude .git --exclude '*.egg-info' /home/claude/alphax_hr/ /home/claude/frappe-bench/apps/alphax_hr/ && sudo chown -R claude:claude /home/claude/frappe-bench/apps/alphax_hr
sudo -u claude -H bash /home/claude/tools/b.sh bench --site hr.test migrate >/dev/null 2>&1
sudo -u claude -H bash /home/claude/tools/b.sh bash -c 'cd sites && ../env/bin/python ../apps/alphax_hr/tests/integration/run_frappe_tests.py hr.test' 2>&1 | grep -vE "^\s+File|^\s{4}|^\s+\^" | tail -${1:-60}
