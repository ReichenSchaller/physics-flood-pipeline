#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  1 18:58:20 2026

@author: epsilon
"""

# %%
from pathlib import Path
import re
import subprocess
import shutil
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# USER SETTINGS — edit these later if needed
# =============================================================================

RUN_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs")


# Run folder names to include.
# These patterns match:
#   launcher_override_test_harvey_002
#   launcher_override_test_harvey_003
#   launcher_test_10_CPU_harvey_001
#   launcher_test_11_CPU_harvey_001
#   launcher_test_12_CPU_harvey_001
# etc.
RUN_NAME_PATTERN = re.compile(r"^launcher_test_\d+_CPU_harvey_\d{3}$")

# Require actual SFINCS outputs to exist before plotting a point.
# This helps avoid plotting failed or incomplete jobs.
REQUIRE_OUTPUT_FILES = True

# Label each point with elapsed minutes.
ANNOTATE_POINTS = True

# =============================================================================
# Helpers
# =============================================================================

def run_name_matches(name: str) -> bool:
    return RUN_NAME_PATTERN.match(name) is not None


def read_job_ids(run_dir: Path) -> dict:
    """
    Reads job_ids.txt files like:
        preprocess=52844680
        sfincs=52844681
        postprocess=52844682
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

        if key and value:
            out[key] = value

    return out


def parse_elapsed_to_seconds(elapsed: str):
    """
    Converts Slurm elapsed strings to seconds.

    Handles common formats:
        MM:SS
        HH:MM:SS
        D-HH:MM:SS
    """
    if not elapsed:
        return None

    elapsed = str(elapsed).strip()

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

        return int(days * 86400 + hours * 3600 + minutes * 60 + seconds)

    except Exception:
        return None


def output_files_exist(run_dir: Path) -> bool:
    """
    Checks for successful SFINCS output files.
    """
    candidates = [
        run_dir / "model" / "sfincs_map.nc",
        run_dir / "model" / "sfincs_his.nc",
    ]

    return any(path.exists() and path.stat().st_size > 0 for path in candidates)


def cpu_from_run_name(name: str):
    """
    Extracts CPU count from names like:
        launcher_test_10_CPU_harvey_001
    """
    m = re.search(r"launcher_test_(\d+)_CPU_harvey_\d+", name)
    if m:
        return int(m.group(1))
    return None

def version_from_run_name(name: str):
    """
    Extracts trailing replicate/version from names like:
        launcher_test_10_CPU_harvey_001 -> 001
        launcher_override_test_harvey_002 -> 002
    """
    m = re.search(r"_(\d{3})$", name)
    if m:
        return m.group(1)
    return "unknown"

def cpu_from_slurm_script(run_dir: Path):
    """
    Fallback: reads #SBATCH --cpus-per-task from SFINCS Slurm script.
    """
    script_candidates = sorted((run_dir / "scripts").glob("*sfincs*.sh"))

    for script in script_candidates:
        text = script.read_text(encoding="utf-8", errors="replace")

        m = re.search(r"#SBATCH\s+--cpus-per-task[=\s]+(\d+)", text)
        if m:
            return int(m.group(1))

    return None


def sacct_for_job(job_id: str):
    """
    Pulls Slurm accounting for the main SFINCS job.
    """
    if not shutil.which("sacct"):
        return None

    cmd = [
        "sacct",
        "-j", str(job_id),
        "--format=JobIDRaw,JobName,State,Elapsed,AllocCPUS,ReqCPUS,ExitCode",
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
    except Exception:
        return None

    if result.returncode != 0:
        return None

    rows = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("|")
        if len(parts) < 7:
            continue

        rows.append({
            "JobIDRaw": parts[0],
            "JobName": parts[1],
            "State": parts[2],
            "Elapsed": parts[3],
            "AllocCPUS": parts[4],
            "ReqCPUS": parts[5],
            "ExitCode": parts[6],
        })

    if not rows:
        return None

    # Prefer the main row exactly matching the job ID, not .batch/.extern steps.
    for row in rows:
        if row["JobIDRaw"] == str(job_id):
            return row

    # Fallback: first row that is not a batch/extern step.
    for row in rows:
        if "." not in row["JobIDRaw"]:
            return row

    return rows[0]


def collect_run_record(run_dir: Path):
    job_ids = read_job_ids(run_dir)
    sfincs_job_id = job_ids.get("sfincs")

    if not sfincs_job_id:
        return {
            "run_name": run_dir.name,
            "status": "skip_no_sfincs_job_id",
        }

    sacct = sacct_for_job(sfincs_job_id)

    if sacct is None:
        return {
            "run_name": run_dir.name,
            "sfincs_job_id": sfincs_job_id,
            "status": "skip_no_sacct",
        }

    state = sacct.get("State", "")
    elapsed = sacct.get("Elapsed", "")
    elapsed_seconds = parse_elapsed_to_seconds(elapsed)

    try:
        alloc_cpus = int(sacct.get("AllocCPUS") or 0)
    except Exception:
        alloc_cpus = 0

    if alloc_cpus <= 0:
        alloc_cpus = cpu_from_run_name(run_dir.name) or cpu_from_slurm_script(run_dir) or 0

    has_outputs = output_files_exist(run_dir)

    is_success = (
        state.startswith("COMPLETED")
        and elapsed_seconds is not None
        and elapsed_seconds > 0
        and alloc_cpus > 0
        and (has_outputs or not REQUIRE_OUTPUT_FILES)
    )

    return {
        "run_name": run_dir.name,
        "run_dir": str(run_dir),
        "sfincs_job_id": sfincs_job_id,
        "state": state,
        "elapsed": elapsed,
        "elapsed_seconds": elapsed_seconds,
        "elapsed_minutes": elapsed_seconds / 60 if elapsed_seconds is not None else None,
        "sfincs_cpus": alloc_cpus,
        "exit_code": sacct.get("ExitCode", ""),
        "has_sfincs_outputs": has_outputs,
        "run_version": version_from_run_name(run_dir.name),
        "status": "success" if is_success else "skip_not_successful",
    }


# =============================================================================
# Scan runs
# =============================================================================

if not RUN_ROOT.exists():
    raise FileNotFoundError(f"RUN_ROOT does not exist: {RUN_ROOT}")

run_dirs = sorted(
    path for path in RUN_ROOT.iterdir()
    if path.is_dir() and run_name_matches(path.name)
)

records = [collect_run_record(path) for path in run_dirs]
df_all = pd.DataFrame(records)

print("\nAll matched run folders:")
if df_all.empty:
    print("No matching run folders found.")
else:
    print(df_all[[
        "run_name",
        "status",
        "sfincs_job_id",
        "state",
        "sfincs_cpus",
        "elapsed",
        "elapsed_minutes",
        "has_sfincs_outputs",
    ]].to_string(index=False))

df_success = df_all[df_all["status"] == "success"].copy()

if df_success.empty:
    raise RuntimeError(
        "No successful SFINCS runs found to plot. "
        "Check job_ids.txt, sacct availability, run folder patterns, or REQUIRE_OUTPUT_FILES."
    )

df_success = df_success.sort_values(["run_version", "sfincs_cpus", "elapsed_minutes", "run_name"])

print("\nSuccessful plotted runs:")
print(df_success[[
    "run_name",
    "run_version",
    "sfincs_job_id",
    "sfincs_cpus",
    "elapsed",
    "elapsed_minutes",
]].to_string(index=False))


# =============================================================================
# Plot
# =============================================================================

plt.figure(figsize=(9.5, 5.8))

version_colors = {
    "001": "tab:blue",
    "002": "tab:orange",
    "003": "tab:green",
    "004": "tab:red",
    "005": "tab:purple",
}

for version, group in df_success.groupby("run_version"):
    group = group.sort_values(["sfincs_cpus", "elapsed_minutes", "run_name"])
    color = version_colors.get(version, None)

    plt.scatter(
        group["sfincs_cpus"],
        group["elapsed_minutes"],
        s=70,
        label=f"Run version {version}",
        color=color,
    )

    # Draw one line per version instead of one jagged line through every point.
    if len(group) > 1:
        plt.plot(
            group["sfincs_cpus"],
            group["elapsed_minutes"],
            linewidth=0,
            alpha=0.55,
            color=color,
        )

    if ANNOTATE_POINTS:
        for _, row in group.iterrows():
            label = f"{row['elapsed_minutes']:.1f} min"
            plt.annotate(
                label,
                (row["sfincs_cpus"], row["elapsed_minutes"]),
                textcoords="offset points",
                xytext=(6, 5),
                fontsize=8,
            )

plt.xlabel("SFINCS CPUs requested / allocated")
plt.ylabel("SFINCS job wall time after start (minutes)")
plt.title("Harvey Override SFINCS CPU Count vs Job Time")
plt.grid(True, alpha=0.3)
plt.legend(title="Run version")

plt.tight_layout()
plt.show()