# %%
from pathlib import Path
from datetime import datetime
import re
import subprocess
import shutil
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# USER SETTINGS
# =============================================================================

RUN_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs")

# Only true CPU sweep runs:
#   launcher_test_34_CPU_harvey_001
#   launcher_test_36_CPU_harvey_001
#   launcher_test_50_CPU_harvey_001
RUN_NAME_PATTERN = re.compile(r"^launcher_test_(?P<cpu>\d+)_CPU_harvey_(?P<rep>\d{3})$")

# Bad runs you deleted or do not want included if any folders remain.
EXCLUDE_RUNS = {
    "launcher_test_40_CPU_harvey_001",
    "launcher_test_42_CPU_harvey_001",
    "launcher_test_44_CPU_harvey_001",
    "launcher_test_46_CPU_harvey_001",
    "launcher_test_48_CPU_harvey_001",
}

ONLY_STARTED_JOBS = True
ANNOTATE_POINTS = True


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
    This avoids accidentally treating run_name/run_root/submitted_at as job IDs.
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


def parse_slurm_datetime(value: str):
    """
    Parses common Slurm sacct datetime strings.

    Common examples:
        2026-06-02T09:41:52
        2026-06-02T09:41
        2026-06-02 09:41:52
        Unknown
    """
    if value is None:
        return None

    value = str(value).strip()

    if not value or value.lower() in {"unknown", "none", "n/a", "null"}:
        return None

    # Remove any simple trailing timezone marker if present.
    value = value.replace("Z", "")

    try:
        return datetime.fromisoformat(value)
    except Exception:
        pass

    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass

    return None


def sacct_for_job(job_id: str):
    """
    Pulls Slurm accounting for the main SFINCS job.

    Important:
    Longleaf's sacct rejected --time-format=iso, so this intentionally does not use it.
    """
    if not shutil.which("sacct"):
        return None, "sacct not found"

    cmd = [
        "sacct",
        "-j", str(job_id),
        "--format=JobIDRaw,JobName,State,Submit,Eligible,Start,End,Elapsed,AllocCPUS,ReqCPUS,ExitCode",
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
        if len(parts) < 11:
            continue

        rows.append({
            "JobIDRaw": parts[0],
            "JobName": parts[1],
            "State": parts[2],
            "Submit": parts[3],
            "Eligible": parts[4],
            "Start": parts[5],
            "End": parts[6],
            "Elapsed": parts[7],
            "AllocCPUS": parts[8],
            "ReqCPUS": parts[9],
            "ExitCode": parts[10],
        })

    if not rows:
        return None, "sacct returned no rows"

    # Prefer the main job row, not .batch/.extern.
    for row in rows:
        if row["JobIDRaw"] == str(job_id):
            return row, ""

    for row in rows:
        if "." not in row["JobIDRaw"]:
            return row, ""

    return rows[0], ""


def blank_record(run_dir: Path, parsed: dict, status: str, reason: str = ""):
    return {
        "run_name": run_dir.name,
        "run_version": parsed["run_version"],
        "sfincs_job_id": "",
        "sfincs_cpus": parsed["cpu_from_name"],
        "state": "",
        "submit": "",
        "eligible": "",
        "start": "",
        "end": "",
        "elapsed": "",
        "total_queue_wait_min": None,
        "eligible_queue_wait_min": None,
        "wait_min": None,
        "dependency_or_hold_wait_min": None,
        "started": False,
        "status": status,
        "reason": reason,
    }


def collect_record(run_dir: Path):
    parsed = parse_run_name(run_dir.name)
    if not parsed:
        return None

    if run_dir.name in EXCLUDE_RUNS:
        return None

    job_ids = read_job_ids(run_dir)
    sfincs_job_id = job_ids.get("sfincs")

    if not sfincs_job_id:
        return blank_record(run_dir, parsed, "skip_no_sfincs_job_id")

    sacct, sacct_reason = sacct_for_job(sfincs_job_id)

    if sacct is None:
        rec = blank_record(run_dir, parsed, "skip_no_sacct", sacct_reason)
        rec["sfincs_job_id"] = sfincs_job_id
        return rec

    submit = parse_slurm_datetime(sacct.get("Submit"))
    eligible = parse_slurm_datetime(sacct.get("Eligible"))
    start = parse_slurm_datetime(sacct.get("Start"))
    end = parse_slurm_datetime(sacct.get("End"))

    total_queue_wait_min = None
    eligible_queue_wait_min = None
    dependency_or_hold_wait_min = None

    if submit and start:
        total_queue_wait_min = (start - submit).total_seconds() / 60

    if eligible and start:
        eligible_queue_wait_min = (start - eligible).total_seconds() / 60

    if submit and eligible:
        dependency_or_hold_wait_min = (eligible - submit).total_seconds() / 60

    # Main metric for planning:
    # Prefer Eligible -> Start because it avoids dependency/hold time when available.
    # Fallback to Submit -> Start.
    wait_min = eligible_queue_wait_min
    if wait_min is None:
        wait_min = total_queue_wait_min

    try:
        alloc_cpus = int(sacct.get("AllocCPUS") or 0)
    except Exception:
        alloc_cpus = 0

    if alloc_cpus <= 0:
        alloc_cpus = parsed["cpu_from_name"]

    started = start is not None

    return {
        "run_name": run_dir.name,
        "run_version": parsed["run_version"],
        "sfincs_job_id": sfincs_job_id,
        "sfincs_cpus": alloc_cpus,
        "state": sacct.get("State", ""),
        "submit": sacct.get("Submit", ""),
        "eligible": sacct.get("Eligible", ""),
        "start": sacct.get("Start", ""),
        "end": sacct.get("End", ""),
        "elapsed": sacct.get("Elapsed", ""),
        "total_queue_wait_min": total_queue_wait_min,
        "eligible_queue_wait_min": eligible_queue_wait_min,
        "wait_min": wait_min,
        "dependency_or_hold_wait_min": dependency_or_hold_wait_min,
        "started": started,
        "status": "started" if started else "pending_or_unstarted",
        "reason": "",
    }


# =============================================================================
# Scan
# =============================================================================

if not RUN_ROOT.exists():
    raise FileNotFoundError(f"RUN_ROOT does not exist: {RUN_ROOT}")

records = []

for run_dir in sorted(RUN_ROOT.iterdir()):
    if not run_dir.is_dir():
        continue

    rec = collect_record(run_dir)
    if rec is not None:
        records.append(rec)

df = pd.DataFrame(records)

if df.empty:
    raise RuntimeError("No CPU sweep runs found.")

# Make sure expected columns exist even if several sacct calls fail.
expected_cols = [
    "run_name",
    "run_version",
    "sfincs_job_id",
    "sfincs_cpus",
    "state",
    "status",
    "total_queue_wait_min",
    "eligible_queue_wait_min",
    "wait_min",
    "dependency_or_hold_wait_min",
    "reason",
]

for col in expected_cols:
    if col not in df.columns:
        df[col] = None

print("\n=== Wait-time audit: all CPU sweep SFINCS jobs ===")
print(df[expected_cols].sort_values(["run_version", "sfincs_cpus"]).to_string(index=False))

bad_sacct = df[df["status"] == "skip_no_sacct"].copy()
if not bad_sacct.empty:
    print("\n=== sacct problems ===")
    print(bad_sacct[["run_name", "sfincs_job_id", "reason"]].to_string(index=False))

plot_df = df.copy()

if ONLY_STARTED_JOBS:
    plot_df = plot_df[plot_df["started"] == True].copy()

plot_df = plot_df.dropna(subset=["wait_min", "sfincs_cpus"])

if plot_df.empty:
    raise RuntimeError(
        "No started jobs with wait time available. "
        "Try again after jobs start, or inspect the sacct problems printed above."
    )

plot_df = plot_df.sort_values(["run_version", "sfincs_cpus"])


# =============================================================================
# Plot: wait time
# =============================================================================

plt.figure(figsize=(9.5, 5.8))

version_colors = {
    "001": "tab:blue",
    "002": "tab:orange",
    "003": "tab:green",
    "004": "tab:red",
    "005": "tab:purple",
}

for version, group in plot_df.groupby("run_version"):
    group = group.sort_values(["sfincs_cpus", "run_name"])
    color = version_colors.get(version, None)

    plt.scatter(
        group["sfincs_cpus"],
        group["wait_min"],
        s=70,
        label=f"Run version {version}",
        color=color,
    )

    if len(group) > 1:
        plt.plot(
            group["sfincs_cpus"],
            group["wait_min"],
            linewidth=1,
            alpha=0.55,
            color=color,
        )

    if ANNOTATE_POINTS:
        for _, row in group.iterrows():
            label = f"{row['wait_min']:.1f} min"
            plt.annotate(
                label,
                (row["sfincs_cpus"], row["wait_min"]),
                textcoords="offset points",
                xytext=(6, 5),
                fontsize=8,
            )

plt.xlabel("SFINCS CPUs requested / allocated")
plt.ylabel("Wait time before SFINCS start (minutes)")
plt.title("Harvey CPU Sweep: SFINCS Wait Time vs CPU Count")
plt.grid(True, alpha=0.3)
plt.legend(title="Run version")

plt.tight_layout()
plt.show()


# =============================================================================
# Optional plot: total Submit -> Start wait
# =============================================================================

total_df = df.dropna(subset=["total_queue_wait_min", "sfincs_cpus"]).copy()

if not total_df.empty:
    plt.figure(figsize=(9.5, 5.8))

    for version, group in total_df.groupby("run_version"):
        group = group.sort_values(["sfincs_cpus", "run_name"])
        color = version_colors.get(version, None)

        plt.scatter(
            group["sfincs_cpus"],
            group["total_queue_wait_min"],
            s=70,
            label=f"Run version {version}",
            color=color,
        )

        if len(group) > 1:
            plt.plot(
                group["sfincs_cpus"],
                group["total_queue_wait_min"],
                linewidth=1,
                alpha=0.55,
                color=color,
            )

    plt.xlabel("SFINCS CPUs requested / allocated")
    plt.ylabel("Total Submit-to-Start wait (minutes)")
    plt.title("Harvey CPU Sweep: Total SFINCS Submit-to-Start Wait")
    plt.grid(True, alpha=0.3)
    plt.legend(title="Run version")

    plt.tight_layout()
    plt.show()