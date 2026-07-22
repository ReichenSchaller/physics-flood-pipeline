#!/usr/bin/env python3
"""Submit the obs/gauge Review product builder to Slurm, with a direct fallback."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PRODUCT_REL = Path("review") / "obs_gauges"
STATUS_NAME = "obs_gauges_status.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    parser.add_argument("--validation-csv", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-match-distance-m", type=float, default=250.0)
    parser.add_argument("--wl-bad-m", type=float, default=1.0)
    parser.add_argument("--flow-bad-cms", type=float, default=1000.0)
    parser.add_argument("--direct", action="store_true", help="Run builder directly instead of sbatch.")
    args = parser.parse_args()

    run_root = Path(args.run_root).expanduser().resolve()
    out_dir = run_root / PRODUCT_REL
    job_dir = run_root / "review" / "jobs"
    out_dir.mkdir(parents=True, exist_ok=True)
    job_dir.mkdir(parents=True, exist_ok=True)

    status_path = out_dir / STATUS_NAME
    script = Path("/proj/zefflab/projects/Flooding/pipeline/code/review_prepare_obs_gauges.py")
    py = Path(os.environ.get("SFINCS_REVIEW_PYTHON", "/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python"))

    cmd = [str(py), str(script), str(run_root), "--force", "--max-match-distance-m", str(args.max_match_distance_m), "--wl-bad-m", str(args.wl_bad_m), "--flow-bad-cms", str(args.flow_bad_cms)]
    if args.validation_csv:
        cmd += ["--validation-csv", args.validation_csv]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slurm_path = job_dir / f"review_obs_gauges_{stamp}.slurm"
    out_path = job_dir / f"review_obs_gauges_{stamp}.out"
    err_path = job_dir / f"review_obs_gauges_{stamp}.err"

    slurm_text = f"""#!/bin/bash
#SBATCH --job-name=review_obs_gauges
#SBATCH --output={out_path}
#SBATCH --error={err_path}
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G

set -euo pipefail
module purge || true
module load anaconda || true

{' '.join(shlex_quote(x) for x in cmd)}
"""
    slurm_path.write_text(slurm_text, encoding="utf-8")

    if args.direct or shutil.which("sbatch") is None:
        state = "running_direct" if args.direct else "sbatch_unavailable"
        write_json(status_path, {
            "state": state,
            "message": "Running obs/gauge builder directly." if args.direct else "sbatch unavailable; run the written Slurm file manually or use --direct.",
            "updated_at": now_iso(),
            "slurm_script": str(slurm_path.resolve().relative_to(run_root)),
        })
        if args.direct:
            proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            out_path.write_text(proc.stdout, encoding="utf-8")
            err_path.write_text(proc.stderr, encoding="utf-8")
            print(json.dumps({"ok": proc.returncode == 0, "returncode": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}))
            return proc.returncode
        print(json.dumps({"ok": True, "status": json.loads(status_path.read_text()), "slurm_script": str(slurm_path)}))
        return 0

    write_json(status_path, {
        "state": "submitting",
        "message": "Submitting obs/gauge validation job to Slurm.",
        "updated_at": now_iso(),
        "slurm_script": str(slurm_path.resolve().relative_to(run_root)),
    })

    proc = subprocess.run(["sbatch", str(slurm_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        write_json(status_path, {
            "state": "submit_failed",
            "message": "Could not submit obs/gauge validation job.",
            "updated_at": now_iso(),
            "error": proc.stderr.strip() or proc.stdout.strip(),
            "slurm_script": str(slurm_path.resolve().relative_to(run_root)),
        })
        print(json.dumps({"ok": False, "error": proc.stderr.strip() or proc.stdout.strip()}))
        return proc.returncode

    job_id = proc.stdout.strip().split()[-1] if proc.stdout.strip().split() else ""
    status = {
        "state": "submitted",
        "message": "Obs/gauge validation job submitted to Slurm.",
        "updated_at": now_iso(),
        "job_id": job_id,
        "sbatch_stdout": proc.stdout.strip(),
        "slurm_script": str(slurm_path.resolve().relative_to(run_root)),
        "stdout_relpath": str(out_path.resolve().relative_to(run_root)),
        "stderr_relpath": str(err_path.resolve().relative_to(run_root)),
    }
    write_json(status_path, status)
    print(json.dumps({"ok": True, "status": status}, indent=2))
    return 0


def shlex_quote(text: str) -> str:
    import shlex
    return shlex.quote(str(text))


if __name__ == "__main__":
    raise SystemExit(main())
