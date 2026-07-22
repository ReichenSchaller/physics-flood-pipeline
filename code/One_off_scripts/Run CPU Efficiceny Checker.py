#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  3 12:25:56 2026

@author: epsilon
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# %%
from pathlib import Path
import re
import shutil
import subprocess
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# USER SETTINGS
# =============================================================================

RUN_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs")

# Only true CPU sweep runs:
#   launcher_test_34_CPU_harvey_001
#   launcher_test_50_CPU_harvey_002
RUN_NAME_PATTERN = re.compile(
    r"^launcher_test_(?P<cpu>\d+)_CPU_harvey_(?P<rep>\d{3})$"
)

# Old bad folders were deleted, so default to no manual exclusions.
EXCLUDE_RUNS = set()

# Main threshold you asked for.
CPU_EFFICIENCY_THRESHOLD_PERCENT = 95.0

# Usually check only the solver stage for this question.
# Options inside job_ids.txt are usually:
#   preprocess
#   sfincs
#   postprocess
STAGES_TO_CHECK = ["sfincs"]

# Require real model outputs for SFINCS runs before calling the run good.
REQUIRE_SFINCS_OUTPUT_FILES = True

# Require Slurm state and exit code to be clean.
REQUIRE_COMPLETED = True
REQUIRE_EXIT_CODE_ZERO = True

# If sacct TotalCPU is unavailable or unparsable, try seff as fallback.
USE_SEFF_FALLBACK = True

# Save CSV summary.
SAVE_CSV = True
OUTPUT_DIR = RUN_ROOT / "_cpu_sweep_analysis"

# Optional plot.
MAKE_PLOT = True


# =============================================================================
# Helpers
# =============================================================================

def parse_run_name(name: str):
    m = RUN_NAME_PATTERN.match(name)
    if not m:
        return None

    return {
        "cpu_from_name": int(m.group("cpu")),
        "run_version": m.group("rep"),
    }


def read_job_ids(run_dir: Path) -> dict:
    """
    Reads job_ids.txt but keeps only numeric Slurm job IDs.

    This avoids accidentally treating run_name, run_root, or submitted_at
    as job IDs.
    """
    path = run_dir / "job_ids.txt"
    if not path.exists():
        return {}

    out = {}

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()

        if not line or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if re.fullmatch(r"\d+", value):
            out[key] = value

    return out


def parse_elapsed_to_seconds(elapsed: str):
    """
    Parses Slurm elapsed-like strings:
        MM:SS
        HH:MM:SS
        D-HH:MM:SS
        MM:SS.micro
        HH:MM:SS.micro
    """
    if elapsed is None:
        return None

    elapsed = str(elapsed).strip()

    if not elapsed or elapsed.lower() in {"unknown", "none", "n/a", "null"}:
        return None

    try:
        days = 0

        if "-" in elapsed:
            day_part, time_part = elapsed.split("-", 1)
            days = int(day_part)
        else:
            time_part = elapsed

        parts = time_part.split(":")
        parts = [float(p) for p in parts]

        if len(parts) == 2:
            minutes, seconds = parts
            hours = 0
        elif len(parts) == 3:
            hours, minutes, seconds = parts
        else:
            return None

        return days * 86400 + hours * 3600 + minutes * 60 + seconds

    except Exception:
        return None


def parse_total_cpu_to_seconds(total_cpu: str):
    """
    Slurm TotalCPU commonly looks like elapsed time:
        00:05:12
        1-02:03:04
        00:05.123
    Reuse the elapsed parser.
    """
    return parse_elapsed_to_seconds(total_cpu)


def output_files_exist(run_dir: Path) -> bool:
    candidates = [
        run_dir / "model" / "sfincs_map.nc",
        run_dir / "model" / "sfincs_his.nc",
    ]

    return any(path.exists() and path.stat().st_size > 0 for path in candidates)


def sacct_for_job(job_id: str):
    """
    Pull Slurm accounting for the main job row.
    """
    if not shutil.which("sacct"):
        return None, "sacct not found"

    cmd = [
        "sacct",
        "-j", str(job_id),
        "--format=JobIDRaw,JobName,State,Elapsed,TotalCPU,AllocCPUS,ReqCPUS,ExitCode",
        "-P",
        "-n",
    ]

    try:
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        return None, f"sacct exception: {exc}"

    if result.returncode != 0:
        return None, "sacct failed: " + result.stderr.strip()

    rows = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        parts = line.split("|")

        if len(parts) < 8:
            continue

        rows.append({
            "JobIDRaw": parts[0],
            "JobName": parts[1],
            "State": parts[2],
            "Elapsed": parts[3],
            "TotalCPU": parts[4],
            "AllocCPUS": parts[5],
            "ReqCPUS": parts[6],
            "ExitCode": parts[7],
        })

    if not rows:
        return None, "sacct returned no rows"

    # Prefer exact main job row, not .batch/.extern.
    for row in rows:
        if row["JobIDRaw"] == str(job_id):
            return row, ""

    # Fallback to first non-step row.
    for row in rows:
        if "." not in row["JobIDRaw"]:
            return row, ""

    return rows[0], ""


def seff_efficiency_for_job(job_id: str):
    """
    Optional fallback if sacct TotalCPU is not useful.

    Returns:
        efficiency_percent, reason
    """
    if not shutil.which("seff"):
        return None, "seff not found"

    cmd = ["seff", str(job_id)]

    try:
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        return None, f"seff exception: {exc}"

    if result.returncode != 0:
        return None, "seff failed: " + result.stderr.strip()

    # Example:
    # CPU Efficiency: 95.32% of 01:20:00 core-walltime
    m = re.search(r"CPU Efficiency:\s*([0-9.]+)%", result.stdout)

    if not m:
        return None, "could not parse seff CPU Efficiency"

    return float(m.group(1)), ""


def collect_stage_record(run_dir: Path, stage: str):
    parsed = parse_run_name(run_dir.name)

    if parsed is None:
        return None

    if run_dir.name in EXCLUDE_RUNS:
        return None

    job_ids = read_job_ids(run_dir)
    job_id = job_ids.get(stage)

    base = {
        "run_name": run_dir.name,
        "run_version": parsed["run_version"],
        "cpu_from_name": parsed["cpu_from_name"],
        "stage": stage,
        "job_id": job_id or "",
        "state": "",
        "exit_code": "",
        "elapsed": "",
        "total_cpu": "",
        "alloc_cpus": None,
        "elapsed_seconds": None,
        "total_cpu_seconds": None,
        "allocated_cpu_seconds": None,
        "cpu_efficiency_percent": None,
        "efficiency_source": "",
        "has_sfincs_outputs": output_files_exist(run_dir),
        "good_finished_run": False,
        "passes_threshold": False,
        "skip_reason": "",
    }

    if not job_id:
        base["skip_reason"] = f"missing numeric {stage} job id"
        return base

    sacct, reason = sacct_for_job(job_id)

    if sacct is None:
        base["skip_reason"] = reason
        return base

    state = sacct.get("State", "")
    exit_code = sacct.get("ExitCode", "")
    elapsed = sacct.get("Elapsed", "")
    total_cpu = sacct.get("TotalCPU", "")

    elapsed_seconds = parse_elapsed_to_seconds(elapsed)
    total_cpu_seconds = parse_total_cpu_to_seconds(total_cpu)

    try:
        alloc_cpus = int(sacct.get("AllocCPUS") or 0)
    except Exception:
        alloc_cpus = 0

    allocated_cpu_seconds = None
    efficiency = None
    efficiency_source = ""

    if elapsed_seconds and elapsed_seconds > 0 and alloc_cpus and alloc_cpus > 0:
        allocated_cpu_seconds = elapsed_seconds * alloc_cpus

        if total_cpu_seconds is not None and total_cpu_seconds >= 0:
            efficiency = 100.0 * total_cpu_seconds / allocated_cpu_seconds
            efficiency_source = "sacct TotalCPU"

    if efficiency is None and USE_SEFF_FALLBACK:
        seff_eff, seff_reason = seff_efficiency_for_job(job_id)

        if seff_eff is not None:
            efficiency = seff_eff
            efficiency_source = "seff"
        else:
            efficiency_source = f"unavailable; {seff_reason}"

    good = True
    skip_reason = ""

    if REQUIRE_COMPLETED and not state.startswith("COMPLETED"):
        good = False
        skip_reason = f"not completed: {state}"

    elif REQUIRE_EXIT_CODE_ZERO and exit_code != "0:0":
        good = False
        skip_reason = f"nonzero exit code: {exit_code}"

    elif elapsed_seconds is None or elapsed_seconds <= 0:
        good = False
        skip_reason = "bad or missing elapsed time"

    elif alloc_cpus is None or alloc_cpus <= 0:
        good = False
        skip_reason = "bad or missing allocated CPU count"

    elif efficiency is None:
        good = False
        skip_reason = "could not compute CPU efficiency"

    elif stage == "sfincs" and REQUIRE_SFINCS_OUTPUT_FILES and not base["has_sfincs_outputs"]:
        good = False
        skip_reason = "missing SFINCS output files"

    passes = (
        good
        and efficiency is not None
        and efficiency >= CPU_EFFICIENCY_THRESHOLD_PERCENT
    )

    base.update({
        "state": state,
        "exit_code": exit_code,
        "elapsed": elapsed,
        "total_cpu": total_cpu,
        "alloc_cpus": alloc_cpus,
        "elapsed_seconds": elapsed_seconds,
        "total_cpu_seconds": total_cpu_seconds,
        "allocated_cpu_seconds": allocated_cpu_seconds,
        "cpu_efficiency_percent": efficiency,
        "efficiency_source": efficiency_source,
        "good_finished_run": good,
        "passes_threshold": passes,
        "skip_reason": skip_reason,
    })

    return base


# =============================================================================
# Scan all runs
# =============================================================================

if not RUN_ROOT.exists():
    raise FileNotFoundError(f"RUN_ROOT does not exist: {RUN_ROOT}")

records = []

for run_dir in sorted(RUN_ROOT.iterdir()):
    if not run_dir.is_dir():
        continue

    if parse_run_name(run_dir.name) is None:
        continue

    for stage in STAGES_TO_CHECK:
        rec = collect_stage_record(run_dir, stage)

        if rec is not None:
            records.append(rec)

df = pd.DataFrame(records)

if df.empty:
    raise RuntimeError("No matching CPU-sweep records found.")

df = df.sort_values(["stage", "run_version", "cpu_from_name", "run_name"])

print("\n=== CPU efficiency audit: all matched records ===")
print(df[
    [
        "run_name",
        "run_version",
        "stage",
        "job_id",
        "state",
        "exit_code",
        "cpu_from_name",
        "alloc_cpus",
        "elapsed",
        "total_cpu",
        "cpu_efficiency_percent",
        "efficiency_source",
        "has_sfincs_outputs",
        "good_finished_run",
        "passes_threshold",
        "skip_reason",
    ]
].to_string(index=False))


# =============================================================================
# Summaries
# =============================================================================

good_df = df[df["good_finished_run"] == True].copy()

if good_df.empty:
    raise RuntimeError("No good finished records available for efficiency check.")

below_df = good_df[good_df["passes_threshold"] == False].copy()
pass_df = good_df[good_df["passes_threshold"] == True].copy()

print("\n=== Summary ===")
print(f"Threshold: {CPU_EFFICIENCY_THRESHOLD_PERCENT:.1f}%")
print(f"Good finished records checked: {len(good_df)}")
print(f"Passing records: {len(pass_df)}")
print(f"Below-threshold records: {len(below_df)}")

print("\nEfficiency stats by stage:")
print(good_df.groupby("stage")["cpu_efficiency_percent"].agg(
    count="count",
    mean="mean",
    median="median",
    min="min",
    max="max",
).to_string())

print("\nEfficiency stats by CPU count:")
print(good_df.groupby("cpu_from_name")["cpu_efficiency_percent"].agg(
    count="count",
    mean="mean",
    median="median",
    min="min",
    max="max",
).to_string())

if below_df.empty:
    print(f"\nPASS: all good finished records are >= {CPU_EFFICIENCY_THRESHOLD_PERCENT:.1f}% CPU efficiency.")
else:
    print(f"\nWARNING: these records are below {CPU_EFFICIENCY_THRESHOLD_PERCENT:.1f}% CPU efficiency:")
    print(below_df[
        [
            "run_name",
            "run_version",
            "stage",
            "job_id",
            "cpu_from_name",
            "alloc_cpus",
            "elapsed",
            "total_cpu",
            "cpu_efficiency_percent",
            "efficiency_source",
        ]
    ].sort_values(["cpu_efficiency_percent", "cpu_from_name"]).to_string(index=False))


# =============================================================================
# Save CSV
# =============================================================================

if SAVE_CSV:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    out_path = OUTPUT_DIR / "cpu_sweep_cpu_efficiency_audit.csv"
    df.to_csv(out_path, index=False)

    below_path = OUTPUT_DIR / "cpu_sweep_cpu_efficiency_below_threshold.csv"
    below_df.to_csv(below_path, index=False)

    print("\nSaved CSVs:")
    print(out_path)
    print(below_path)


# =============================================================================
# Plot
# =============================================================================

if MAKE_PLOT:
    plt.figure(figsize=(11, 6.5))

    for stage, group in good_df.groupby("stage"):
        plt.scatter(
            group["cpu_from_name"],
            group["cpu_efficiency_percent"],
            s=55,
            alpha=0.75,
            label=stage,
        )

    plt.axhline(
        CPU_EFFICIENCY_THRESHOLD_PERCENT,
        linestyle="--",
        linewidth=1.5,
        label=f"{CPU_EFFICIENCY_THRESHOLD_PERCENT:.1f}% threshold",
    )

    plt.xlabel("SFINCS CPUs requested / allocated")
    plt.ylabel("CPU efficiency (%)")
    plt.title("CPU Sweep: SFINCS Solver CPU Efficiency Audit")
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.tight_layout()
    plt.show()