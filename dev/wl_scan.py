import ast,sys,os,collections
root=sys.argv[1]; rows=[]
for dp,_,fs in os.walk(root):
  for f in fs:
    if not f.endswith('.py'): continue
    p=os.path.join(dp,f)
    try: src=open(p,encoding='utf-8').read(); t=ast.parse(src)
    except Exception as e: print('PARSE_FAIL',p,e); continue
    for n in ast.walk(t):
      if isinstance(n,(ast.FunctionDef,)):
        wl=None
        for d in n.decorator_list:
          s=ast.get_source_segment(src,d) or ''
          if 'whitelist' in s: wl=s
        if not wl: continue
        body=ast.get_source_segment(src,n) or ''
        guard=any(k in body for k in ['has_permission','check_permission','only_for','get_roles','require_','_is_hr','is_hr','validate_role','PermissionError','frappe.only_for'])
        writes=any(k in body for k in ['ignore_permissions=True','db.set_value','db.sql("UPDATE','db.sql("DELETE','.insert(','.save(','.submit(','.delete(','delete_doc','db.delete'])
        reads=any(k in body for k in ['frappe.get_all','db.sql','get_list','db.get_value','get_doc('])
        rows.append((os.path.relpath(p,root),n.name,'guest' if 'allow_guest' in wl else '',guard,writes,reads,'ignore_permissions=True' in body))
c=collections.Counter()
for r in rows:
  c['total']+=1
  if not r[3]: c['no_guard']+=1
  if not r[3] and r[4]: c['no_guard_writes']+=1
  if not r[3] and r[6]: c['no_guard_ignore_perms']+=1
print(dict(c))
for r in rows:
  if not r[3] and r[6]: print('  ',r[0],r[1],r[2])
