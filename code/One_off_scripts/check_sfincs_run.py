#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 28 13:07:05 2026

@author: epsilon


#!/usr/bin/env python3

Robust SFINCS web-launcher run checker.

Usage:
  python check_sfincs_run.py sfincs_weblauncher_override_005

or:
  python check_sfincs_run.py /proj/zefflab/projects/Flooding/sfincs_runs/sfincs_weblauncher_override_005
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime


DEFAULT_RUN_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs")


def section(title: str) -> None:
    print()
    print("=" * 90)
    print(title)
    print("=" * 90)


def run_cmd(cmd: list[str], *, timeout: int = 20) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except Exception as exc:
        return 999, "", str(exc)


def tail_file(path: Path, n: int = 120) -> str:
    if not path.exists():
        return f"[missing] {path}"

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception as exc:
        return f"[could not read {path}: {exc}]"


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return {"_json_read_error": str(exc)}


def parse_job_ids(job_file: Path) -> dict[str, str]:
    out = {}
    if not job_file.exists():
        return out

    for line in job_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"preprocess", "sfincs", "postprocess"} and value:
            out[key] = value
    return out


def print_tree(run_root: Path) -> None:
    if not run_root.exists():
        print(f"RUN FOLDER MISSING: {run_root}")
        return

    files = sorted(
        [p for p in run_root.rglob("*") if p.is_file()],
        key=lambda p: str(p),
    )

    if not files:
        print("[no files found]")
        return

    for p in files:
        try:
            stat = p.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            rel = p.relative_to(run_root)
            print(f"{mtime}  {stat.st_size:>12}  {rel}")
        except Exception:
            print(p)


def parse_sfincs_inp(path: Path) -> dict[str, str]:
    out = {}
    if not path.exists():
        return out

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("!"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def check_sfincs_inp_pointers(model_dir: Path) -> None:
    inp = model_dir / "sfincs.inp"

    if not inp.exists():
        print("sfincs.inp: MISSING")
        return

    print(f"sfincs.inp: FOUND ({inp.stat().st_size} bytes)")

    parsed = parse_sfincs_inp(inp)

    print()
    print("Important sfincs.inp keys:")
    for key in [
        "tref", "tstart", "tstop",
        "epsg", "crsgeo", "coriolis",
        "depfile", "mskfile", "indexfile", "sbgfile",
        "manningfile", "scsfile",
        "bndfile", "bzsfile",
        "srcfile", "disfile",
        "obsfile", "crsfile", "thdfile",
        "netamprfile",
    ]:
        if key in parsed:
            print(f"  {key:<16} = {parsed[key]}")

    print()
    print("Pointer existence check:")
    missing = []
    for key, value in sorted(parsed.items()):
        if not key.endswith("file"):
            continue
        if not value or value.lower() in {"none", "null"}:
            continue

        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = model_dir / candidate

        ok = candidate.exists()
        print(f"  {'OK     ' if ok else 'MISSING'} {key:<16} -> {value}")

        if not ok:
            missing.append((key, value, candidate))

    if missing:
        print()
        print("Missing pointer files:")
        for key, value, candidate in missing:
            print(f"  {key} = {value} -> {candidate}")


def summarize_config(cfg_path: Path) -> None:
    cfg = read_json(cfg_path)
    if cfg is None:
        print(f"run_config.json missing: {cfg_path}")
        return

    if isinstance(cfg, dict) and "_json_read_error" in cfg:
        print(f"run_config.json read error: {cfg['_json_read_error']}")
        return

    print(f"Config: {cfg_path}")
    for key in [
        "run_name",
        "pipeline_mode",
        "preprocess_mode",
        "use_sfincs_file_overrides",
        "tref",
        "tstart",
        "tstop",
        "data_root",
        "output_root",
        "conda_python",
        "sfincs_container_path",
        "overwrite_existing_run",
    ]:
        print(f"  {key:<28} = {cfg.get(key)!r}")

    adv = cfg.get("advanced_config") or {}
    if isinstance(adv, dict):
        print("  advanced_config selected values:")
        for key in ["epsg", "crsgeo", "coriolis", "baro", "pavbnd", "mmax", "nmax", "dx", "dy"]:
            print(f"    {key:<10} = {adv.get(key)!r}")
    else:
        print(f"  advanced_config is not a dict: {type(adv).__name__}")

    overrides = cfg.get("sfincs_file_overrides") or {}
    if isinstance(overrides, dict):
        on = sorted([k for k, v in overrides.items() if v])
        off = sorted([k for k, v in overrides.items() if not v])
        print(f"  overrides ON ({len(on)}): {on}")
        print(f"  overrides OFF ({len(off)}): {off}")


def show_failure_jsons(run_root: Path) -> None:
    for name in ["preprocess_failed.json", "sfincs_failed.json", "postprocess_failed.json"]:
        path = run_root / name
        if not path.exists():
            print(f"{name}: not present")
            continue

        print()
        print(f"{name}:")
        data = read_json(path)
        if isinstance(data, dict):
            for key in ["status", "failed_at", "error_type", "error_message", "config_path", "model_root"]:
                if key in data:
                    print(f"  {key}: {data[key]}")
        else:
            print(tail_file(path, 80))


def show_slurm(run_root: Path) -> None:
    jobs = parse_job_ids(run_root / "job_ids.txt")

    if not jobs:
        print("No job_ids.txt or no Slurm job IDs found.")
        return

    print("Job IDs:")
    for k, v in jobs.items():
        print(f"  {k:<12} {v}")

    job_csv = ",".join(jobs.values())

    print()
    print("squeue:")
    rc, out, err = run_cmd(["squeue", "-j", job_csv], timeout=15)
    print(out.strip() or err.strip() or f"[squeue returned {rc}]")

    print()
    print("sacct:")
    rc, out, err = run_cmd([
        "sacct",
        "-j", job_csv,
        "--format=JobID,JobName%34,State,ExitCode,Elapsed,MaxRSS,ReqMem,NCPUS",
    ], timeout=20)
    print(out.strip() or err.strip() or f"[sacct returned {rc}]")


def show_logs(run_root: Path) -> None:
    logs = sorted((run_root / "logs").glob("*"))

    if not logs:
        print("No files in logs/.")
        return

    for log in logs:
        if not log.is_file():
            continue
        print()
        print("-" * 90)
        print(log)
        print("-" * 90)
        print(tail_file(log, 140))


def show_launcher_logs(run_root: Path) -> None:
    output_root = run_root.parent
    launcher_dir = output_root / "_launcher_logs" / run_root.name

    if not launcher_dir.exists():
        print(f"No launcher log folder: {launcher_dir}")
        return

    logs = sorted(
        [p for p in launcher_dir.glob("*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not logs:
        print(f"No launcher logs in: {launcher_dir}")
        return

    for log in logs[:6]:
        print()
        print("-" * 90)
        print(log)
        print("-" * 90)
        print(tail_file(log, 120))


def diagnose(run_root: Path) -> None:
    section("RUN")
    print(run_root)
    print(f"exists: {run_root.exists()}")

    section("FILES")
    print_tree(run_root)

    section("CONFIG SUMMARY")
    summarize_config(run_root / "run_config.json")

    section("SLURM STATUS")
    show_slurm(run_root)

    section("FAILURE JSONS")
    show_failure_jsons(run_root)

    section("MODEL CHECK")
    model_dir = run_root / "model"
    if model_dir.exists():
        print(f"model dir: {model_dir}")
        for p in sorted(model_dir.iterdir()):
            if p.is_file():
                print(f"  {p.name:<30} {p.stat().st_size:>12} bytes")
    else:
        print("model dir missing")
    print()
    check_sfincs_inp_pointers(model_dir)

    section("RUN LOGS")
    show_logs(run_root)

    section("LAUNCHER LOGS")
    show_launcher_logs(run_root)

    section("QUICK INTERPRETATION HINTS")
    print("""\
- If preprocess failed before sfincs.inp exists: look at preprocess_failed.json and preprocess_*.err.
- If sfincs.inp exists but pointer check shows MISSING: an override file was selected but not copied/found.
- If preprocess succeeded but SFINCS failed: inspect sfincs_*.out/err and sfincs.inp pointer check.
- If postprocess failed: inspect postprocess_failed.json and postprocess_*.err.
- If Slurm jobs after preprocess are CANCELLED: preprocess likely failed and afterok blocked the chain.
""")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python check_sfincs_run.py RUN_NAME_OR_RUN_PATH")
        return 2

    arg = sys.argv[1].strip()
    p = Path(arg)

    if p.is_absolute():
        run_root = p
    else:
        run_root = DEFAULT_RUN_ROOT / arg

    diagnose(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())