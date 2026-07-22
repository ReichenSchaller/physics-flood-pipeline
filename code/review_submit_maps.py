#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 17 16:15:16 2026

@author: epsilon
"""

from pathlib import Path
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys


DEFAULT_RUN = Path("/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_020")
PIPE = Path("/proj/zefflab/projects/Flooding/pipeline")
PY = PIPE / "envs" / "sfincs_contextily" / "bin" / "python"
SCRIPT = PIPE / "code" / "review_prepare_maps.py"


def now_stamp():
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def quote_bash(text):
    return "'" + str(text).replace("'", "'\"'\"'") + "'"


def parse_job_id(stdout):
    m = re.search(r"Submitted batch job\s+(\d+)", stdout or "")
    if m:
        return m.group(1)
    return None


def make_sbatch(run_root, force=False):
    run_root = Path(run_root).resolve()
    cfg = read_json(run_root / "run_config.json")

    review_dir = run_root / "review"
    jobs_dir = review_dir / "jobs"
    logs_dir = review_dir / "logs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    stamp = now_stamp()
    sbatch_path = jobs_dir / f"review_maps_{stamp}.sbatch"
    out_log = logs_dir / f"review_maps_{stamp}.out"
    err_log = logs_dir / f"review_maps_{stamp}.err"

    time = cfg.get("review_maps_time") or "01:00:00"
    mem = cfg.get("review_maps_mem") or cfg.get("postprocess_mem") or "24G"
    cpus = cfg.get("review_maps_cpus_per_task") or cfg.get("postprocess_cpus_per_task") or 4
    ntasks = 1

    slurm_account = cfg.get("slurm_account")
    slurm_partition = cfg.get("slurm_partition")
    slurm_qos = cfg.get("slurm_qos")
    mail_type = cfg.get("slurm_mail_type")
    email = cfg.get("slurm_email")

    lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name=review_maps_{run_root.name[:28]}",
        f"#SBATCH --output={out_log}",
        f"#SBATCH --error={err_log}",
        f"#SBATCH --time={time}",
        f"#SBATCH --nodes=1",
        f"#SBATCH --ntasks={ntasks}",
        f"#SBATCH --cpus-per-task={cpus}",
        f"#SBATCH --mem={mem}",
    ]

    if slurm_account:
        lines.append(f"#SBATCH --account={slurm_account}")
    if slurm_partition:
        lines.append(f"#SBATCH --partition={slurm_partition}")
    if slurm_qos:
        lines.append(f"#SBATCH --qos={slurm_qos}")
    if mail_type:
        lines.append(f"#SBATCH --mail-type={mail_type}")
    if email:
        lines.append(f"#SBATCH --mail-user={email}")

    command = [
        "set -euo pipefail",
        "echo '================================================================================'",
        "echo 'REVIEW MAP CACHE JOB'",
        "echo '================================================================================'",
        "date",
        "hostname",
        f"echo RUN={quote_bash(run_root)}",
        f"echo PY={quote_bash(PY)}",
        f"echo SCRIPT={quote_bash(SCRIPT)}",
        "export MPLBACKEND=Agg",
        "export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-1}",
        "",
        f"{quote_bash(PY)} {quote_bash(SCRIPT)} {quote_bash(run_root)} {'--force' if force else ''} --pretty",
        "",
        "echo '================================================================================'",
        "echo 'DONE REVIEW MAP CACHE JOB'",
        "echo '================================================================================'",
        "date",
    ]

    sbatch_path.write_text("\n".join(lines + [""] + command) + "\n", encoding="utf-8")

    return sbatch_path, out_log, err_log


def submit_maps(run_root, force=False):
    run_root = Path(run_root).resolve()
    status_path = run_root / "review" / "maps" / "map_status.json"

    if not (run_root / "model" / "sfincs_map.nc").exists():
        raise FileNotFoundError(f"Run does not have model/sfincs_map.nc: {run_root}")

    sbatch_path, out_log, err_log = make_sbatch(run_root, force=force)

    if shutil.which("sbatch") is None:
        write_json(status_path, {
            "state": "sbatch_unavailable",
            "updated_at": dt.datetime.now().replace(microsecond=0).isoformat(),
            "message": "sbatch command was not found. The sbatch file was written but not submitted.",
            "sbatch_path": str(sbatch_path),
            "stdout_log": str(out_log),
            "stderr_log": str(err_log),
        })
        print("SBATCH NOT FOUND")
        print(sbatch_path)
        return None

    result = subprocess.run(
        ["sbatch", str(sbatch_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        write_json(status_path, {
            "state": "submit_failed",
            "updated_at": dt.datetime.now().replace(microsecond=0).isoformat(),
            "sbatch_path": str(sbatch_path),
            "stdout": result.stdout,
            "stderr": result.stderr,
        })
        raise RuntimeError(f"sbatch failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    job_id = parse_job_id(result.stdout)

    write_json(status_path, {
        "state": "submitted",
        "updated_at": dt.datetime.now().replace(microsecond=0).isoformat(),
        "job_id": job_id,
        "sbatch_path": str(sbatch_path),
        "stdout_log": str(out_log),
        "stderr_log": str(err_log),
        "message": result.stdout.strip(),
    })

    print(result.stdout.strip())
    print(f"job_id={job_id}")
    print(f"status={status_path}")
    print(f"sbatch={sbatch_path}")
    print(f"stdout_log={out_log}")
    print(f"stderr_log={err_log}")

    return job_id


def main():
    parser = argparse.ArgumentParser(description="Submit Review map cache builder to Slurm.")
    parser.add_argument("run_root", nargs="?", default=str(DEFAULT_RUN))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    submit_maps(Path(args.run_root), force=args.force)


if __name__ == "__main__":
    main()