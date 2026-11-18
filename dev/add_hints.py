"""Add type hints to untyped parameters of @frappe.whitelist functions (Frappe semgrep rule)."""
import ast, sys, pathlib

S = "str"
NUM = "int | str"          # flags / counts: callers send 1, "1" or true; code uses cint()
AMT = "float | str"        # amounts: code uses flt()
JSON = "str | dict | list" # JSON strings or parsed objects; code uses parse_json()
ANY = "Any"
STRS = set("""name company month employee department reason doctype run date from_date status to_date file_format
leave_type violation_type action start_date end_date search user request_type kind cycle exit_date loan_type account
posting_date mode txt half_day_date shift_type description violation_date payroll_date field note comment remarks
first_month paid_by saudi_nationality event_date relation log_type explanation expense_type expense_date discovered_on
source_ref reply modified site_field file_url paid_on category scope_type scope_value step salary_component when lang
endpoint gosi_registration_date text key end""".split())
NUMS = set("""limit start half_day include_disabled dry_run consent apply overdue enabled make_default installments months
issue replace page_length override submitted_only is_saudi unpaid_days days year idx helpful saudi""".split())
AMTS = set("amount monthly_wage other_earnings other_deductions daily_hours latitude longitude accuracy leave_days".split())
JSONS = set("""data employees filters ratings details rows reflections goals feedback row changes extra advances periods
weekdays rules package subscription device""".split())

def kind(arg):
    n = arg.arg
    if n == "_check": return "bool"
    if n in STRS: return S
    if n in NUMS: return NUM
    if n in AMTS: return AMT
    if n in JSONS: return JSON
    return ANY

def main(root):
    for p in pathlib.Path(root).rglob("*.py"):
        if "public" in p.parts: continue
        src = p.read_text(); tree = ast.parse(src); lines = src.splitlines(keepends=True)
        edits = []; used_any = False
        for n in ast.walk(tree):
            if not (isinstance(n, ast.FunctionDef) and any("whitelist" in ast.unparse(d) for d in n.decorator_list)):
                continue
            a = n.args; pos = a.args; ds = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
            for arg, d in list(zip(pos, ds)) + list(zip(a.kwonlyargs, a.kw_defaults)):
                if arg.annotation is not None or arg.arg in ("self", "cls"): continue
                t = kind(arg); used_any |= t == ANY
                if isinstance(d, ast.Constant) and d.value is None: t += " | None"
                edits.append((arg.end_lineno, arg.end_col_offset, ": " + t))
        if not edits: continue
        for ln, col, txt in sorted(edits, reverse=True):
            s = lines[ln - 1]; b = s.encode()[:col].decode(); lines[ln - 1] = b + txt + s[len(b):]
        out = "".join(lines)
        if used_any and "from typing import Any" not in out:
            t2 = ast.parse(out); body = t2.body; i = 0
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant): i = 1
            ins = body[i].lineno - 1 if i < len(body) else 0
            ol = out.splitlines(keepends=True); ol.insert(ins, "from typing import Any\n\n" if i == 0 and False else "from typing import Any\n"); out = "".join(ol)
        p.write_text(out); print(p, len(edits))
main(sys.argv[1])
