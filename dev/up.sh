#!/bin/bash
pgrep mariadbd >/dev/null || (sudo mysqld_safe > /dev/null 2>&1 &)
pgrep redis-server >/dev/null || redis-server --daemonize yes >/dev/null
grep -q hr.test /etc/hosts || echo "127.0.0.1 hr.test" | sudo tee -a /etc/hosts >/dev/null
for i in $(seq 1 20); do mysqladmin ping >/dev/null 2>&1 && break; sudo mysqladmin ping >/dev/null 2>&1 && break; sleep 1; done
if ! curl -s -o /dev/null --max-time 5 http://hr.test:8000/api/method/ping; then
  sudo -u claude -H bash -c 'source /tmp/proxyenv.sh 2>/dev/null; export HOME=/home/claude PATH=/home/claude/benchenv/bin:/opt/node22/bin:/usr/local/bin:/usr/bin:/bin; cd /home/claude/frappe-bench && (nohup bench serve --port 8000 > /home/claude/serve.log 2>&1 &)'
  for i in $(seq 1 30); do curl -s -o /dev/null --max-time 3 http://hr.test:8000/api/method/ping && break; sleep 2; done
fi
curl -s -o /dev/null -w "site %{http_code}\n" --max-time 10 http://hr.test:8000/api/method/ping
