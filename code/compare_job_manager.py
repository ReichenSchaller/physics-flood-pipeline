#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 28 17:52:53 2026

@author: epsilon


#!/usr/bin/env python3

compare_job_manager.py

Backend helper for SFINCS web-launcher Compare Runs mode.

Purpose:
  - Recommend Slurm settings from compare level + number of runs.
  - Submit a Slurm comparison job.
  - Compare N runs as baseline-vs-each-other.
  - Write status JSON for the web UI to poll.
  - Write final result JSON for the result page.
  - Capture basic utilization info from /usr/bin/time -v.

This is intentionally separate from Flask. Flask should call this helper instead
of duplicating Slurm/job/result logic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PIPELINE_ROOT = Path("/proj/zefflab/projects/Flooding/pipeline")
CODE_ROOT = PIPELINE_ROOT / "code"
RUN_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs")
COMPARE_ROOT = RUN_ROOT / "_compare_jobs"

PYTHON = PIPELINE_ROOT / "envs" / "sfincs" / "bin" / "python"
COMPARE_SCRIPT = CODE_ROOT / "compare_sfincs_netcdf_numeric.py"

ALLOWED_RUN_ROOTS = [
    Path("/proj/zefflab/projects/Flooding/sfincs_runs"),
    Path("/work/users/e/p/epsilon/sfincs_runs"),
]

VALID_LEVELS = ["quick", "standard", "full"]

MAX_RUNS_DEFAULT = 12


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(data), indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def clean_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip())
    text = text.strip("_")
    return text[:80] or "run"

def short_run_display_name(name: str, max_prefix: int = 28) -> str:
    """
    Shorten long run folder names for Compare Mode display.

    Keeps the recognizable beginning and preserves a trailing run number like
    001, 007, 014, etc.
    """
    text = str(name or "").strip()
    if not text:
        return "run"

    # Preserve common trailing run numbers like _001, -007, .014.
    m = re.search(r"([_.-]?)([0-9]{3,4})$", text)
    if m and len(text) > max_prefix + 6:
        suffix = m.group(2)
        prefix = text[:max_prefix].rstrip("_.- ")
        return f"{prefix}...{suffix}"

    # Fallback for names without a trailing numeric suffix.
    max_total = max_prefix + 10
    if len(text) <= max_total:
        return text

    return f"{text[:max_prefix].rstrip('_.- ')}...{text[-8:]}"

def resolve_run_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def is_allowed_run_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False

    for root in ALLOWED_RUN_ROOTS:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue

    return False


def validate_runs(run_strings: List[str], max_runs: int = MAX_RUNS_DEFAULT) -> List[Path]:
    if len(run_strings) < 2:
        raise ValueError("Select at least two runs.")

    if len(run_strings) > max_runs:
        raise ValueError(f"Too many runs selected. Current cap is {max_runs}.")

    runs = [resolve_run_path(s) for s in run_strings]

    seen = set()
    clean_runs = []
    for run in runs:
        key = str(run)
        if key in seen:
            raise ValueError(f"Duplicate run selected: {run}")
        seen.add(key)
        clean_runs.append(run)

    for run in clean_runs:
        if not run.exists():
            raise ValueError(f"Run folder does not exist: {run}")

        model = run / "model"
        if not model.exists() and not (run / "sfincs.inp").exists():
            raise ValueError(f"Run does not look like a SFINCS run folder: {run}")

        if not is_allowed_run_path(run):
            raise ValueError(
                "Run path is outside allowed roots. "
                f"Path: {run}. Allowed roots: {', '.join(str(p) for p in ALLOWED_RUN_ROOTS)}"
            )

    return clean_runs


def parse_mem_gb(mem_text: str) -> Optional[float]:
    """
    Parse common Slurm mem strings like:
      64G, 64000M, 128GB
    """
    if not mem_text:
        return None

    text = mem_text.strip().upper()
    m = re.fullmatch(r"([0-9.]+)\s*([KMGTP]?B?|)", text)
    if not m:
        return None

    value = float(m.group(1))
    unit = m.group(2)

    if unit in ["", "M", "MB"]:
        return value / 1024.0
    if unit in ["G", "GB"]:
        return value
    if unit in ["T", "TB"]:
        return value * 1024.0
    if unit in ["K", "KB"]:
        return value / (1024.0 * 1024.0)

    return None


def recommend_settings(level: str, run_count: int) -> Dict[str, Any]:

    if level not in VALID_LEVELS:

        raise ValueError(f"Invalid level {level}. Choose one of {VALID_LEVELS}.")



    # Current manager compares baseline-vs-each-other sequentially, not in parallel.

    # Memory should mainly reflect one pair at a time, with only a small buffer for more pairs.

    comparisons = max(1, run_count - 1)



    if level == "quick":

        mem_gb = min(8, 2 + 0.5 * comparisons)

        cpus = 1

        time = "00:10:00"

        chunk_mb = 32

        note = "Quick compare avoids full physical array scans. Good for config/file/metadata checks."



    elif level == "standard":

        mem_gb = min(32, 7 + 1 * comparisons)

        cpus = 2

        time = "00:45:00"

        chunk_mb = 128

        note = "Standard compare scans selected physical variables only. Good default scientific check."



    else:

        mem_gb = min(64, 14 + 2 * comparisons)

        cpus = 2

        time = "02:00:00"

        chunk_mb = 128

        note = "Full compare scans all overlapping numeric NetCDF variables. Use carefully for large runs."



    return {

        "level": level,

        "run_count": run_count,

        "comparison_mode": "baseline_vs_each_other",

        "comparisons": comparisons,

        "recommended_mem": f"{int(mem_gb)}G",

        "recommended_cpus": cpus,

        "recommended_time": time,

        "chunk_mb": chunk_mb,

        "note": note,

    }





def compare_args_for_level(level: str, chunk_mb: int) -> List[str]:
    """
    Translate compare level into compare_sfincs_netcdf_numeric.py arguments.

    This assumes the compare script supports:
      --json
      --chunk-mb
      --vars
      --all-vars

    Current trick:
      quick uses a deliberately nonexistent variable name so the script still
      performs sfincs.inp, byte/file, and NetCDF metadata checks but avoids
      scanning large arrays.
    """
    base = ["--json", "--chunk-mb", str(chunk_mb)]

    if level == "quick":
        return base + ["--vars", "__quick_no_numeric_array_scan__"]

    if level == "standard":
        standard_vars = [
            "zsmax",
            "zs",
            "zb",
            "qinf",
            "point_zs",
            "point_zb",
            "point_qinf",
            "crosssection_discharge",
        ]
        return base + ["--vars", ",".join(standard_vars)]

    if level == "full":
        return base + ["--all-vars"]

    raise ValueError(f"Invalid level: {level}")


def shell_quote_list(items: List[str]) -> str:
    return " ".join(shlex.quote(str(x)) for x in items)


def make_job_dir(runs: List[Path], level: str) -> Path:
    baseline_name = clean_name(runs[0].name)
    job_dir = COMPARE_ROOT / f"compare_{level}_{baseline_name}_{timestamp_slug()}"
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def build_slurm_script(
    job_dir: Path,
    runs: List[Path],
    level: str,
    mem: str,
    cpus: int,
    time: str,
    chunk_mb: int,
) -> str:
    """
    Create a Slurm script that runs pairwise baseline-vs-each-other comparisons.

    The script writes:
      compare_status.json
      pair_001_result.json
      pair_001_stderr.log
      pair_001_time.log
      compare_result.json
    """
    baseline = runs[0]
    others = runs[1:]
    compare_extra = compare_args_for_level(level, chunk_mb)

    pairs_json = []
    for i, other in enumerate(others, start=1):
        baseline_display = short_run_display_name(baseline.name)
        other_display = short_run_display_name(other.name)

        pairs_json.append({
            "pair_index": i,

            # Internal full paths used by the compare script.
            "old_run": str(baseline),
            "new_run": str(other),

            # User-facing names for the web UI/status/result pages.
            "baseline_name": baseline.name,
            "comparison_name": other.name,
            "baseline_display": baseline_display,
            "comparison_display": other_display,
            "display_label": f"{baseline_display} vs {other_display}",

            # Keep label for backward compatibility with existing UI code.
            "label": f"{baseline_display} vs {other_display}",

            "result_file": f"pair_{i:03d}_result.json",
            "stderr_file": f"pair_{i:03d}_stderr.log",
            "time_file": f"pair_{i:03d}_time.log",
        })

    request = {
        "created_at": now_text(),
        "level": level,
        "runs": [str(r) for r in runs],
        "baseline": str(baseline),
        "comparison_mode": "baseline_vs_each_other",
        "pairs": pairs_json,
        "slurm": {
            "mem": mem,
            "cpus_per_task": cpus,
            "time": time,
        },
        "compare_script": str(COMPARE_SCRIPT),
        "python": str(PYTHON),
        "compare_extra_args": compare_extra,
        "chunk_mb": chunk_mb,
    }
    write_json(job_dir / "compare_request.json", request)

    pairs_literal = json.dumps(pairs_json)
    extra_literal = json.dumps(compare_extra)

    script = f"""#!/bin/bash
#SBATCH --job-name=sf_compare
#SBATCH --output={job_dir}/compare_stdout.log
#SBATCH --error={job_dir}/compare_stderr.log
#SBATCH --time={time}
#SBATCH --mem={mem}
#SBATCH --cpus-per-task={cpus}

set -u

JOBDIR={shlex.quote(str(job_dir))}
PY={shlex.quote(str(PYTHON))}
COMPARE_SCRIPT={shlex.quote(str(COMPARE_SCRIPT))}
LEVEL={shlex.quote(level)}
REQUEST="$JOBDIR/compare_request.json"
STATUS="$JOBDIR/compare_status.json"
FINAL="$JOBDIR/compare_result.json"

export OMP_NUM_THREADS={int(cpus)}
export OPENBLAS_NUM_THREADS={int(cpus)}
export MKL_NUM_THREADS={int(cpus)}
export NUMEXPR_NUM_THREADS={int(cpus)}

write_status() {{
  "$PY" - "$STATUS" "$1" "$2" "$3" <<'PY'
import json, sys, time
path, status, message, progress = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
data = {{
    "status": status,
    "message": message,
    "progress": progress,
    "updated_unix": time.time(),
}}
open(path, "w").write(json.dumps(data, indent=2, sort_keys=True) + "\\n")
PY
}}

write_status "running" "Starting compare job" 0

"$PY" - "$JOBDIR" "$REQUEST" <<'PY'
import json, sys
from pathlib import Path
jobdir = Path(sys.argv[1])
request = json.loads(Path(sys.argv[2]).read_text())
(jobdir / "compare_started.txt").write_text("started\\n")
PY

PAIRS_JSON={shlex.quote(pairs_literal)}
EXTRA_JSON={shlex.quote(extra_literal)}

"$PY" - "$JOBDIR" "$PY" "$COMPARE_SCRIPT" "$PAIRS_JSON" "$EXTRA_JSON" <<'PY'
import json
import subprocess
import sys
import time
from pathlib import Path

jobdir = Path(sys.argv[1])
py = sys.argv[2]
compare_script = sys.argv[3]
pairs = json.loads(sys.argv[4])
extra = json.loads(sys.argv[5])

status_path = jobdir / "compare_status.json"
total = len(pairs)

def write_status(status, message, progress, **extra_fields):
    data = {{
        "status": status,
        "message": message,
        "progress": progress,
        "current_pair": extra_fields.get("current_pair"),
        "total_pairs": total,
        "updated_unix": time.time(),
    }}
    data.update(extra_fields)
    status_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\\n")

for idx, pair in enumerate(pairs, start=1):
    progress = (idx - 1) / max(total, 1)
    write_status(
        "running",
        f"Comparing pair {{idx}}/{{total}}: {{pair['label']}}",
        progress,
        current_pair=idx,
        old_run=pair["old_run"],
        new_run=pair["new_run"],
    )

    result_path = jobdir / pair["result_file"]
    stderr_path = jobdir / pair["stderr_file"]
    time_path = jobdir / pair["time_file"]

    cmd = [
        "/usr/bin/time",
        "-v",
        "-o",
        str(time_path),
        py,
        compare_script,
        *extra,
        pair["old_run"],
        pair["new_run"],
    ]

    with result_path.open("w") as out, stderr_path.open("w") as err:
        proc = subprocess.run(cmd, stdout=out, stderr=err)

    if proc.returncode != 0:
        write_status(
            "failed",
            f"Pair {{idx}} failed with exit code {{proc.returncode}}",
            progress,
            current_pair=idx,
            failed_pair=pair,
            exit_code=proc.returncode,
        )
        sys.exit(proc.returncode)

write_status("assembling", "Assembling final compare report", 0.98)
PY

"$PY" - "$JOBDIR" <<'PY'
import json
import re
import sys
import time
from pathlib import Path

jobdir = Path(sys.argv[1])
request = json.loads((jobdir / "compare_request.json").read_text())

def parse_time_log(path):
    out = {{
        "time_log": str(path),
        "max_rss_kb": None,
        "max_rss_gb": None,
        "elapsed_raw": None,
        "user_time_seconds": None,
        "system_time_seconds": None,
        "percent_cpu": None,
    }}
    if not path.exists():
        return out

    text = path.read_text(errors="replace")
    for line in text.splitlines():
        if "Maximum resident set size" in line:
            m = re.search(r":\\s*([0-9]+)", line)
            if m:
                kb = int(m.group(1))
                out["max_rss_kb"] = kb
                out["max_rss_gb"] = kb / 1024 / 1024
        elif "Elapsed (wall clock) time" in line:
            out["elapsed_raw"] = line.split(":", 1)[1].strip()
        elif "User time (seconds)" in line:
            try:
                out["user_time_seconds"] = float(line.split(":", 1)[1].strip())
            except Exception:
                pass
        elif "System time (seconds)" in line:
            try:
                out["system_time_seconds"] = float(line.split(":", 1)[1].strip())
            except Exception:
                pass
        elif "Percent of CPU this job got" in line:
            out["percent_cpu"] = line.split(":", 1)[1].strip()
    return out

def parse_elapsed_seconds(raw):
    # Parse /usr/bin/time -v elapsed strings like M:SS, M:SS.ss, or H:MM:SS.
    text = str(raw or "").strip()
    if not text:
        return None

    parts = text.split(":")
    try:
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(text)
    except Exception:
        return None


def safe_float(value):
    try:
        return float(str(value).strip())
    except Exception:
        return None


def parse_percent_cpu(raw):
    text = str(raw or "").strip()
    if not text:
        return None

    m = re.search(r"([0-9.]+)", text)
    if not m:
        return None

    try:
        return float(m.group(1))
    except Exception:
        return None

def parse_mem_gb(mem_text):
    text = str(mem_text).strip().upper()
    m = re.fullmatch(r"([0-9.]+)\\s*([KMGTP]?B?|)", text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2)
    if unit in ["", "M", "MB"]:
        return value / 1024
    if unit in ["G", "GB"]:
        return value
    if unit in ["T", "TB"]:
        return value * 1024
    if unit in ["K", "KB"]:
        return value / 1024 / 1024
    return None

pairs_out = []
max_rss_gb = 0.0

for pair in request["pairs"]:
    result_path = jobdir / pair["result_file"]
    time_path = jobdir / pair["time_file"]
    stderr_path = jobdir / pair["stderr_file"]

    pair_result = None
    pair_summary = None
    if result_path.exists():
        pair_result = json.loads(result_path.read_text())
        pair_summary = pair_result.get("summary", {{}})

    usage = parse_time_log(time_path)
    if usage.get("max_rss_gb") is not None:
        max_rss_gb = max(max_rss_gb, usage["max_rss_gb"])

    pairs_out.append({{
        "pair_index": pair["pair_index"],
        "label": pair["label"],
        "old_run": pair["old_run"],
        "new_run": pair["new_run"],
        "summary": pair_summary,
        "result_file": pair["result_file"],
        "stderr_file": pair["stderr_file"],
        "time_file": pair["time_file"],
        "usage": usage,
    }})

req_mem_gb = parse_mem_gb(request["slurm"]["mem"])
mem_util_pct = None
if req_mem_gb and req_mem_gb > 0:
    mem_util_pct = 100 * max_rss_gb / req_mem_gb

requested_cpus = int(request["slurm"]["cpus_per_task"])

max_avg_cpu_cores = None
max_cpu_util_pct = None
max_percent_cpu_raw = None

for pair_out in pairs_out:
    usage = pair_out.get("usage") or {{}}

    user_seconds = safe_float(usage.get("user_time_seconds"))
    system_seconds = safe_float(usage.get("system_time_seconds"))
    elapsed_seconds = parse_elapsed_seconds(usage.get("elapsed_raw"))
    percent_cpu_raw = parse_percent_cpu(usage.get("percent_cpu"))

    usage["elapsed_seconds"] = elapsed_seconds
    usage["percent_cpu_numeric"] = percent_cpu_raw

    if (
        user_seconds is not None
        and system_seconds is not None
        and elapsed_seconds is not None
        and elapsed_seconds > 0
    ):
        avg_cpu_cores = (user_seconds + system_seconds) / elapsed_seconds
    elif percent_cpu_raw is not None:
        avg_cpu_cores = percent_cpu_raw / 100.0
    else:
        avg_cpu_cores = None

    usage["average_cpu_cores_used"] = avg_cpu_cores

    if avg_cpu_cores is not None and requested_cpus > 0:
        cpu_util = 100.0 * avg_cpu_cores / requested_cpus
    else:
        cpu_util = None

    usage["cpu_utilization_percent_of_request"] = cpu_util

    if avg_cpu_cores is not None:
        if max_avg_cpu_cores is None or avg_cpu_cores > max_avg_cpu_cores:
            max_avg_cpu_cores = avg_cpu_cores

    if cpu_util is not None:
        if max_cpu_util_pct is None or cpu_util > max_cpu_util_pct:
            max_cpu_util_pct = cpu_util

    if percent_cpu_raw is not None:
        if max_percent_cpu_raw is None or percent_cpu_raw > max_percent_cpu_raw:
            max_percent_cpu_raw = percent_cpu_raw

util_note = {{
    "requested_mem": request["slurm"]["mem"],
    "requested_mem_gb": req_mem_gb,
    "requested_cpus": requested_cpus,
    "max_pair_process_rss_gb": max_rss_gb,
    "approx_mem_utilization_percent": mem_util_pct,
    "max_pair_average_cpu_cores_used": max_avg_cpu_cores,
    "max_pair_cpu_utilization_percent_of_request": max_cpu_util_pct,
    "max_pair_percent_cpu_raw": max_percent_cpu_raw,
    "cpu_summary": (
        None if max_avg_cpu_cores is None
        else f"CPU used: ~{{max_avg_cpu_cores:.2f}} / {{requested_cpus}} requested CPUs average "
             f"({{max_cpu_util_pct:.1f}}% of request)"
    ),
    "note": "MaxRSS and CPU estimates come from /usr/bin/time -v for each Python compare process, not full Slurm job accounting.",
    "cpu_note": "Average CPU cores used is estimated as (user time + system time) / elapsed wall time. For sequential pair comparisons, this reports the maximum pair process average.",
}}

if mem_util_pct is not None:
    if mem_util_pct < 20:
        util_note["recommendation"] = "Requested memory was likely overkill for this comparison level/run set."
    elif mem_util_pct > 85:
        util_note["recommendation"] = "Memory was close to the request. Increase --mem next time."
    else:
        util_note["recommendation"] = "Memory request looks reasonable."

if max_cpu_util_pct is not None:
    if requested_cpus > 1 and max_cpu_util_pct < 50:
        util_note["cpu_recommendation"] = "Requested CPUs were likely more than this comparison used. Consider fewer CPUs unless wall time was too slow."
    elif max_cpu_util_pct > 85:
        util_note["cpu_recommendation"] = "CPU request was well used for at least one pair comparison."
    else:
        util_note["cpu_recommendation"] = "CPU request looks reasonable for this comparison."

final = {{
    "status": "done",
    "created_at": request["created_at"],
    "finished_unix": time.time(),
    "level": request["level"],
    "comparison_mode": request["comparison_mode"],
    "baseline": request["baseline"],
    "runs": request["runs"],
    "slurm": request["slurm"],
    "pairs": pairs_out,
    "utilization_note": util_note,
}}

(jobdir / "compare_result.json").write_text(json.dumps(final, indent=2, sort_keys=True) + "\\n")
(jobdir / "compare_status.json").write_text(json.dumps({{
    "status": "done",
    "message": "Compare job finished",
    "progress": 1.0,
    "total_pairs": len(request["pairs"]),
    "updated_unix": time.time(),
}}, indent=2, sort_keys=True) + "\\n")
PY
"""
    return script


def submit_job(
    level: str,
    run_strings: List[str],
    mem: Optional[str],
    cpus: Optional[int],
    time: Optional[str],
    chunk_mb: Optional[int],
    max_runs: int,
) -> Dict[str, Any]:
    runs = validate_runs(run_strings, max_runs=max_runs)
    rec = recommend_settings(level, len(runs))

    final_mem = mem or rec["recommended_mem"]
    final_cpus = int(cpus or rec["recommended_cpus"])
    final_time = time or rec["recommended_time"]
    final_chunk_mb = int(chunk_mb or rec["chunk_mb"])

    job_dir = make_job_dir(runs, level)

    request_preview = {
        "status": "created",
        "created_at": now_text(),
        "level": level,
        "runs": [str(r) for r in runs],
        "recommendation": rec,
        "selected_slurm": {
            "mem": final_mem,
            "cpus_per_task": final_cpus,
            "time": final_time,
            "chunk_mb": final_chunk_mb,
        },
    }
    write_json(job_dir / "compare_status.json", {
        "status": "created",
        "message": "Compare job created but not submitted yet.",
        "progress": 0,
    })
    write_json(job_dir / "submit_preview.json", request_preview)

    slurm_text = build_slurm_script(
        job_dir=job_dir,
        runs=runs,
        level=level,
        mem=final_mem,
        cpus=final_cpus,
        time=final_time,
        chunk_mb=final_chunk_mb,
    )

    slurm_path = job_dir / "compare_job.sl"
    slurm_path.write_text(slurm_text)
    os.chmod(slurm_path, 0o775)

    # Safety check: sbatch requires shebang at byte 0.
    first_bytes = slurm_path.read_bytes()[:2]
    if first_bytes != b"#!":
        raise RuntimeError(f"Slurm script does not start with shebang: {slurm_path}")

    proc = subprocess.run(
        ["sbatch", str(slurm_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        write_json(job_dir / "compare_status.json", {
            "status": "submit_failed",
            "message": "sbatch failed",
            "progress": 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        })
        raise RuntimeError(f"sbatch failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

    job_id = None
    m = re.search(r"Submitted batch job\s+(\d+)", proc.stdout)
    if m:
        job_id = m.group(1)

    submitted = {
        "status": "submitted",
        "message": "Compare job submitted to Slurm.",
        "progress": 0,
        "job_id": job_id,
        "job_dir": str(job_dir),
        "slurm_script": str(slurm_path),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "level": level,
        "runs": [str(r) for r in runs],
        "slurm": {
            "mem": final_mem,
            "cpus_per_task": final_cpus,
            "time": final_time,
            "chunk_mb": final_chunk_mb,
        },
        "recommendation": rec,
    }
    write_json(job_dir / "compare_status.json", submitted)
    write_json(job_dir / "submit_result.json", submitted)

    return submitted


def get_status(job_dir_string: str) -> Dict[str, Any]:
    job_dir = Path(job_dir_string).expanduser().resolve()

    if not job_dir.exists():
        raise ValueError(f"Compare job folder does not exist: {job_dir}")

    if not str(job_dir).startswith(str(COMPARE_ROOT.resolve())):
        raise ValueError(f"Job folder is outside compare root: {job_dir}")

    status_path = job_dir / "compare_status.json"
    result_path = job_dir / "compare_result.json"

    status = {}
    if status_path.exists():
        status = read_json(status_path)
    else:
        status = {
            "status": "unknown",
            "message": "No compare_status.json found.",
            "progress": 0,
        }

    status["job_dir"] = str(job_dir)
    status["has_result"] = result_path.exists()

    if result_path.exists():
        status["result_path"] = str(result_path)

    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage SFINCS compare jobs.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("recommend", help="Recommend Slurm settings.")
    p_rec.add_argument("--level", required=True, choices=VALID_LEVELS)
    p_rec.add_argument("--runs", nargs="+", required=True)

    p_submit = sub.add_parser("submit", help="Submit a Slurm compare job.")
    p_submit.add_argument("--level", required=True, choices=VALID_LEVELS)
    p_submit.add_argument("--runs", nargs="+", required=True)
    p_submit.add_argument("--mem", default=None)
    p_submit.add_argument("--cpus", type=int, default=None)
    p_submit.add_argument("--time", default=None)
    p_submit.add_argument("--chunk-mb", type=int, default=None)
    p_submit.add_argument("--max-runs", type=int, default=MAX_RUNS_DEFAULT)

    p_status = sub.add_parser("status", help="Read compare job status.")
    p_status.add_argument("--job-dir", required=True)

    args = parser.parse_args()

    try:
        if args.cmd == "recommend":
            runs = validate_runs(args.runs)
            out = recommend_settings(args.level, len(runs))

        elif args.cmd == "submit":
            out = submit_job(
                level=args.level,
                run_strings=args.runs,
                mem=args.mem,
                cpus=args.cpus,
                time=args.time,
                chunk_mb=args.chunk_mb,
                max_runs=args.max_runs,
            )

        elif args.cmd == "status":
            out = get_status(args.job_dir)

        else:
            raise ValueError(f"Unknown command: {args.cmd}")

        print(json.dumps(json_safe(out), indent=2, sort_keys=True))

    except Exception as exc:
        error = {
            "status": "error",
            "message": str(exc),
        }
        print(json.dumps(error, indent=2, sort_keys=True), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()