"""
Author: Reichen Schaller
Slurm script writing and submission helpers for the SFINCS pipeline runner.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from runner_core import print_section, run_paths, shell_quote


def _cfg(cfg: dict[str, Any], key: str, default: Any = None) -> Any:
    return cfg.get(key, default)


def python_thread_env_lines(cpus_per_task: int) -> str:
    return f"""\
echo "Configuring Python numeric/geospatial thread limits..."
export OMP_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export OPENBLAS_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export MKL_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export NUMEXPR_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
export GDAL_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus_per_task}}}"
echo "OMP_NUM_THREADS=${{OMP_NUM_THREADS}}"
echo "OPENBLAS_NUM_THREADS=${{OPENBLAS_NUM_THREADS}}"
echo "MKL_NUM_THREADS=${{MKL_NUM_THREADS}}"
echo "NUMEXPR_NUM_THREADS=${{NUMEXPR_NUM_THREADS}}"
echo "GDAL_NUM_THREADS=${{GDAL_NUM_THREADS}}"
"""


def sbatch_header(
    cfg: dict[str, Any],
    job_name: str,
    log_name: str,
    time_limit: str,
    nodes: int,
    ntasks: int,
    cpus_per_task: int,
    mem: str,
) -> str:
    paths = run_paths(cfg)
    logs_root = paths["logs_root"]

    lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --output={logs_root / log_name}",
        f"#SBATCH --error={logs_root / log_name.replace('.out', '.err')}",
        f"#SBATCH --time={time_limit}",
        f"#SBATCH --nodes={nodes}",
        f"#SBATCH --ntasks={ntasks}",
        f"#SBATCH --cpus-per-task={cpus_per_task}",
        f"#SBATCH --mem={mem}",
    ]

    if _cfg(cfg, "slurm_partition"):
        lines.append(f"#SBATCH --partition={_cfg(cfg, 'slurm_partition')}")
    if _cfg(cfg, "slurm_account"):
        lines.append(f"#SBATCH --account={_cfg(cfg, 'slurm_account')}")
    if _cfg(cfg, "slurm_qos"):
        lines.append(f"#SBATCH --qos={_cfg(cfg, 'slurm_qos')}")
    if _cfg(cfg, "slurm_email"):
        lines.append(f"#SBATCH --mail-user={_cfg(cfg, 'slurm_email')}")
        lines.append(f"#SBATCH --mail-type={_cfg(cfg, 'slurm_mail_type', 'END,FAIL')}")

    for extra in _cfg(cfg, "slurm_extra_directives", []) or []:
        lines.append(str(extra))

    lines.append("")

    if bool(_cfg(cfg, "bash_strict_mode", True)):
        lines.append("set -euo pipefail")
        lines.append("")

    return "\n".join(lines)


def write_preprocess_slurm(cfg: dict[str, Any]) -> Path:
    paths = run_paths(cfg)
    body = f"""\
{sbatch_header(
    cfg=cfg,
    job_name=f"pre_{cfg['run_name']}",
    log_name="preprocess_%j.out",
    time_limit=str(_cfg(cfg, "preprocess_time")),
    nodes=int(_cfg(cfg, "preprocess_nodes")),
    ntasks=int(_cfg(cfg, "preprocess_ntasks")),
    cpus_per_task=int(_cfg(cfg, "preprocess_cpus_per_task")),
    mem=str(_cfg(cfg, "preprocess_mem")),
)}
echo "========== PREPROCESS JOB START =========="
date
hostname
pwd

echo "Run root: {paths['run_root']}"
echo "Config:   {paths['config_json_path']}"

echo "Using configured Python executable:"
test -x {shell_quote(cfg['conda_python'])}
{shell_quote(cfg['conda_python'])} --version

{python_thread_env_lines(int(_cfg(cfg, "preprocess_cpus_per_task")))}

echo "Running preprocess_stage.py..."
{shell_quote(cfg['conda_python'])} {shell_quote(cfg['preprocess_stage_script'])} {shell_quote(paths['config_json_path'])}

echo "Checking preprocessing outputs..."
test -d {shell_quote(paths['model_root'])}
test -f {shell_quote(paths['model_root'] / 'sfincs.inp')}

echo "Preprocessing completed successfully."
date
echo "========== PREPROCESS JOB END =========="
"""
    out = paths["preprocess_slurm_path"]
    out.write_text(body, encoding="utf-8")
    out.chmod(0o755)
    print(f"Wrote preprocess Slurm script: {out}")
    return out


def write_sfincs_slurm(cfg: dict[str, Any]) -> Path:
    paths = run_paths(cfg)

    if bool(_cfg(cfg, "sfincs_use_openmp_threads", True)):
        omp_lines = f"""\
echo "Configuring OpenMP threading..."
export OMP_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{int(_cfg(cfg, "sfincs_cpus_per_task"))}}}"
export OMP_PROC_BIND="{_cfg(cfg, "sfincs_omp_proc_bind", "true")}"
export OMP_PLACES="{_cfg(cfg, "sfincs_omp_places", "cores")}"
echo "OMP_NUM_THREADS=${{OMP_NUM_THREADS}}"
echo "OMP_PROC_BIND=${{OMP_PROC_BIND}}"
echo "OMP_PLACES=${{OMP_PLACES}}"
"""
    else:
        omp_lines = """\
echo "OpenMP threading disabled by config."
export OMP_NUM_THREADS=1
"""

    body = f"""\
{sbatch_header(
    cfg=cfg,
    job_name=f"sf_{cfg['run_name']}",
    log_name="sfincs_%j.out",
    time_limit=str(_cfg(cfg, "sfincs_time")),
    nodes=int(_cfg(cfg, "sfincs_nodes")),
    ntasks=int(_cfg(cfg, "sfincs_ntasks")),
    cpus_per_task=int(_cfg(cfg, "sfincs_cpus_per_task")),
    mem=str(_cfg(cfg, "sfincs_mem")),
)}
echo "========== SFINCS JOB START =========="
date
hostname
pwd

echo "Model root: {paths['model_root']}"
echo "Container:  {cfg['sfincs_container_path']}"

echo "Loading Apptainer..."
module purge
module load {_cfg(cfg, "apptainer_module", "apptainer")}
apptainer --version

echo "Checking model input..."
test -d {shell_quote(paths['model_root'])}
test -f {shell_quote(paths['model_root'] / 'sfincs.inp')}

cd {shell_quote(paths['model_root'])}

{omp_lines}
echo "Running SFINCS container..."
apptainer run -B "$(pwd):/data" {shell_quote(cfg['sfincs_container_path'])}

echo "Checking SFINCS outputs..."
test -f {shell_quote(paths['model_root'] / 'sfincs.log')}
test -f {shell_quote(paths['model_root'] / 'sfincs_map.nc')}

echo "SFINCS completed successfully."
date
echo "========== SFINCS JOB END =========="
"""
    out = paths["sfincs_slurm_path"]
    out.write_text(body, encoding="utf-8")
    out.chmod(0o755)
    print(f"Wrote SFINCS Slurm script: {out}")
    return out


def write_postprocess_slurm(cfg: dict[str, Any]) -> Path:
    paths = run_paths(cfg)
    body = f"""\
{sbatch_header(
    cfg=cfg,
    job_name=f"post_{cfg['run_name']}",
    log_name="postprocess_%j.out",
    time_limit=str(_cfg(cfg, "postprocess_time")),
    nodes=int(_cfg(cfg, "postprocess_nodes")),
    ntasks=int(_cfg(cfg, "postprocess_ntasks")),
    cpus_per_task=int(_cfg(cfg, "postprocess_cpus_per_task")),
    mem=str(_cfg(cfg, "postprocess_mem")),
)}
echo "========== POSTPROCESS JOB START =========="
date
hostname
pwd

echo "Run root: {paths['run_root']}"
echo "Config:   {paths['config_json_path']}"

echo "Using configured Python executable:"
test -x {shell_quote(cfg['conda_python'])}
{shell_quote(cfg['conda_python'])} --version

echo "Checking raw SFINCS output..."
test -f {shell_quote(paths['model_root'] / 'sfincs_map.nc')}

{python_thread_env_lines(int(_cfg(cfg, "postprocess_cpus_per_task")))}

echo "Running postprocess_stage.py..."
{shell_quote(cfg['conda_python'])} {shell_quote(cfg['postprocess_stage_script'])} {shell_quote(paths['config_json_path'])}

echo "Checking postprocess folder..."
test -d {shell_quote(paths['postprocess_root'])}

echo "Postprocessing completed successfully."
date
echo "========== POSTPROCESS JOB END =========="
"""
    out = paths["postprocess_slurm_path"]
    out.write_text(body, encoding="utf-8")
    out.chmod(0o755)
    print(f"Wrote postprocess Slurm script: {out}")
    return out


def write_slurm_scripts(cfg: dict[str, Any]) -> dict[str, Path | None]:
    print_section("WRITE SLURM SCRIPTS")

    written: dict[str, Path | None] = {
        "preprocess": None,
        "sfincs": None,
        "postprocess": None,
    }

    if bool(_cfg(cfg, "run_preprocessing_job", False)):
        written["preprocess"] = write_preprocess_slurm(cfg)
    if bool(_cfg(cfg, "run_sfincs_job", False)):
        written["sfincs"] = write_sfincs_slurm(cfg)
    if bool(_cfg(cfg, "run_postprocessing_job", False)):
        written["postprocess"] = write_postprocess_slurm(cfg)

    return written


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    print("Running command:", " ".join(command))
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_sbatch_job_id(stdout: str) -> str:
    text = stdout.strip()
    if not text:
        raise ValueError("sbatch returned empty stdout; cannot parse job ID")
    return text.split(";")[0]


def submit_sbatch(script_path: Path, dependency_job_id: str | None = None, dependency_type: str = "afterok") -> str:
    command = ["sbatch", "--parsable"]
    if dependency_job_id:
        command.append(f"--dependency={dependency_type}:{dependency_job_id}")
    command.append(str(script_path))

    result = run_command(command)
    if result.stderr.strip():
        print("sbatch stderr:")
        print(result.stderr.strip())

    job_id = parse_sbatch_job_id(result.stdout)
    print(f"Submitted {script_path.name}: job ID {job_id}")
    return job_id


def submit_slurm_chain(cfg: dict[str, Any]) -> dict[str, str | None]:
    print_section("SUBMIT SLURM CHAIN")

    paths = run_paths(cfg)
    job_ids: dict[str, str | None] = {
        "preprocess": None,
        "sfincs": None,
        "postprocess": None,
    }

    previous_job_id: str | None = None

    if bool(_cfg(cfg, "run_preprocessing_job", False)):
        job_ids["preprocess"] = submit_sbatch(paths["preprocess_slurm_path"])
        previous_job_id = job_ids["preprocess"]

    if bool(_cfg(cfg, "run_sfincs_job", False)):
        dep = previous_job_id if bool(_cfg(cfg, "submit_with_dependencies", True)) else None
        job_ids["sfincs"] = submit_sbatch(
            paths["sfincs_slurm_path"],
            dependency_job_id=dep,
            dependency_type=str(_cfg(cfg, "dependency_type", "afterok")),
        )
        previous_job_id = job_ids["sfincs"]

    if bool(_cfg(cfg, "run_postprocessing_job", False)):
        dep = previous_job_id if bool(_cfg(cfg, "submit_with_dependencies", True)) else None
        job_ids["postprocess"] = submit_sbatch(
            paths["postprocess_slurm_path"],
            dependency_job_id=dep,
            dependency_type=str(_cfg(cfg, "dependency_type", "afterok")),
        )

    return job_ids


def write_job_ids(cfg: dict[str, Any], job_ids: dict[str, str | None]) -> Path | None:
    if not bool(_cfg(cfg, "save_job_ids", True)):
        return None

    paths = run_paths(cfg)
    lines = [
        f"run_name={cfg['run_name']}",
        f"run_root={paths['run_root']}",
        f"submitted_at={datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    for stage, job_id in job_ids.items():
        lines.append(f"{stage}={job_id}")

    out = paths["job_ids_path"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote job IDs: {out}")
    return out