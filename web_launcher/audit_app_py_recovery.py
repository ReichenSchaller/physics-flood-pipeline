
#!/usr/bin/env python3

"""

Massive read-only audit for recovered SFINCS web_launcher/app.py.



Compares:

  - active app.py

  - recovered app_recovered_from_good_copy_plus_settings_patch.py



This script does not modify either file.

"""



from __future__ import annotations



import ast

import difflib

import hashlib

import json

import py_compile

import re

import subprocess

import sys

import traceback

from collections import Counter, defaultdict

from dataclasses import dataclass

from pathlib import Path

from typing import Any





WEB_DIR = Path("/proj/zefflab/projects/Flooding/pipeline/web_launcher")



DEFAULT_A = WEB_DIR / "app.py"

DEFAULT_B = WEB_DIR / "app_recovered_from_good_copy_plus_settings_patch.py"



REPORT_PATH = WEB_DIR / "APP_PY_RECOVERY_AUDIT_REPORT.txt"

JSON_PATH = WEB_DIR / "APP_PY_RECOVERY_AUDIT_REPORT.json"





REQUIRED_FUNCTIONS = {

    # launcher defaults / settings-path architecture

    "_read_launcher_site_defaults",

    "_write_launcher_site_defaults",

    "launcher_default_value",

    "split_launcher_path_list",

    "launcher_default_path_root",

    "effective_allowed_roots",

    "configured_project_root_path",

    "configured_run_root_path",

    "configured_project_script_path",

    "configured_runner_python_path",

    "configured_contextily_python_path",



    # safety/path helpers

    "safe_resolve",

    "safe_run_name",

    "is_allowed_path",

    "directory_listing",

    "inspect_run_root",

    "json_error",



    # app/config runner helpers

    "staged_config_path",

    "write_staged_runner_config",

    "run_pipeline_runner",



    # catalog helpers

    "_catalog_path_is_ignored",

    "_catalog_warning",

    "_catalog_path_list_from_config",

    "_catalog_first_top_level_file",

    "_catalog_first_match",

    "_catalog_active_mask_match",

    "_catalog_all_matches",

    "_catalog_has_any",

    "_read_runtime_csv_values",

    "_derive_hydromt_catalog_paths_from_roots",

    "_detect_one_data_catalog",

    "detect_data_catalogs_from_config",



    # runtime/review helpers

    "_review_runtime_normalize_path_list",

    "_review_runtime_normalize_time",

    "_review_runtime_check_from_config",



    # sfincs file detection helpers

    "parse_sfincs_inp_value",

    "sfincs_time_to_launcher_time",

    "parse_sfincs_inp_file",

    "attach_sfincs_inp_parse",

    "iter_files_limited",

    "detect_sfincs_files",

    "detect_sfincs_files_multiple",



    # geometry check helpers/routes

    "_write_staged_geometry_check_config",

    "_manual_geometry_check_command",

    "_geometry_check_optional_sbatch_lines",

    "api_manual_geometry_check_local",

    "api_manual_geometry_check_submit",



    # key API/page routes

    "index",

    "index_html",

    "manual_html",

    "override_html",

    "batch_html",

    "guided_html",

    "guide_html",

    "api_get_launcher_defaults",

    "api_set_launcher_defaults",

    "api_detect_data_catalogs",

    "api_review_runtime_window",

    "api_run_pipeline",

    "api_manual_catalog_native_warning_hyphen",

    "api_manual_catalog_native_warning",

    "api_review_animation_info",

    "api_review_animation_status",

    "api_review_animation_video",

    "api_review_animation_submit",

    "api_review_obs_gauges_status",

    "api_review_obs_gauges_submit",

}



REQUIRED_ROUTES = {

    "/",

    "/index.html",

    "/manual.html",

    "/override.html",

    "/batch.html",

    "/guided.html",

    "/guide.html",

    "/api/launcher-defaults",

    "/api/detect-data-catalogs",

    "/api/detect-manual-catalogs",

    "/api/review-runtime-window",

    "/api/run-pipeline",

    "/api/manual-catalog-native-warning",

    "/api/manual_catalog_native_warning",

    "/api/manual-geometry-check-local",

    "/api/manual-geometry-check-submit",

    "/api/review/animation/info",

    "/api/review/animation/status",

    "/api/review/animation/video",

    "/api/review/animation/submit",

    "/api/review/obs-gauges/status",

    "/api/review/obs-gauges/submit",

}



REQUIRED_LITERAL_TOKENS = {

    "LAUNCHER_DEFAULTS_PATH",

    "LAUNCHER_DEFAULT_KEYS",

    "LAUNCHER_BUILTIN_DEFAULTS",

    "contextilyPython",

    "browseAllowedRoots",

    "projectRoot",

    "runRoot",

    "condaPython",

    "sfincsContainerPath",

    "configured_project_script_path",

    "configured_runner_python_path",

    "configured_contextily_python_path",

}



FORBIDDEN_PATH_TOKENS = {

    "/proj/zefflab/projects/Flooding/Data",

    "/users/e/p/epsilon/Data/Data",

    "/users/e/p/epsilon/Data/kieran_data",

    "/proj/zefflab/projects/Flooding/pipeline/envs",

    "/proj/zefflab/projects/Flooding/sfincs_runs",

    "/work/users/e/p/epsilon/sfincs_runs",

}



MARKDOWN_DAMAGE_TOKENS = {

    "```",

    "from **future** import annotations",

    "Path(**file**)",

    "Flask(\n**name**",

    "**file**",

    "**name**",

    "**future**",

}





@dataclass

class FileAudit:

    path: Path

    exists: bool

    text: str

    lines: list[str]

    sha256: str | None

    size_bytes: int | None

    line_count: int

    nonblank_line_count: int

    compile_ok: bool

    compile_error: str

    ast_ok: bool

    ast_error: str

    tree: ast.AST | None

    functions_ast: dict[str, int]

    classes_ast: dict[str, int]

    calls_ast: Counter

    routes_ast: list[dict[str, Any]]

    functions_regex: dict[str, int]

    routes_regex: list[dict[str, Any]]

    token_counts: dict[str, int]

    forbidden_path_counts: dict[str, int]

    markdown_damage_counts: dict[str, int]

    top_level_assignments: dict[str, int]





def sha256_file(path: Path) -> str:

    h = hashlib.sha256()

    with path.open("rb") as f:

        for chunk in iter(lambda: f.read(1024 * 1024), b""):

            h.update(chunk)

    return h.hexdigest()





def compile_file(path: Path) -> tuple[bool, str]:

    try:

        py_compile.compile(str(path), doraise=True)

        return True, ""

    except Exception:

        return False, traceback.format_exc()





def get_call_name(node: ast.AST) -> str | None:

    if isinstance(node, ast.Name):

        return node.id

    if isinstance(node, ast.Attribute):

        parent = get_call_name(node.value)

        if parent:

            return f"{parent}.{node.attr}"

        return node.attr

    return None





def literal_value(node: ast.AST) -> Any:

    try:

        return ast.literal_eval(node)

    except Exception:

        return None





def parse_routes_from_ast(tree: ast.AST) -> list[dict[str, Any]]:

    routes = []



    for node in ast.walk(tree):

        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

            continue



        for dec in node.decorator_list:

            if not isinstance(dec, ast.Call):

                continue



            dec_name = get_call_name(dec.func) or ""



            is_route = dec_name in {

                "app.route",

                "app.get",

                "app.post",

                "app.put",

                "app.delete",

                "app.patch",

            }



            if not is_route:

                continue



            route_path = ""

            methods = []



            if dec.args:

                route_path = literal_value(dec.args[0]) or ""



            if dec_name == "app.get":

                methods = ["GET"]

            elif dec_name == "app.post":

                methods = ["POST"]

            elif dec_name == "app.put":

                methods = ["PUT"]

            elif dec_name == "app.delete":

                methods = ["DELETE"]

            elif dec_name == "app.patch":

                methods = ["PATCH"]



            for kw in dec.keywords:

                if kw.arg == "methods":

                    val = literal_value(kw.value)

                    if isinstance(val, (list, tuple)):

                        methods = [str(x) for x in val]

                    elif isinstance(val, str):

                        methods = [val]



            routes.append({

                "route": str(route_path),

                "methods": sorted(set(methods)),

                "function": node.name,

                "decorator": dec_name,

                "line": getattr(node, "lineno", None),

            })



    routes.sort(key=lambda x: (x["route"], x["function"], x.get("line") or 0))

    return routes





def parse_regex_functions(text: str) -> dict[str, int]:

    out = {}

    for m in re.finditer(r"(?m)^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):

        out[m.group(1)] = text[:m.start()].count("\n") + 1

    return out





def parse_regex_routes(text: str) -> list[dict[str, Any]]:

    lines = text.splitlines()

    routes = []

    pending = []



    route_re = re.compile(

        r"""@app\.(route|get|post|put|delete|patch)\(\s*(['"])(.*?)\2(?:\s*,\s*methods\s*=\s*(\[[^\]]*\]))?""",

    )

    def_re = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")



    for i, line in enumerate(lines, start=1):

        rm = route_re.search(line)

        if rm:

            decorator_kind = rm.group(1)

            path = rm.group(3)

            methods_text = rm.group(4) or ""

            methods = []

            if decorator_kind == "get":

                methods = ["GET"]

            elif decorator_kind == "post":

                methods = ["POST"]

            elif decorator_kind == "put":

                methods = ["PUT"]

            elif decorator_kind == "delete":

                methods = ["DELETE"]

            elif decorator_kind == "patch":

                methods = ["PATCH"]

            elif methods_text:

                methods = re.findall(r"['\"]([A-Z]+)['\"]", methods_text)

            pending.append({

                "route": path,

                "methods": sorted(set(methods)),

                "decorator": f"app.{decorator_kind}",

                "decorator_line": i,

            })

            continue



        dm = def_re.search(line)

        if dm and pending:

            fn = dm.group(1)

            for item in pending:

                item = dict(item)

                item["function"] = fn

                item["line"] = i

                routes.append(item)

            pending = []



    routes.sort(key=lambda x: (x["route"], x["function"], x.get("line") or 0))

    return routes





def top_level_assignments_from_ast(tree: ast.AST | None) -> dict[str, int]:

    out = {}

    if tree is None:

        return out



    for node in getattr(tree, "body", []):

        targets = []

        if isinstance(node, ast.Assign):

            for t in node.targets:

                if isinstance(t, ast.Name):

                    targets.append(t.id)

        elif isinstance(node, ast.AnnAssign):

            if isinstance(node.target, ast.Name):

                targets.append(node.target.id)



        for name in targets:

            out[name] = getattr(node, "lineno", -1)



    return out





def audit_file(path: Path) -> FileAudit:

    exists = path.exists()

    text = ""

    lines: list[str] = []

    sha = None

    size = None



    if exists:

        text = path.read_text(encoding="utf-8", errors="replace")

        lines = text.splitlines()

        sha = sha256_file(path)

        size = path.stat().st_size



    compile_ok, compile_error = (False, "file does not exist")

    if exists:

        compile_ok, compile_error = compile_file(path)



    tree = None

    ast_ok = False

    ast_error = ""

    if exists:

        try:

            tree = ast.parse(text, filename=str(path))

            ast_ok = True

        except Exception:

            ast_error = traceback.format_exc()



    functions_ast = {}

    classes_ast = {}

    calls_ast = Counter()

    routes_ast = []



    if tree is not None:

        for node in ast.walk(tree):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

                functions_ast[node.name] = getattr(node, "lineno", -1)

            elif isinstance(node, ast.ClassDef):

                classes_ast[node.name] = getattr(node, "lineno", -1)

            elif isinstance(node, ast.Call):

                name = get_call_name(node.func)

                if name:

                    calls_ast[name] += 1



        routes_ast = parse_routes_from_ast(tree)



    token_counts = {token: text.count(token) for token in REQUIRED_LITERAL_TOKENS}

    forbidden_counts = {token: text.count(token) for token in FORBIDDEN_PATH_TOKENS}

    markdown_counts = {token: text.count(token) for token in MARKDOWN_DAMAGE_TOKENS}



    return FileAudit(

        path=path,

        exists=exists,

        text=text,

        lines=lines,

        sha256=sha,

        size_bytes=size,

        line_count=len(lines),

        nonblank_line_count=sum(1 for line in lines if line.strip()),

        compile_ok=compile_ok,

        compile_error=compile_error,

        ast_ok=ast_ok,

        ast_error=ast_error,

        tree=tree,

        functions_ast=functions_ast,

        classes_ast=classes_ast,

        calls_ast=calls_ast,

        routes_ast=routes_ast,

        functions_regex=parse_regex_functions(text),

        routes_regex=parse_regex_routes(text),

        token_counts=token_counts,

        forbidden_path_counts=forbidden_counts,

        markdown_damage_counts=markdown_counts,

        top_level_assignments=top_level_assignments_from_ast(tree),

    )





def route_key(route: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:

    return (

        str(route.get("route", "")),

        str(route.get("function", "")),

        tuple(route.get("methods") or []),

    )





def route_path_method_key(route: dict[str, Any]) -> tuple[str, tuple[str, ...]]:

    return (

        str(route.get("route", "")),

        tuple(route.get("methods") or []),

    )





def section(title: str, lines: list[str]) -> None:

    lines.append("")

    lines.append("=" * 100)

    lines.append(title)

    lines.append("=" * 100)





def format_file_summary(label: str, fa: FileAudit, lines: list[str]) -> None:

    section(f"{label}: {fa.path}", lines)

    lines.append(f"exists: {fa.exists}")

    lines.append(f"size_bytes: {fa.size_bytes}")

    lines.append(f"sha256: {fa.sha256}")

    lines.append(f"line_count: {fa.line_count}")

    lines.append(f"nonblank_line_count: {fa.nonblank_line_count}")

    lines.append(f"compile_ok: {fa.compile_ok}")

    lines.append(f"ast_ok: {fa.ast_ok}")

    lines.append(f"function_count_ast: {len(fa.functions_ast)}")

    lines.append(f"function_count_regex: {len(fa.functions_regex)}")

    lines.append(f"route_count_ast: {len(fa.routes_ast)}")

    lines.append(f"route_count_regex: {len(fa.routes_regex)}")

    lines.append(f"class_count_ast: {len(fa.classes_ast)}")



    bad_markdown = {k: v for k, v in fa.markdown_damage_counts.items() if v}

    bad_paths = {k: v for k, v in fa.forbidden_path_counts.items() if v}

    missing_tokens = [k for k, v in fa.token_counts.items() if v == 0]



    lines.append(f"markdown_damage_counts_nonzero: {bad_markdown}")

    lines.append(f"forbidden_path_counts_nonzero: {bad_paths}")

    lines.append(f"required_literal_tokens_missing: {missing_tokens}")



    if not fa.compile_ok:

        lines.append("")

        lines.append("COMPILE ERROR:")

        lines.append(fa.compile_error[-6000:])



    if not fa.ast_ok:

        lines.append("")

        lines.append("AST ERROR:")

        lines.append(fa.ast_error[-6000:])





def compare_functions(a: FileAudit, b: FileAudit, lines: list[str]) -> dict[str, Any]:

    section("FUNCTION INVENTORY COMPARISON", lines)



    # If AST is unavailable for a file, regex still catches def-lines.

    funcs_a = set(a.functions_ast or a.functions_regex)

    funcs_b = set(b.functions_ast or b.functions_regex)



    missing_in_b = sorted(funcs_a - funcs_b)

    extra_in_b = sorted(funcs_b - funcs_a)



    required_missing_b = sorted(REQUIRED_FUNCTIONS - funcs_b)

    required_missing_a = sorted(REQUIRED_FUNCTIONS - funcs_a)



    lines.append(f"functions_in_A: {len(funcs_a)}")

    lines.append(f"functions_in_B: {len(funcs_b)}")

    lines.append(f"functions_from_A_missing_in_B: {len(missing_in_b)}")

    for name in missing_in_b:

        lines.append(f"  MISSING_IN_B: {name}")



    lines.append(f"functions_extra_in_B_vs_A: {len(extra_in_b)}")

    for name in extra_in_b:

        lines.append(f"  EXTRA_IN_B: {name}")



    lines.append("")

    lines.append(f"REQUIRED_FUNCTIONS missing in A: {required_missing_a}")

    lines.append(f"REQUIRED_FUNCTIONS missing in B: {required_missing_b}")



    duplicates_b = [

        name for name, count in Counter(re.findall(r"(?m)^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", b.text)).items()

        if count > 1

    ]

    lines.append(f"duplicate def names in B by regex: {duplicates_b}")



    return {

        "functions_in_a": len(funcs_a),

        "functions_in_b": len(funcs_b),

        "missing_in_b": missing_in_b,

        "extra_in_b": extra_in_b,

        "required_missing_a": required_missing_a,

        "required_missing_b": required_missing_b,

        "duplicate_defs_b": duplicates_b,

    }





def compare_routes(a: FileAudit, b: FileAudit, lines: list[str]) -> dict[str, Any]:

    section("ROUTE INVENTORY COMPARISON", lines)



    routes_a = a.routes_ast if a.routes_ast else a.routes_regex

    routes_b = b.routes_ast if b.routes_ast else b.routes_regex



    full_a = {route_key(r): r for r in routes_a}

    full_b = {route_key(r): r for r in routes_b}



    path_method_a = {route_path_method_key(r): r for r in routes_a}

    path_method_b = {route_path_method_key(r): r for r in routes_b}



    missing_full_in_b = sorted(set(full_a) - set(full_b))

    extra_full_in_b = sorted(set(full_b) - set(full_a))



    missing_pathmethod_in_b = sorted(set(path_method_a) - set(path_method_b))

    extra_pathmethod_in_b = sorted(set(path_method_b) - set(path_method_a))



    route_paths_b = {r["route"] for r in routes_b}

    required_routes_missing_b = sorted(REQUIRED_ROUTES - route_paths_b)



    lines.append(f"routes_in_A: {len(routes_a)}")

    lines.append(f"routes_in_B: {len(routes_b)}")

    lines.append("")

    lines.append("Routes in B:")

    for r in routes_b:

        lines.append(f"  {r.get('methods') or []} {r.get('route')} -> {r.get('function')} line {r.get('line')}")



    lines.append("")

    lines.append(f"route path+method entries from A missing in B: {len(missing_pathmethod_in_b)}")

    for item in missing_pathmethod_in_b:

        lines.append(f"  MISSING_ROUTE_PATH_METHOD_IN_B: {item}")



    lines.append(f"route path+method entries extra in B vs A: {len(extra_pathmethod_in_b)}")

    for item in extra_pathmethod_in_b:

        lines.append(f"  EXTRA_ROUTE_PATH_METHOD_IN_B: {item}")



    lines.append("")

    lines.append(f"full route+function entries from A missing in B: {len(missing_full_in_b)}")

    for item in missing_full_in_b:

        lines.append(f"  MISSING_FULL_ROUTE_IN_B: {item}")



    lines.append(f"full route+function entries extra in B vs A: {len(extra_full_in_b)}")

    for item in extra_full_in_b:

        lines.append(f"  EXTRA_FULL_ROUTE_IN_B: {item}")



    lines.append("")

    lines.append(f"REQUIRED_ROUTES missing in B: {required_routes_missing_b}")



    route_counter = Counter((r["route"], tuple(r.get("methods") or [])) for r in routes_b)

    dup_routes = [item for item, count in route_counter.items() if count > 1]

    lines.append(f"duplicate route path/method entries in B: {dup_routes}")



    return {

        "routes_in_a": len(routes_a),

        "routes_in_b": len(routes_b),

        "missing_pathmethod_in_b": [str(x) for x in missing_pathmethod_in_b],

        "extra_pathmethod_in_b": [str(x) for x in extra_pathmethod_in_b],

        "missing_full_in_b": [str(x) for x in missing_full_in_b],

        "extra_full_in_b": [str(x) for x in extra_full_in_b],

        "required_routes_missing_b": required_routes_missing_b,

        "duplicate_routes_b": [str(x) for x in dup_routes],

    }





def audit_calls(fa: FileAudit, lines: list[str]) -> dict[str, Any]:

    section(f"INTERNAL CALL AUDIT FOR B: {fa.path}", lines)



    if not fa.ast_ok:

        lines.append("Skipped: B does not parse as AST.")

        return {"skipped": True}



    defined = set(fa.functions_ast)

    imported_or_builtin_like = {

        # common builtins

        "str", "int", "float", "bool", "len", "list", "dict", "set", "tuple", "sorted",

        "sum", "any", "all", "next", "iter", "print", "open", "isinstance", "hasattr",

        "getattr", "setattr", "enumerate", "range", "min", "max", "round",



        # flask globals/imported names

        "Flask", "jsonify", "render_template", "request.get_json", "send_from_directory",

        "send_file", "abort",



        # imported modules/classes/functions

        "Path", "datetime.now", "json.loads", "json.dumps", "re.compile", "re.search",

        "csv.DictReader", "subprocess.run", "shlex.quote", "traceback.format_exc",

        "os.walk", "os.environ.get",

    }



    calls = fa.calls_ast

    internal_calls = sorted(name for name in calls if name in defined)

    bare_calls = sorted(

        name for name in calls

        if "." not in name and name not in defined and name not in imported_or_builtin_like

    )



    # These are not necessarily errors; they can be local nested functions.

    suspicious_bare = []

    for name in bare_calls:

        if name.startswith("_"):

            suspicious_bare.append(name)



    lines.append(f"defined_functions: {len(defined)}")

    lines.append(f"internal functions called: {len(internal_calls)}")

    lines.append("Top internal calls:")

    for name in sorted(internal_calls, key=lambda n: (-calls[n], n))[:100]:

        lines.append(f"  {name}: {calls[name]}")



    lines.append("")

    lines.append("Suspicious bare calls not defined at module level, not common builtins/imports:")

    for name in suspicious_bare[:200]:

        lines.append(f"  {name}: {calls[name]}")



    # Required helper usage checks.

    usage_checks = {

        "configured_project_script_path": calls.get("configured_project_script_path", 0),

        "configured_runner_python_path": calls.get("configured_runner_python_path", 0),

        "configured_contextily_python_path": calls.get("configured_contextily_python_path", 0),

        "launcher_default_value": calls.get("launcher_default_value", 0),

        "safe_resolve": calls.get("safe_resolve", 0),

    }

    lines.append("")

    lines.append(f"Required helper usage counts: {usage_checks}")



    return {

        "internal_calls_count": len(internal_calls),

        "suspicious_bare_calls": suspicious_bare,

        "usage_checks": usage_checks,

    }





def grep_lines(fa: FileAudit, patterns: list[str], lines: list[str], title: str) -> dict[str, list[str]]:

    section(title, lines)

    out = {}



    for pat in patterns:

        hits = []

        for i, line in enumerate(fa.lines, start=1):

            if pat in line:

                hits.append(f"{i}: {line.rstrip()}")

        out[pat] = hits

        lines.append(f"{pat!r}: {len(hits)} hit(s)")

        for hit in hits[:50]:

            lines.append(f"  {hit}")

        if len(hits) > 50:

            lines.append(f"  ... {len(hits) - 50} more")



    return out





def diff_important_function_sources(a: FileAudit, b: FileAudit, lines: list[str]) -> None:

    section("IMPORTANT FUNCTION SOURCE DIFFS WHERE BOTH ASTS PARSE", lines)



    if not (a.ast_ok and b.ast_ok):

        lines.append("Skipped: both files need AST parse for source-segment function diff.")

        return



    def get_function_segments(fa: FileAudit) -> dict[str, str]:

        segs = {}

        for node in ast.walk(fa.tree):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):

                seg = ast.get_source_segment(fa.text, node)

                if seg:

                    segs[node.name] = seg

        return segs



    seg_a = get_function_segments(a)

    seg_b = get_function_segments(b)



    important = sorted(REQUIRED_FUNCTIONS & set(seg_a) & set(seg_b))

    changed = []



    for name in important:

        if seg_a[name].strip() != seg_b[name].strip():

            changed.append(name)



    lines.append(f"important functions compared: {len(important)}")

    lines.append(f"important functions whose source differs A vs B: {len(changed)}")

    for name in changed:

        lines.append(f"  DIFFERS: {name}")



    for name in changed[:20]:

        lines.append("")

        lines.append("-" * 100)

        lines.append(f"DIFF: {name}")

        lines.append("-" * 100)

        diff = difflib.unified_diff(

            seg_a[name].splitlines(),

            seg_b[name].splitlines(),

            fromfile=f"A:{name}",

            tofile=f"B:{name}",

            lineterm="",

            n=3,

        )

        for line in list(diff)[:300]:

            lines.append(line)





def make_verdict(a: FileAudit, b: FileAudit, fn_cmp: dict[str, Any], route_cmp: dict[str, Any], call_audit: dict[str, Any]) -> tuple[str, list[str]]:

    problems = []

    warnings = []



    if not b.exists:

        problems.append("Recovered candidate B does not exist.")

    if not b.compile_ok:

        problems.append("Recovered candidate B does not compile.")

    if not b.ast_ok:

        problems.append("Recovered candidate B does not parse with ast.")



    if fn_cmp.get("required_missing_b"):

        problems.append(f"Recovered candidate B is missing required functions: {fn_cmp['required_missing_b']}")



    if route_cmp.get("required_routes_missing_b"):

        problems.append(f"Recovered candidate B is missing required routes: {route_cmp['required_routes_missing_b']}")



    if fn_cmp.get("missing_in_b"):

        warnings.append(f"Recovered candidate B is missing functions found in A: {fn_cmp['missing_in_b']}")



    if route_cmp.get("missing_pathmethod_in_b"):

        warnings.append(f"Recovered candidate B is missing route path/method entries found in A: {route_cmp['missing_pathmethod_in_b']}")



    bad_markdown_b = {k: v for k, v in b.markdown_damage_counts.items() if v}

    if bad_markdown_b:

        problems.append(f"Recovered candidate B still contains markdown damage tokens: {bad_markdown_b}")



    bad_paths_b = {k: v for k, v in b.forbidden_path_counts.items() if v}

    if bad_paths_b:

        problems.append(f"Recovered candidate B contains forbidden hardcoded path tokens: {bad_paths_b}")



    missing_tokens_b = [k for k, v in b.token_counts.items() if v == 0]

    if missing_tokens_b:

        problems.append(f"Recovered candidate B is missing required literal tokens: {missing_tokens_b}")



    usage = call_audit.get("usage_checks", {})

    for key in ["configured_project_script_path", "configured_runner_python_path", "launcher_default_value", "safe_resolve"]:

        if usage.get(key, 0) == 0:

            warnings.append(f"Recovered candidate B has zero AST call count for helper {key!r}.")



    if problems:

        return "FAIL", problems + warnings

    if warnings:

        return "WARN", warnings

    return "PASS", ["Recovered candidate B compiles, contains required functions/routes/tokens, and has no known markdown/path regressions."]





def main() -> int:

    a_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_A

    b_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_B



    a = audit_file(a_path)

    b = audit_file(b_path)



    lines: list[str] = []

    lines.append("SFINCS APP.PY RECOVERY AUDIT")

    lines.append(f"A active/broken/reference: {a.path}")

    lines.append(f"B recovered candidate:       {b.path}")



    format_file_summary("A", a, lines)

    format_file_summary("B", b, lines)



    fn_cmp = compare_functions(a, b, lines)

    route_cmp = compare_routes(a, b, lines)

    call_info = audit_calls(b, lines)



    grep_lines(

        b,

        sorted(FORBIDDEN_PATH_TOKENS),

        lines,

        "FORBIDDEN HARDCODED PATH GREP IN B",

    )



    grep_lines(

        b,

        sorted(MARKDOWN_DAMAGE_TOKENS),

        lines,

        "MARKDOWN DAMAGE GREP IN B",

    )



    grep_lines(

        b,

        sorted(REQUIRED_LITERAL_TOKENS),

        lines,

        "REQUIRED SETTINGS/PATH ARCHITECTURE TOKEN GREP IN B",

    )



    diff_important_function_sources(a, b, lines)



    section("LINE COUNT / SIZE COMPARISON", lines)

    lines.append(f"A line_count: {a.line_count}")

    lines.append(f"B line_count: {b.line_count}")

    lines.append(f"B - A line_count delta: {b.line_count - a.line_count}")

    lines.append(f"A nonblank_line_count: {a.nonblank_line_count}")

    lines.append(f"B nonblank_line_count: {b.nonblank_line_count}")

    lines.append(f"B - A nonblank delta: {b.nonblank_line_count - a.nonblank_line_count}")

    lines.append(f"A size_bytes: {a.size_bytes}")

    lines.append(f"B size_bytes: {b.size_bytes}")



    verdict, verdict_messages = make_verdict(a, b, fn_cmp, route_cmp, call_info)



    section("FINAL VERDICT", lines)

    lines.append(f"VERDICT: {verdict}")

    for msg in verdict_messages:

        lines.append(f"- {msg}")



    report = "\n".join(lines) + "\n"

    REPORT_PATH.write_text(report, encoding="utf-8")



    json_data = {

        "verdict": verdict,

        "a_path": str(a.path),

        "b_path": str(b.path),

        "a": {

            "exists": a.exists,

            "compile_ok": a.compile_ok,

            "ast_ok": a.ast_ok,

            "line_count": a.line_count,

            "nonblank_line_count": a.nonblank_line_count,

            "size_bytes": a.size_bytes,

            "sha256": a.sha256,

            "functions_ast": a.functions_ast,

            "functions_regex": a.functions_regex,

            "routes_ast": a.routes_ast,

            "routes_regex": a.routes_regex,

            "forbidden_path_counts": a.forbidden_path_counts,

            "markdown_damage_counts": a.markdown_damage_counts,

        },

        "b": {

            "exists": b.exists,

            "compile_ok": b.compile_ok,

            "ast_ok": b.ast_ok,

            "line_count": b.line_count,

            "nonblank_line_count": b.nonblank_line_count,

            "size_bytes": b.size_bytes,

            "sha256": b.sha256,

            "functions_ast": b.functions_ast,

            "functions_regex": b.functions_regex,

            "routes_ast": b.routes_ast,

            "routes_regex": b.routes_regex,

            "forbidden_path_counts": b.forbidden_path_counts,

            "markdown_damage_counts": b.markdown_damage_counts,

            "token_counts": b.token_counts,

        },

        "function_comparison": fn_cmp,

        "route_comparison": route_cmp,

        "call_audit": call_info,

        "verdict_messages": verdict_messages,

    }

    JSON_PATH.write_text(json.dumps(json_data, indent=2, sort_keys=True), encoding="utf-8")



    print(report)

    print(f"\nWrote report: {REPORT_PATH}")

    print(f"Wrote JSON:   {JSON_PATH}")



    return 0 if verdict == "PASS" else 2 if verdict == "WARN" else 1





if __name__ == "__main__":

    raise SystemExit(main())

