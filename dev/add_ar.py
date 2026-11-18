import json, re, sys
p = '/home/claude/alphax_hr/frontend/src/lib/i18n.tsx'
s = open(p).read()
new = json.load(open(sys.argv[1]))
keys = set(re.findall(r"^\s+'([^']+)':", s, re.M)) | set(re.findall(r'^\s+"([^"]+)":', s, re.M))
add = ''
for k, v in new.items():
    if k in keys:
        continue
    q = '"' if "'" in k or "'" in v else "'"
    add += f"  {q}{k}{q}: {q}{v}{q},\n"
s = s.replace("  'Home': 'الرئيسية',\n", "  'Home': 'الرئيسية',\n" + add, 1)
open(p, 'w').write(s)
print(len(add.splitlines()), 'added')
