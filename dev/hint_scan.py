import ast, sys, pathlib, collections
c = collections.Counter(); defaults = collections.defaultdict(set)
for p in pathlib.Path(sys.argv[1]).rglob("*.py"):
    if "public" in p.parts: continue
    t = ast.parse(p.read_text())
    for n in ast.walk(t):
        if isinstance(n, ast.FunctionDef) and any("whitelist" in ast.unparse(d) for d in n.decorator_list):
            a = n.args; pos = a.args; ds = [None]*(len(pos)-len(a.defaults)) + list(a.defaults)
            for arg, d in list(zip(pos, ds)) + list(zip(a.kwonlyargs, a.kw_defaults)):
                if arg.annotation is None:
                    c[arg.arg] += 1; defaults[arg.arg].add(ast.unparse(d) if d is not None else "-")
for k, v in c.most_common(): print(v, k, sorted(defaults[k]))
