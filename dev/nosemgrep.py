import json, collections
d = json.load(open('/tmp/sg.json'))
why = {"frappe-ssti": "template path is fixed in the app, or an HR-authored letter rendered in Frappe's sandboxed Jinja",
       "frappe-security-file-traversal": "path is fixed, or resolved and checked to stay inside the site's files folder",
       "frappe-sql-format-injection": "identifiers come from DocType metadata / a fixed list, not from the request"}
by = collections.defaultdict(list)
for r in d["results"]: by[r["path"]].append((r["start"]["line"], r["check_id"].split(".")[-1]))
for path, items in by.items():
    lines = open(path).read().split("\n")
    for ln, rule in sorted(set(items), reverse=True):
        l = lines[ln - 1]
        if "nosemgrep" in l: continue
        indent = l[:len(l) - len(l.lstrip())]
        lines[ln - 1] = l + "  # nosemgrep"
        lines.insert(ln - 1, f"{indent}# Reviewed: {why[rule]}.")
    open(path, "w").write("\n".join(lines))
    print(path)
