#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 18 14:20:08 2026

@author: epsilon
"""


from pathlib import Path
import argparse
import datetime as dt
import json
import re
import subprocess


PIPE = Path("/proj/zefflab/projects/Flooding/pipeline")
PY = PIPE / "envs" / "sfincs" / "bin" / "python"
BUILDER = PIPE / "code" / "review_prepare_animation.py"
RUNS = Path("/proj/zefflab/projects/Flooding/sfincs_runs")


def now_iso():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def clean_rel(path, run_root):
    return str(Path(path).resolve().relative_to(run_root.resolve()))


def safe_run_root(raw):
    p = Path(raw).resolve()
    runs = RUNS.resolve()
    if p != runs and runs not in p.parents:
        raise ValueError(f"Run path is outside allowed runs root: {p}")
    if not p.exists():
        raise FileNotFoundError(f"Run root does not exist: {p}")
    return p


def animation_status_path(run_root):
    return run_root / "review" / "animations" / "animation_status.json"


def set_status(run_root, state, **extra):
    payload = {
        "state": state,
        "updated_at": now_iso(),
        **extra,
    }
    write_json(animation_status_path(run_root), payload)


def safe_job_name(run_name):
    txt = re.sub(r"[^A-Za-z0-9_]+", "_", run_name)
    return ("review_anim_" + txt)[:64]


def main():
    parser = argparse.ArgumentParser(description="Submit Review animation builder as a Slurm job.")
    parser.add_argument("run_root")
    parser.add_argument("--hours-per-frame", type=float, required=True)
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run_root = safe_run_root(args.run_root)
    hpf = float(args.hours_per_frame)
    fps = float(args.fps)

    if hpf <= 0:
        raise ValueError("hours_per_frame must be > 0")
    if fps <= 0:
        raise ValueError("fps must be > 0")

    anim_dir = run_root / "review" / "animations"
    job_dir = run_root / "review" / "jobs"
    anim_dir.mkdir(parents=True, exist_ok=True)
    job_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    sbatch_path = job_dir / f"review_animation_{stamp}.sbatch"
    stdout_path = job_dir / f"review_animation_{stamp}.out"
    stderr_path = job_dir / f"review_animation_{stamp}.err"

    force_arg = " --force" if args.force else ""

    sbatch_text = f"""#!/bin/bash
#SBATCH --job-name={safe_job_name(run_root.name)}
#SBATCH --output={stdout_path}
#SBATCH --error={stderr_path}
#SBATCH --time=02:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=4

set -euo pipefail

export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4
export NUMEXPR_NUM_THREADS=4
export PYTHONUNBUFFERED=1
export PATH=/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin:$PATH

cd {PIPE}

{PY} {BUILDER} {run_root} --hours-per-frame {hpf} --fps {fps}{force_arg} --pretty
"""

    sbatch_path.write_text(sbatch_text, encoding="utf-8")

    set_status(
        run_root,
        "submitting",
        message="Submitting Review animation job to Slurm.",
        hours_per_frame=hpf,
        fps=fps,
        sbatch_relpath=clean_rel(sbatch_path, run_root),
    )

    proc = subprocess.run(
        ["sbatch", "--parsable", str(sbatch_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        set_status(
            run_root,
            "failed",
            message="sbatch failed while submitting Review animation job.",
            error=proc.stderr.strip() or proc.stdout.strip(),
            sbatch_relpath=clean_rel(sbatch_path, run_root),
        )
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

    job_id = proc.stdout.strip().split(";")[0].strip()

    status = {
        "state": "submitted",
        "updated_at": now_iso(),
        "message": "Review animation job submitted to Slurm.",
        "job_id": job_id,
        "hours_per_frame": hpf,
        "fps": fps,
        "sbatch_relpath": clean_rel(sbatch_path, run_root),
        "stdout_relpath": clean_rel(stdout_path, run_root),
        "stderr_relpath": clean_rel(stderr_path, run_root),
    }
    write_json(animation_status_path(run_root), status)

    print(json.dumps({
        "ok": True,
        "run": run_root.name,
        "status": status,
    }, indent=2))


if __name__ == "__main__":
    main()