import os, json, re, ast, collections, sys
root = sys.argv[1]  # .../CentralHrms-main
app = os.path.join(root, "centralhrms")
inv = {"doctypes": [], "workflows": [], "reports": [], "pages": [], "print_formats": [], "custom_fields": {}, "property_setters": {}, "notifications": [], "workspaces": []}
refcount = collections.Counter()
alltext = []
for dp, _, fs in os.walk(app):
    for f in fs:
        p = os.path.join(dp, f)
        if f.endswith((".py", ".js")) and "/public/ui_assets" not in p:
            try: alltext.append(open(p, encoding="utf-8", errors="ignore").read())
            except: pass
blob = "\n".join(alltext)
for dp, _, fs in os.walk(app):
    base = os.path.basename(dp)
    for f in fs:
        if not f.endswith(".json"): continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, app)
        try: d = json.load(open(p))
        except Exception: continue
        if isinstance(d, dict) and d.get("doctype") == "DocType" and f == base + ".json" and "/doctype/" in p:
            mod_dir = rel.split("/")[0] if rel.split("/")[0] != "centralhrms" else "centralhrms"
            fields = d.get("fields", [])
            links = sorted({x.get("options") for x in fields if x.get("fieldtype") in ("Link", "Table", "Table MultiSelect") and x.get("options")})
            py = os.path.join(dp, base + ".py")
            pysrc = open(py).read() if os.path.exists(py) else ""
            methods = re.findall(r"def (\w+)\(", pysrc)
            name = d["name"]
            refs = len(re.findall(re.escape(f'"{name}"'), blob)) + len(re.findall(re.escape(f"'{name}'"), blob))
            inv["doctypes"].append({"name": name, "module": d.get("module"), "path": rel, "istable": d.get("istable", 0),
                "issingle": d.get("issingle", 0), "submittable": d.get("is_submittable", 0), "nfields": len([x for x in fields if x.get("fieldtype") not in ("Section Break","Column Break","Tab Break")]),
                "fieldnames": [x["fieldname"] for x in fields if x.get("fieldtype") not in ("Section Break","Column Break","Tab Break","HTML")][:60],
                "links": links, "py_lines": pysrc.count("\n"), "methods": [m for m in methods if not m.startswith("_")][:25], "code_refs": refs,
                "description": (d.get("description") or "")[:200]})
        elif "/report/" in p and f == base + ".json" and isinstance(d, dict) and d.get("doctype") == "Report":
            pyp = os.path.join(dp, base + ".py")
            inv["reports"].append({"name": d["name"], "type": d.get("report_type"), "ref_doctype": d.get("ref_doctype"), "module": d.get("module"),
                                   "py_lines": open(pyp).read().count("\n") if os.path.exists(pyp) else 0})
        elif "/page/" in p and f == base + ".json" and isinstance(d, dict) and d.get("doctype") == "Page":
            pyp = os.path.join(dp, base + ".py"); jsp = os.path.join(dp, base + ".js")
            inv["pages"].append({"name": d["name"], "title": d.get("title"), "roles": [r.get("role") for r in d.get("roles", [])],
                                 "py_lines": open(pyp).read().count("\n") if os.path.exists(pyp) else 0, "js_lines": open(jsp).read().count("\n") if os.path.exists(jsp) else 0})
        elif "/print_format/" in p and isinstance(d, dict) and d.get("doctype") == "Print Format":
            inv["print_formats"].append({"name": d["name"], "doc_type": d.get("doc_type")})
        elif "/notification/" in p and isinstance(d, dict) and d.get("doctype") == "Notification":
            inv["notifications"].append({"name": d["name"], "document_type": d.get("document_type"), "event": d.get("event"), "subject": d.get("subject")})
        elif "/workspace/" in p and isinstance(d, dict) and d.get("doctype") == "Workspace":
            inv["workspaces"].append(d["name"])
        elif rel.startswith("centralhrms/custom/") or "/custom/" in rel:
            if isinstance(d, dict) and "custom_fields" in d:
                dt = d.get("doctype")
                inv["custom_fields"][dt] = [{"fieldname": c["fieldname"], "label": c.get("label"), "fieldtype": c.get("fieldtype"), "options": c.get("options"), "reqd": c.get("reqd")} for c in d["custom_fields"]]
                inv["property_setters"][dt] = [{"field": ps.get("field_name"), "property": ps.get("property"), "value": ps.get("value")} for ps in d.get("property_setters", [])]
wf = json.load(open(os.path.join(app, "fixtures", "workflow.json")))
for w in wf:
    inv["workflows"].append({"name": w["name"], "doctype": w["document_type"], "states": [s["state"] for s in w.get("states", [])],
                             "transitions": [f'{t["state"]} -[{t["action"]} by {t["allowed"]}]-> {t["next_state"]}' for t in w.get("transitions", [])]})
json.dump(inv, open(sys.argv[2], "w"), indent=1)
print("doctypes", len(inv["doctypes"]), "reports", len(inv["reports"]), "pages", len(inv["pages"]), "print", len(inv["print_formats"]),
      "notifications", len(inv["notifications"]), "custom dt", len(inv["custom_fields"]), "cf total", sum(len(v) for v in inv["custom_fields"].values()), "workflows", len(inv["workflows"]))
