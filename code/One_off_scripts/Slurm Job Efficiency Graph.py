#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# %%
from pathlib import Path
from datetime import datetime
import json
import math
import re
import shutil
import subprocess
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# USER SETTINGS
# =============================================================================

RUN_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs")

RUN_NAME_PATTERN = re.compile(
    r"^launcher_test_(?P<cpu>\d+)_CPU_harvey_(?P<rep>\d{3})$"
)

# You said the old bad folders were deleted, so leave this empty.
EXCLUDE_RUNS = set()

# Only trust solver jobs that completed and produced SFINCS output.
REQUIRE_COMPLETED = True
REQUIRE_EXIT_CODE_ZERO = True
REQUIRE_OUTPUT_FILES = True

# Check run_config.json if present and require sfincs_cpus_per_task to match the run name.
REQUIRE_CONFIG_CPU_MATCH_IF_CONFIG_EXISTS = True

# CPU budget for the runs/hour estimate.
# Use 800 if you want practical breathing room under the 1000 CPU association cap.
CPU_BUDGET = 900

# Average by CPU after filtering.
AVERAGE_METHOD = "mean"   # "mean" or "median"

# Minimum number of good non-outlier runs required to include a CPU count.
# Keep 1 while exploring. Use 2 or 3 when enough replicates exist.
MIN_GOOD_RUNS_PER_CPU = 3


# =============================================================================
# WAIT TIME OPTIONS
# =============================================================================

# Default is clean solver-only optimization.
INCLUDE_WAIT_TIME = False

# If INCLUDE_WAIT_TIME = True, choose how wait is included.
#
# "measured_by_cpu":
#     use average measured wait for each CPU count.
#
# "flat_average":
#     use one flat wait value equal to the average measured wait across all CPU counts.
#
# "cap_at_flat_average":
#     use measured wait by CPU, but cap high wait at the flat average.
#
# "flat_value":
#     use MANUAL_FLAT_WAIT_MIN for every CPU count.
WAIT_POLICY = "measured_by_cpu"

MANUAL_FLAT_WAIT_MIN = 10.0

# "eligible" means Eligible -> Start, preferred for dependency chains.
# "total" means Submit -> Start.
WAIT_METRIC = "eligible"


# =============================================================================
# OUTLIER OPTIONS
# =============================================================================

REMOVE_OUTLIERS = True

# This script uses a curve-residual outlier filter:
# 1. Gather all good completed runs.
# 2. Fit a rough runtime curve to CPU medians.
# 3. Remove raw runs that are much slower/faster than the rough curve.
# 4. Average the remaining runs by CPU.
#
# This works better than per-CPU MAD when some CPU counts have only 1-2 replicates.
DROP_SLOW_OUTLIERS = True
DROP_FAST_OUTLIERS = False

# A run is a slow outlier if:
#     observed_runtime > predicted_runtime * SLOW_OUTLIER_FACTOR
SLOW_OUTLIER_FACTOR = 1.75

# A run is a fast outlier if:
#     observed_runtime < predicted_runtime / FAST_OUTLIER_FACTOR
FAST_OUTLIER_FACTOR = 2.00

# Absolute sanity bounds. These are intentionally loose.
APPLY_ABSOLUTE_RUNTIME_LIMITS = False
MIN_RUNTIME_MIN = 1.0
MAX_RUNTIME_MIN = 500.0


# =============================================================================
# CURVE FIT OPTIONS
# =============================================================================

# Runtime model:
#     runtime_min = a + b / CPU^p
#
# This forces a decreasing curve that flattens, which is a reasonable shape
# for parallel scaling. p is chosen by grid search.
FIT_P_MIN = 0.05
FIT_P_MAX = 3.00
FIT_P_STEPS = 350

# Weight final fit by number of good runs per CPU count.
WEIGHT_FINAL_FIT_BY_REPLICATES = True

# Fit/plot CPU range. None means observed min/max.
PLOT_CPU_MIN = None
PLOT_CPU_MAX = None

# Do not mark "best" on plot unless you want it.
SHOW_OPTIMUM_MARKER = False


# =============================================================================
# PLOT COLORS
# =============================================================================

COLOR_RAW = "0.70"
COLOR_OUTLIER = "tab:red"

COLOR_AVG_WALL = "tab:green"
COLOR_FIT_WALL = "darkgreen"

COLOR_RUNS_PER_HOUR = "tab:orange"
COLOR_FIT_RUNS_PER_HOUR = "darkorange"

COLOR_CPU_HOURS = "tab:blue"


# =============================================================================
# SAVE OPTIONS
# =============================================================================

OUTPUT_DIR = RUN_ROOT / "_cpu_sweep_analysis"
SAVE_CSV = True
SAVE_PLOTS = False


# =============================================================================
# HELPERS — parsing / Slurm / run validation
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

        # Important: only keep actual numeric Slurm job IDs.
        if re.fullmatch(r"\d+", value):
            out[key] = value

    return out


def parse_elapsed_to_seconds(elapsed: str):
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

        parts = [float(p) for p in time_part.split(":")]

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


def parse_slurm_datetime(value: str):
    if value is None:
        return None

    value = str(value).strip()

    if not value or value.lower() in {"unknown", "none", "n/a", "null"}:
        return None

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


def output_files_exist(run_dir: Path) -> bool:
    candidates = [
        run_dir / "model" / "sfincs_map.nc",
        run_dir / "model" / "sfincs_his.nc",
    ]

    return any(path.exists() and path.stat().st_size > 0 for path in candidates)


def read_config_cpu(run_dir: Path):
    config_path = run_dir / "run_config.json"

    if not config_path.exists():
        return None

    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return None

    value = cfg.get("sfincs_cpus_per_task")

    try:
        return int(value)
    except Exception:
        return None


def sacct_for_job(job_id: str):
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

    # Prefer the main job row, not .batch/.extern steps.
    for row in rows:
        if row["JobIDRaw"] == str(job_id):
            return row, ""

    for row in rows:
        if "." not in row["JobIDRaw"]:
            return row, ""

    return rows[0], ""


def collect_record(run_dir: Path):
    parsed = parse_run_name(run_dir.name)

    if parsed is None:
        return None

    if run_dir.name in EXCLUDE_RUNS:
        return None

    cpu_from_name = parsed["cpu_from_name"]
    run_version = parsed["run_version"]

    base = {
        "run_name": run_dir.name,
        "run_dir": str(run_dir),
        "run_version": run_version,
        "cpu_from_name": cpu_from_name,
        "sfincs_cpus": cpu_from_name,
        "config_cpu": np.nan,
        "sfincs_job_id": "",
        "state": "",
        "exit_code": "",
        "elapsed": "",
        "solver_runtime_min": np.nan,
        "solver_wall_hours": np.nan,
        "total_wait_min": np.nan,
        "eligible_wait_min": np.nan,
        "wait_min": np.nan,
        "has_outputs": False,
        "good_finished_run": False,
        "skip_reason": "",
    }

    config_cpu = read_config_cpu(run_dir)
    if config_cpu is not None:
        base["config_cpu"] = config_cpu

        if REQUIRE_CONFIG_CPU_MATCH_IF_CONFIG_EXISTS and config_cpu != cpu_from_name:
            base["skip_reason"] = f"config CPU {config_cpu} != run-name CPU {cpu_from_name}"
            return base

    job_ids = read_job_ids(run_dir)
    sfincs_job_id = job_ids.get("sfincs")

    if not sfincs_job_id:
        base["skip_reason"] = "missing numeric sfincs job id"
        return base

    base["sfincs_job_id"] = sfincs_job_id

    sacct, reason = sacct_for_job(sfincs_job_id)

    if sacct is None:
        base["skip_reason"] = reason
        return base

    state = sacct.get("State", "")
    exit_code = sacct.get("ExitCode", "")
    elapsed = sacct.get("Elapsed", "")

    elapsed_seconds = parse_elapsed_to_seconds(elapsed)

    submit = parse_slurm_datetime(sacct.get("Submit"))
    eligible = parse_slurm_datetime(sacct.get("Eligible"))
    start = parse_slurm_datetime(sacct.get("Start"))

    total_wait_min = np.nan
    eligible_wait_min = np.nan

    if submit and start:
        total_wait_min = (start - submit).total_seconds() / 60

    if eligible and start:
        eligible_wait_min = (start - eligible).total_seconds() / 60

    if WAIT_METRIC == "eligible":
        wait_min = eligible_wait_min
        if pd.isna(wait_min):
            wait_min = total_wait_min
    elif WAIT_METRIC == "total":
        wait_min = total_wait_min
    else:
        raise ValueError(f"Invalid WAIT_METRIC: {WAIT_METRIC}")

    try:
        alloc_cpus = int(sacct.get("AllocCPUS") or 0)
    except Exception:
        alloc_cpus = 0

    if alloc_cpus <= 0:
        alloc_cpus = cpu_from_name

    # For consistency, trust the CPU count encoded in the controlled run name
    # unless sacct disagrees. If it disagrees, skip the run.
    if alloc_cpus != cpu_from_name:
        base.update({
            "state": state,
            "exit_code": exit_code,
            "elapsed": elapsed,
            "sfincs_cpus": alloc_cpus,
            "skip_reason": f"sacct AllocCPUS {alloc_cpus} != run-name CPU {cpu_from_name}",
        })
        return base

    has_outputs = output_files_exist(run_dir)

    solver_runtime_min = np.nan
    if elapsed_seconds is not None:
        solver_runtime_min = elapsed_seconds / 60

    good = True

    if REQUIRE_COMPLETED and not state.startswith("COMPLETED"):
        good = False
        reason = "not COMPLETED"

    elif REQUIRE_EXIT_CODE_ZERO and exit_code != "0:0":
        good = False
        reason = f"exit code {exit_code}"

    elif pd.isna(solver_runtime_min) or solver_runtime_min <= 0:
        good = False
        reason = "bad elapsed runtime"

    elif REQUIRE_OUTPUT_FILES and not has_outputs:
        good = False
        reason = "missing sfincs_map.nc/sfincs_his.nc output"

    else:
        reason = ""

    base.update({
        "sfincs_cpus": cpu_from_name,
        "state": state,
        "exit_code": exit_code,
        "elapsed": elapsed,
        "solver_runtime_min": solver_runtime_min,
        "solver_wall_hours": solver_runtime_min / 60 if not pd.isna(solver_runtime_min) else np.nan,
        "total_wait_min": total_wait_min,
        "eligible_wait_min": eligible_wait_min,
        "wait_min": wait_min,
        "has_outputs": has_outputs,
        "good_finished_run": good,
        "skip_reason": reason,
    })

    return base


# =============================================================================
# FITTING HELPERS
# =============================================================================

def fit_inverse_power(cpu_values, runtime_min_values, weights=None):
    """
    Fit:
        runtime_min = a + b / CPU^p

    p is chosen by grid search.
    For each p, a and b are solved by weighted least squares.
    """
    x = np.asarray(cpu_values, dtype=float)
    y = np.asarray(runtime_min_values, dtype=float)

    if weights is None:
        w = np.ones_like(y)
    else:
        w = np.asarray(weights, dtype=float)

    mask = (
        np.isfinite(x)
        & np.isfinite(y)
        & np.isfinite(w)
        & (x > 0)
        & (y > 0)
        & (w > 0)
    )

    x = x[mask]
    y = y[mask]
    w = w[mask]

    if len(x) < 3:
        raise ValueError("Need at least 3 CPU points to fit runtime curve.")

    best = None

    for p in np.linspace(FIT_P_MIN, FIT_P_MAX, FIT_P_STEPS):
        z = 1.0 / (x ** p)
        X = np.column_stack([np.ones_like(z), z])

        sqrt_w = np.sqrt(w)
        Xw = X * sqrt_w[:, None]
        yw = y * sqrt_w

        try:
            coef, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
        except Exception:
            continue

        a, b = coef

        # Require physically reasonable decreasing curve.
        if b <= 0:
            continue

        pred = a + b * z

        if np.any(pred <= 0):
            continue

        rmse = np.sqrt(np.average((y - pred) ** 2, weights=w))

        if best is None or rmse < best["rmse"]:
            best = {
                "a": float(a),
                "b": float(b),
                "p": float(p),
                "rmse": float(rmse),
            }

    if best is None:
        raise ValueError("Could not find a valid inverse-power fit.")

    def predict(cpu_new):
        cpu_new = np.asarray(cpu_new, dtype=float)
        return best["a"] + best["b"] / (cpu_new ** best["p"])

    best["predict"] = predict
    return best


def average_group(values):
    values = pd.to_numeric(values, errors="coerce").dropna()

    if values.empty:
        return np.nan

    if AVERAGE_METHOD == "mean":
        return values.mean()

    if AVERAGE_METHOD == "median":
        return values.median()

    raise ValueError(f"Invalid AVERAGE_METHOD: {AVERAGE_METHOD}")


def make_cpu_averages(df):
    rows = []

    for cpu, group in df.groupby("sfincs_cpus"):
        runtimes = group["solver_runtime_min"].dropna()
        waits = group["wait_min"].dropna()

        rows.append({
            "sfincs_cpus": int(cpu),
            "n_runs": int(runtimes.count()),
            "avg_runtime_min": average_group(runtimes),
            "median_runtime_min": runtimes.median() if not runtimes.empty else np.nan,
            "min_runtime_min": runtimes.min() if not runtimes.empty else np.nan,
            "max_runtime_min": runtimes.max() if not runtimes.empty else np.nan,
            "std_runtime_min": runtimes.std(ddof=1) if runtimes.count() > 1 else np.nan,
            "avg_wait_min": average_group(waits),
            "run_versions": ", ".join(sorted(group["run_version"].astype(str).unique())),
        })

    out = pd.DataFrame(rows).sort_values("sfincs_cpus").reset_index(drop=True)

    if not out.empty:
        out["avg_wall_hours"] = out["avg_runtime_min"] / 60
        out["cpu_hours_per_run"] = out["sfincs_cpus"] * out["avg_wall_hours"]

    return out


def choose_wait_for_averages(avg_df):
    if not INCLUDE_WAIT_TIME:
        return pd.Series(0.0, index=avg_df.index), "solver runtime only; wait excluded"

    measured = avg_df["avg_wait_min"].copy()

    if measured.notna().any():
        flat_average = measured.mean(skipna=True)
    else:
        flat_average = 0.0

    if WAIT_POLICY == "measured_by_cpu":
        return measured.fillna(flat_average), "solver runtime + measured average wait by CPU"

    if WAIT_POLICY == "flat_average":
        return pd.Series(flat_average, index=avg_df.index), (
            f"solver runtime + flat average wait ({flat_average:.2f} min)"
        )

    if WAIT_POLICY == "cap_at_flat_average":
        return measured.fillna(flat_average).clip(upper=flat_average), (
            f"solver runtime + measured wait capped at flat average ({flat_average:.2f} min)"
        )

    if WAIT_POLICY == "flat_value":
        return pd.Series(float(MANUAL_FLAT_WAIT_MIN), index=avg_df.index), (
            f"solver runtime + flat wait value ({float(MANUAL_FLAT_WAIT_MIN):.2f} min)"
        )

    raise ValueError(f"Invalid WAIT_POLICY: {WAIT_POLICY}")


# =============================================================================
# SCAN RUNS
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

df_all = pd.DataFrame(records)

if df_all.empty:
    raise RuntimeError("No true CPU sweep runs found.")

print("\n=== All matched true CPU-sweep SFINCS jobs ===")
print(df_all[
    [
        "run_name",
        "run_version",
        "sfincs_job_id",
        "sfincs_cpus",
        "state",
        "exit_code",
        "elapsed",
        "solver_runtime_min",
        "has_outputs",
        "good_finished_run",
        "skip_reason",
    ]
].sort_values(["run_version", "sfincs_cpus"]).to_string(index=False))

good_df = df_all[df_all["good_finished_run"] == True].copy()

if good_df.empty:
    raise RuntimeError("No good finished SFINCS solver runs found.")

good_df["solver_runtime_min"] = pd.to_numeric(good_df["solver_runtime_min"], errors="coerce")
good_df["wait_min"] = pd.to_numeric(good_df["wait_min"], errors="coerce")
good_df["sfincs_cpus"] = pd.to_numeric(good_df["sfincs_cpus"], errors="coerce").astype(int)

good_df = good_df.dropna(subset=["sfincs_cpus", "solver_runtime_min"])

if good_df.empty:
    raise RuntimeError("No good runs remain after numeric cleanup.")


# =============================================================================
# ROUGH FIT FOR OUTLIER DETECTION
# =============================================================================

good_df["outlier"] = False
good_df["rough_pred_runtime_min"] = np.nan
good_df["runtime_over_rough_pred"] = np.nan

initial_avg = make_cpu_averages(good_df)

if len(initial_avg) >= 3:
    try:
        rough_fit = fit_inverse_power(
            initial_avg["sfincs_cpus"],
            initial_avg["median_runtime_min"],
            weights=initial_avg["n_runs"],
        )

        pred = rough_fit["predict"](good_df["sfincs_cpus"].to_numpy(dtype=float))
        good_df["rough_pred_runtime_min"] = pred
        good_df["runtime_over_rough_pred"] = good_df["solver_runtime_min"] / pred

        if REMOVE_OUTLIERS:
            outlier = pd.Series(False, index=good_df.index)

            if DROP_SLOW_OUTLIERS:
                outlier = outlier | (
                    good_df["solver_runtime_min"]
                    > good_df["rough_pred_runtime_min"] * SLOW_OUTLIER_FACTOR
                )

            if DROP_FAST_OUTLIERS:
                outlier = outlier | (
                    good_df["solver_runtime_min"]
                    < good_df["rough_pred_runtime_min"] / FAST_OUTLIER_FACTOR
                )

            good_df["outlier"] = outlier.fillna(False)

    except Exception as exc:
        warnings.warn(f"Rough outlier fit failed; no curve-based outliers removed: {exc}")

if APPLY_ABSOLUTE_RUNTIME_LIMITS:
    absolute_bad = (
        (good_df["solver_runtime_min"] < MIN_RUNTIME_MIN)
        | (good_df["solver_runtime_min"] > MAX_RUNTIME_MIN)
    )
    good_df["outlier"] = good_df["outlier"] | absolute_bad.fillna(False)

clean_df = good_df[~good_df["outlier"]].copy()
outlier_df = good_df[good_df["outlier"]].copy()

print("\n=== Good finished runs before outlier filtering ===")
print(good_df[
    [
        "run_name",
        "run_version",
        "sfincs_cpus",
        "solver_runtime_min",
        "rough_pred_runtime_min",
        "runtime_over_rough_pred",
        "outlier",
    ]
].sort_values(["sfincs_cpus", "run_version"]).to_string(index=False))

if REMOVE_OUTLIERS and not outlier_df.empty:
    print("\n=== Removed outliers ===")
    print(outlier_df[
        [
            "run_name",
            "run_version",
            "sfincs_cpus",
            "solver_runtime_min",
            "rough_pred_runtime_min",
            "runtime_over_rough_pred",
        ]
    ].sort_values(["sfincs_cpus", "run_version"]).to_string(index=False))
elif REMOVE_OUTLIERS:
    print("\nNo outliers removed by current settings.")
else:
    print("\nOutlier removal is OFF.")

if clean_df.empty:
    raise RuntimeError("No good finished runs remain after outlier filtering.")


# =============================================================================
# AVERAGE BY CPU AND FINAL FIT
# =============================================================================

avg_df = make_cpu_averages(clean_df)

avg_df = avg_df[avg_df["n_runs"] >= MIN_GOOD_RUNS_PER_CPU].copy()

if avg_df.empty:
    raise RuntimeError(
        "No CPU counts remain after MIN_GOOD_RUNS_PER_CPU filtering."
    )

wait_used_min, effective_label = choose_wait_for_averages(avg_df)
avg_df["wait_used_min"] = wait_used_min
avg_df["effective_runtime_min"] = avg_df["avg_runtime_min"] + avg_df["wait_used_min"]
avg_df["effective_wall_hours"] = avg_df["effective_runtime_min"] / 60

# Important:
# - avg_wall_hours is actual wall-clock hours per run.
# - cpu_hours_per_run is allocation cost = CPU count × wall hours.
# - runs_per_hour_at_budget is campaign throughput estimate under CPU_BUDGET.
avg_df["effective_cpu_hours_per_run"] = (
    avg_df["sfincs_cpus"] * avg_df["effective_wall_hours"]
)
avg_df["runs_per_hour_at_budget"] = (
    CPU_BUDGET / avg_df["effective_cpu_hours_per_run"]
)

if len(avg_df) < 3:
    raise RuntimeError("Need at least 3 CPU averages to fit final runtime curve.")

weights = avg_df["n_runs"] if WEIGHT_FINAL_FIT_BY_REPLICATES else None

final_fit = fit_inverse_power(
    avg_df["sfincs_cpus"],
    avg_df["avg_runtime_min"],
    weights=weights,
)

cpu_min = int(avg_df["sfincs_cpus"].min() if PLOT_CPU_MIN is None else PLOT_CPU_MIN)
cpu_max = int(avg_df["sfincs_cpus"].max() if PLOT_CPU_MAX is None else PLOT_CPU_MAX)

fit_cpus = np.arange(cpu_min, cpu_max + 1, dtype=float)
fit_runtime_min = final_fit["predict"](fit_cpus)
fit_runtime_min = np.maximum(fit_runtime_min, 0.001)

# For fitted optimization, use a simple wait assumption if enabled.
if INCLUDE_WAIT_TIME:
    if WAIT_POLICY == "flat_value":
        fit_wait_min = np.full_like(fit_runtime_min, float(MANUAL_FLAT_WAIT_MIN))

    else:
        # Interpolate the wait values chosen for the CPU averages.
        fit_wait_min = np.interp(
            fit_cpus,
            avg_df["sfincs_cpus"].to_numpy(dtype=float),
            avg_df["wait_used_min"].to_numpy(dtype=float),
        )
else:
    fit_wait_min = np.zeros_like(fit_runtime_min)

fit_effective_runtime_min = fit_runtime_min + fit_wait_min
fit_wall_hours = fit_effective_runtime_min / 60
fit_cpu_hours_per_run = fit_cpus * fit_wall_hours
fit_runs_per_hour = CPU_BUDGET / fit_cpu_hours_per_run

fit_df = pd.DataFrame({
    "sfincs_cpus": fit_cpus.astype(int),
    "fit_runtime_min": fit_runtime_min,
    "fit_wall_hours": fit_wall_hours,
    "fit_wait_min": fit_wait_min,
    "fit_cpu_hours_per_run": fit_cpu_hours_per_run,
    "fit_runs_per_hour_at_budget": fit_runs_per_hour,
})

best_fit_idx = fit_df["fit_runs_per_hour_at_budget"].idxmax()
best_fit_cpu = int(fit_df.loc[best_fit_idx, "sfincs_cpus"])

fastest_fit_idx = fit_df["fit_runtime_min"].idxmin()
fastest_fit_cpu = int(fit_df.loc[fastest_fit_idx, "sfincs_cpus"])

lowest_cpu_hour_idx = fit_df["fit_cpu_hours_per_run"].idxmin()
lowest_cpu_hour_cpu = int(fit_df.loc[lowest_cpu_hour_idx, "sfincs_cpus"])


# =============================================================================
# PRINT SUMMARY
# =============================================================================

print("\n=== Averaged good finished runs by CPU ===")
print(avg_df[
    [
        "sfincs_cpus",
        "n_runs",
        "avg_runtime_min",
        "avg_wall_hours",
        "cpu_hours_per_run",
        "wait_used_min",
        "effective_wall_hours",
        "effective_cpu_hours_per_run",
        "runs_per_hour_at_budget",
        "run_versions",
    ]
].to_string(index=False))

print("\n=== Final fitted runtime model ===")
print(
    "runtime_min = "
    f"{final_fit['a']:.3f} + {final_fit['b']:.3f} / CPU^{final_fit['p']:.3f}"
)
print(f"Fit RMSE on averaged CPU points: {final_fit['rmse']:.3f} minutes")
print(f"Effective time policy: {effective_label}")
print(f"CPU budget: {CPU_BUDGET} CPUs")

print("\n=== Simple optimization check from fitted curve ===")
print(
    f"Best fitted campaign throughput: {best_fit_cpu} CPUs "
    f"= {fit_df.loc[best_fit_idx, 'fit_runs_per_hour_at_budget']:.2f} runs/hour "
    f"at {CPU_BUDGET} CPUs"
)
print(
    f"Lowest fitted CPU-hours/run: {lowest_cpu_hour_cpu} CPUs "
    f"= {fit_df.loc[lowest_cpu_hour_idx, 'fit_cpu_hours_per_run']:.3f} CPU-hours/run"
)
print(
    f"Fastest fitted wall runtime: {fastest_fit_cpu} CPUs "
    f"= {fit_df.loc[fastest_fit_idx, 'fit_runtime_min']:.2f} minutes/run"
)

print("\nNOTE ON UNITS:")
print("- Wall hours/run is actual clock time for one SFINCS solve.")
print("- CPU-hours/run is allocation cost: CPUs × wall-hours.")
print("- Runs/hour at budget is CPU_BUDGET / CPU-hours-per-run.")
print("- So CPU-hours/run can be much larger than wall-hours/run.")


# =============================================================================
# SAVE CSVs
# =============================================================================

if SAVE_CSV:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = OUTPUT_DIR / "cpu_sweep_good_runs_with_outliers.csv"
    avg_path = OUTPUT_DIR / "cpu_sweep_average_by_cpu.csv"
    fit_path = OUTPUT_DIR / "cpu_sweep_fitted_curve_optimization.csv"

    good_df.to_csv(raw_path, index=False)
    avg_df.to_csv(avg_path, index=False)
    fit_df.to_csv(fit_path, index=False)

    print("\nSaved CSVs:")
    print(raw_path)
    print(avg_path)
    print(fit_path)


# =============================================================================
# PLOT 1 — Wall hours/run and runs/hour
# =============================================================================

fig, ax_left = plt.subplots(figsize=(12, 7))

# Raw good runs as faint points, in wall-hours.
ax_left.scatter(
    clean_df["sfincs_cpus"],
    clean_df["solver_runtime_min"] / 60,
    s=28,
    alpha=0.32,
    color=COLOR_RAW,
    label="Good finished raw runs",
)

if not outlier_df.empty:
    ax_left.scatter(
        outlier_df["sfincs_cpus"],
        outlier_df["solver_runtime_min"] / 60,
        s=70,
        marker="x",
        alpha=0.85,
        color=COLOR_OUTLIER,
        label="Removed runtime outliers",
    )

# CPU averages.
ax_left.plot(
    avg_df["sfincs_cpus"],
    avg_df["avg_wall_hours"],
    marker="o",
    linewidth=1.8,
    color=COLOR_AVG_WALL,
    label="Average wall hours/run",
)

# Fitted wall time curve.
ax_left.plot(
    fit_df["sfincs_cpus"],
    fit_df["fit_wall_hours"],
    linewidth=2.4,
    color=COLOR_FIT_WALL,
    label="Fitted wall hours/run",
)

ax_left.set_xlabel("SFINCS CPUs requested / allocated")
ax_left.set_ylabel("Solver wall hours per run", color=COLOR_FIT_WALL)
ax_left.tick_params(axis="y", labelcolor=COLOR_FIT_WALL)
ax_left.grid(True, alpha=0.28)

ax_right = ax_left.twinx()

# Average-estimated runs/hour.
ax_right.plot(
    avg_df["sfincs_cpus"],
    avg_df["runs_per_hour_at_budget"],
    marker="s",
    linewidth=1.7,
    color=COLOR_RUNS_PER_HOUR,
    label=f"Average-estimated runs/hour at {CPU_BUDGET} CPUs",
)

# Fitted-estimated runs/hour.
ax_right.plot(
    fit_df["sfincs_cpus"],
    fit_df["fit_runs_per_hour_at_budget"],
    linestyle="--",
    linewidth=2.2,
    color=COLOR_FIT_RUNS_PER_HOUR,
    label=f"Fit-estimated runs/hour at {CPU_BUDGET} CPUs",
)

ax_right.set_ylabel(
    f"Estimated campaign throughput, runs/hour at {CPU_BUDGET} CPUs",
    color=COLOR_FIT_RUNS_PER_HOUR,
)
ax_right.tick_params(axis="y", labelcolor=COLOR_FIT_RUNS_PER_HOUR)

if SHOW_OPTIMUM_MARKER:
    best_row = fit_df.loc[best_fit_idx]
    ax_right.axvline(best_fit_cpu, linestyle=":", color=COLOR_FIT_RUNS_PER_HOUR, alpha=0.75)
    ax_right.annotate(
        f"Best fit\n{best_fit_cpu} CPUs",
        xy=(best_fit_cpu, best_row["fit_runs_per_hour_at_budget"]),
        xytext=(12, 18),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->"},
        fontsize=9,
    )

lines_left, labels_left = ax_left.get_legend_handles_labels()
lines_right, labels_right = ax_right.get_legend_handles_labels()

ax_left.legend(
    lines_left + lines_right,
    labels_left + labels_right,
    loc="best",
    fontsize=9,
)

plt.title(
    "Harvey CPU Sweep: Fitted Solver Wall Time and Estimated Throughput\n"
    f"{effective_label}"
)

plt.tight_layout()

if SAVE_PLOTS:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_path = OUTPUT_DIR / "cpu_sweep_wall_hours_and_runs_per_hour.png"
    plt.savefig(plot_path, dpi=180)
    print(f"Saved plot: {plot_path}")

plt.show()


# =============================================================================
# PLOT 2 — CPU-hours/run and runs/hour
# =============================================================================

fig, ax_left = plt.subplots(figsize=(12, 7))

ax_left.plot(
    avg_df["sfincs_cpus"],
    avg_df["effective_cpu_hours_per_run"],
    marker="o",
    linewidth=1.8,
    color=COLOR_CPU_HOURS,
    label="Average CPU-hours/run",
)

ax_left.plot(
    fit_df["sfincs_cpus"],
    fit_df["fit_cpu_hours_per_run"],
    linewidth=2.4,
    color="navy",
    label="Fitted CPU-hours/run",
)

ax_left.set_xlabel("SFINCS CPUs requested / allocated")
ax_left.set_ylabel("CPU-hours per run", color="navy")
ax_left.tick_params(axis="y", labelcolor="navy")
ax_left.grid(True, alpha=0.28)

ax_right = ax_left.twinx()

ax_right.plot(
    avg_df["sfincs_cpus"],
    avg_df["runs_per_hour_at_budget"],
    marker="s",
    linewidth=1.7,
    color=COLOR_RUNS_PER_HOUR,
    label=f"Average-estimated runs/hour at {CPU_BUDGET} CPUs",
)

ax_right.plot(
    fit_df["sfincs_cpus"],
    fit_df["fit_runs_per_hour_at_budget"],
    linestyle="--",
    linewidth=2.2,
    color=COLOR_FIT_RUNS_PER_HOUR,
    label=f"Fit-estimated runs/hour at {CPU_BUDGET} CPUs",
)

ax_right.set_ylabel(
    f"Estimated campaign throughput, runs/hour at {CPU_BUDGET} CPUs",
    color=COLOR_FIT_RUNS_PER_HOUR,
)
ax_right.tick_params(axis="y", labelcolor=COLOR_FIT_RUNS_PER_HOUR)

if SHOW_OPTIMUM_MARKER:
    best_row = fit_df.loc[best_fit_idx]
    ax_right.axvline(best_fit_cpu, linestyle=":", color=COLOR_FIT_RUNS_PER_HOUR, alpha=0.75)

lines_left, labels_left = ax_left.get_legend_handles_labels()
lines_right, labels_right = ax_right.get_legend_handles_labels()

ax_left.legend(
    lines_left + lines_right,
    labels_left + labels_right,
    loc="best",
    fontsize=9,
)

plt.title(
    "Harvey CPU Sweep: CPU-Hours per Run and Estimated Throughput\n"
    f"{effective_label}"
)

plt.tight_layout()

if SAVE_PLOTS:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_path = OUTPUT_DIR / "cpu_sweep_cpu_hours_and_runs_per_hour.png"
    plt.savefig(plot_path, dpi=180)
    print(f"Saved plot: {plot_path}")

plt.show()