# Slurm Execution

The Physics-Based Flood Simulation Pipeline uses Slurm to run computationally
expensive work on UNC Longleaf compute nodes.

A normal submitted model run consists of three separate Slurm jobs:

```text
Preprocessing
      |
      | afterok
      v
SFINCS solver
      |
      | afterok
      v
Postprocessing
```

The jobs are connected with Slurm `afterok` dependencies. This means that each
stage begins only after the preceding stage finishes successfully.

The Web Launcher does not run SFINCS directly inside the browser or Flask
process. Instead, it collects the run settings, passes a structured
configuration to the Python backend, and allows the backend to write and submit
the Slurm job stack.

---

## Purpose of the Slurm stack

Separating a model run into three jobs provides several advantages:

- each stage can request appropriate computing resources;
- failures can be traced to a specific stage;
- later stages do not run after an earlier failure;
- logs remain separated by stage;
- the solver can run inside its Apptainer container;
- preprocessing and postprocessing can use the project Python environment;
- the submitted run remains reproducible through its frozen configuration and
  generated job scripts.

The Slurm scripts are execution wrappers. Most scientific and data-processing
logic remains in the Python stage scripts or the SFINCS solver.

---

## Position in the system

The Slurm execution layer sits between the Python pipeline backend and the run
directory.

```text
Web Launcher
      |
      v
Structured run configuration
      |
      v
Python pipeline backend
      |
      +-- validates the configuration
      +-- creates the run directory
      +-- freezes run_config.json
      +-- writes three Slurm scripts
      +-- submits the dependency chain
      |
      v
UNC Longleaf Slurm scheduler
      |
      +-- preprocessing job
      +-- SFINCS solver job
      +-- postprocessing job
      |
      v
Run directory, logs, model outputs, and postprocess products
```

The main backend files involved are:

```text
pipeline_runner.py
    Coordinates the requested workflow.

workflow_planner.py
    Determines which stages are required.

slurm_writer.py
    Writes the Slurm job scripts.

slurm_submit.py
    Submits the scripts and records their job IDs.

preprocess_stage.py
    Builds or updates the SFINCS model inputs.

postprocess_stage.py
    Reads completed SFINCS outputs and creates derived products.
```

Detailed implementation notes for these files belong in the
[Python backend documentation](python_backend/backend.md) and the
[Python backend module catalog](python_backend/module_catalog.md).

---

## Execution modes

The backend supports different levels of execution.

### Preflight only

```text
preflight_only
```

This mode validates the configuration and important paths without creating or
submitting the full job stack.

It is used by launcher previews and checks. Seeing
`pipeline_mode = preflight_only` in a preview does not mean that a later Submit
action will also be preflight-only.

### Build scripts only

```text
build_scripts_only
```

This mode:

```text
validates the configuration
creates the run directory
writes the frozen run_config.json
writes the three Slurm scripts
does not submit them
```

This is useful for reviewing the exact scripts before allowing them to run.

### Submit Slurm chain

```text
submit_slurm_chain
```

This mode:

```text
validates the configuration
creates the run directory
writes the frozen run_config.json
writes the three Slurm scripts
submits all three jobs with dependencies
records the resulting Slurm job IDs
```

This is the normal full-run execution mode used by the launcher Submit action.

---

## Run-directory layout

A submitted run generally contains the following structure:

```text
<run_name>/
├── run_config.json
├── job_ids.txt
├── scripts/
│   ├── preprocess_job.sl
│   ├── sfincs_job.sl
│   └── postprocess_job.sl
├── logs/
│   ├── preprocess_<job_id>.out
│   ├── preprocess_<job_id>.err
│   ├── sfincs_<job_id>.out
│   ├── sfincs_<job_id>.err
│   ├── postprocess_<job_id>.out
│   └── postprocess_<job_id>.err
├── model/
│   ├── sfincs.inp
│   ├── sfincs.log
│   ├── sfincs_map.nc
│   ├── sfincs_his.nc
│   └── other generated SFINCS inputs and outputs
├── postprocess/
│   └── derived outputs and summaries
└── review/
    ├── maps/
    ├── animations/
    ├── obs_gauges/
    └── jobs/
```

The exact contents vary by preprocessing mode, enabled forcing, requested
outputs, and Review products.

The current shared production-style run root is: (though of course this can always be changed in the settings tab)

```text
/proj/zefflab/projects/Flooding/sfincs_runs
```


The run-local `run_config.json` is the frozen record of the configuration used
to build and submit that run. It should be inspected instead of assuming that a
run used the current launcher defaults.

---

## Script generation and submission

`slurm_writer.py` writes the three scripts but does not submit them. Keeping
script generation separate from submission allows the pipeline to support the
build-scripts-only workflow.

The scripts are then submitted by `slurm_submit.py` in a sequence equivalent to:

```bash
preprocess_id=$(sbatch --parsable scripts/preprocess_job.sl)

sfincs_id=$(sbatch --parsable \
  --dependency=afterok:${preprocess_id} \
  scripts/sfincs_job.sl)

postprocess_id=$(sbatch --parsable \
  --dependency=afterok:${sfincs_id} \
  scripts/postprocess_job.sl)
```

This shell example illustrates the dependency structure. The production
pipeline performs the submission through Python rather than requiring the user
to enter these commands manually.

The submitted relationship is:

```text
preprocess job ID
        |
        | afterok:<preprocess job ID>
        v
SFINCS job ID
        |
        | afterok:<SFINCS job ID>
        v
postprocess job ID
```

The IDs are recorded so that the jobs can later be located with `squeue`,
`scontrol`, or accounting tools.

---

## Meaning of `afterok`

An `afterok` dependency requires the earlier job to finish with a successful
exit status.

Therefore:

```text
If preprocessing succeeds:
    the SFINCS job becomes eligible to run.

If preprocessing fails:
    the SFINCS job does not run.

If SFINCS succeeds:
    the postprocess job becomes eligible to run.

If SFINCS fails:
    the postprocess job does not run.
```

The chain does not pause for manual inspection between stages. The SFINCS solver
may begin as soon as preprocessing succeeds and scheduler resources are
available.

A read-only audit performed immediately after preprocessing may therefore
overlap with a pending or running solver job. Audits should not alter, suspend,
or delete an active run.

---

## Common script safety behavior

All three generated scripts begin with:

```bash
#!/bin/bash
```

The shebang must be the first line of the file. A blank line before it can
prevent Slurm from interpreting the script correctly.

The scripts also use:

```bash
set -euo pipefail
```

This provides three important safeguards:

```text
-e
    Stop when a command returns a nonzero exit status.

-u
    Treat the use of an unset variable as an error.

-o pipefail
    Treat a failure inside a command pipeline as a pipeline failure.
```

The scripts use `test` commands as stage gates. For example:

```bash
test -f '/path/to/model/sfincs.inp'
```

If the required file does not exist, `test` returns a failure status and the job
stops instead of reporting false success.

---

# Stage 1: Preprocessing job

## Purpose

The preprocessing job converts the frozen run configuration and selected
catalog inputs into a SFINCS-ready model folder.

Depending on the selected preprocessing mode, it may:

```text
build a model through HydroMT-SFINCS
copy trusted native SFINCS inputs
combine trusted static inputs with event forcing
write generated rainfall or boundary forcing
write observation points and cross sections
write sfincs.inp and associated model files
```

The preprocessing job runs through:

```text
/proj/zefflab/projects/Flooding/pipeline/code/preprocess_stage.py
```

using the configured Python executable:

```text
/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python
```

## Representative resource request

The following resources were used for the Harvey
`harvey_2017_mrms_manual_035` preprocessing job:

| Resource | Requested value |
|---|---:|
| Nodes | 1 |
| Tasks | 1 |
| CPUs per task | 8 |
| Memory | 48 GB |
| Time limit | 2 hours |

These values are a real working example, not a universal requirement for every
event or preprocessing mode.

## Representative preprocessing script

```bash
#!/bin/bash
#SBATCH --job-name=pre_harvey_2017_mrms_manual_035
#SBATCH --output=/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/logs/preprocess_%j.out
#SBATCH --error=/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/logs/preprocess_%j.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G

set -euo pipefail

PYTHON='/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python'
CONFIG='/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/run_config.json'
RUN_ROOT='/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035'

test -x "${PYTHON}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export GDAL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"

"${PYTHON}" \
  '/proj/zefflab/projects/Flooding/pipeline/code/preprocess_stage.py' \
  "${CONFIG}"

test -d "${RUN_ROOT}/model"
test -f "${RUN_ROOT}/model/sfincs.inp"
```

The actual generated script also prints timestamps, hostname information,
selected paths, Python version, and thread settings into its standard-output
log. Failure logs/ error codes are printed into the output by the `preprocess_stage.py` script.

## Required success evidence

The current preprocessing wrapper explicitly requires:

```text
<run>/model/
<run>/model/sfincs.inp
```

Their presence proves that the minimum script checks passed. It does not by
itself prove that every generated scientific input is correct.

Generated boundary files, masks, rainfall forcing, observation points, cross
sections, and atmospheric settings still require their own audits.

---

# Stage 2: SFINCS solver job

## Purpose

The solver job runs the SFINCS executable inside an Apptainer container.

The current production container is:

```text
/proj/zefflab/projects/Flooding/pipeline/containers/
sfincs-v2.3.0-mt-Faber-Release.sif
```

The solver job does not rebuild the model. It enters the generated `model`
folder, binds that folder into the container as `/data`, and runs the SFINCS
container against the existing model inputs.

## Representative resource request

The Harvey `manual_035` solver used:

| Resource | Requested value |
|---|---:|
| Nodes | 1 |
| Tasks | 1 |
| CPUs per task | 24 |
| Memory | 32 GB |
| Time limit | 6 hours |

The SFINCS container is multithreaded, so the script assigns
`SLURM_CPUS_PER_TASK` to `OMP_NUM_THREADS`.

## Representative solver script

```bash
#!/bin/bash
#SBATCH --job-name=sf_harvey_2017_mrms_manual_035
#SBATCH --output=/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/logs/sfincs_%j.out
#SBATCH --error=/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/logs/sfincs_%j.err
#SBATCH --time=06:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G

set -euo pipefail

MODEL_ROOT='/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/model'
CONTAINER='/proj/zefflab/projects/Flooding/pipeline/containers/sfincs-v2.3.0-mt-Faber-Release.sif'

module purge
module load apptainer

test -d "${MODEL_ROOT}"
test -f "${MODEL_ROOT}/sfincs.inp"
test -f "${CONTAINER}"

cd "${MODEL_ROOT}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-24}"
export OMP_PROC_BIND=true
export OMP_PLACES=cores

apptainer run -B "$(pwd):/data" "${CONTAINER}"

test -f "${MODEL_ROOT}/sfincs.log"
test -f "${MODEL_ROOT}/sfincs_map.nc"
```

## Container binding

This line:

```bash
apptainer run -B "$(pwd):/data" "${CONTAINER}"
```

binds the current model directory to `/data` inside the container.

Conceptually:

```text
Longleaf host:
    <run>/model

Container:
    /data
```

The containerized SFINCS executable reads and writes files through this mounted
directory, so the resulting outputs remain in the run folder after the
container exits.

## OpenMP settings

The solver script uses:

```bash
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-24}"
export OMP_PROC_BIND=true
export OMP_PLACES=cores
```

These settings tell the OpenMP solver how many threads to use and encourage
those threads to remain bound to allocated CPU cores.

Requesting many CPUs does not automatically prove that they are used
efficiently. Resource tuning should be based on measured runtime and utilization
rather than increasing CPU counts without evidence.

## Required success evidence

The current wrapper requires:

```text
<run>/model/sfincs.log
<run>/model/sfincs_map.nc
```

A normal run may also produce:

```text
<run>/model/sfincs_his.nc
```

and other requested outputs.

A Slurm-completed solver job means the wrapper exited successfully. Scientific
checks are still needed to confirm that the outputs contain expected variables,
time coverage, forcing response, observation dimensions, and physically
reasonable values.

---

# Stage 3: Postprocessing job

## Purpose

The postprocessing job reads completed SFINCS outputs and creates derived
products, summaries, and quality-control materials.

It runs:

```text
/proj/zefflab/projects/Flooding/pipeline/code/postprocess_stage.py
```

through the project SFINCS Python environment.

Postprocessing is separate from Review Mode. The postprocess stage creates
standard pipeline products. Review Mode may later create additional maps,
animations, observation comparisons, or other requested products.

## Representative resource request

The Harvey `manual_035` postprocess job used:

| Resource | Requested value |
|---|---:|
| Nodes | 1 |
| Tasks | 1 |
| CPUs per task | 4 |
| Memory | 24 GB |
| Time limit | 1 hour |

## Representative postprocessing script

```bash
#!/bin/bash
#SBATCH --job-name=post_harvey_2017_mrms_manual_035
#SBATCH --output=/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/logs/postprocess_%j.out
#SBATCH --error=/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/logs/postprocess_%j.err
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G

set -euo pipefail

PYTHON='/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python'
CONFIG='/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035/run_config.json'
RUN_ROOT='/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_035'

test -x "${PYTHON}"
test -f "${RUN_ROOT}/model/sfincs_map.nc"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export GDAL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

"${PYTHON}" \
  '/proj/zefflab/projects/Flooding/pipeline/code/postprocess_stage.py' \
  "${CONFIG}"

test -d "${RUN_ROOT}/postprocess"
```

## Required success evidence

The current wrapper requires:

```text
<run>/model/sfincs_map.nc
<run>/postprocess/
```

The existence of the postprocess folder is only the minimum wrapper check.
Individual expected products should also be checked for stable, nonzero files
and error-free logs.

---

## Why the stages request different resources

The three jobs perform different kinds of work.

### Preprocessing

Preprocessing commonly performs:

```text
Python processing
GeoPandas and raster operations
HydroMT-SFINCS model construction
NetCDF and GeoTIFF access
catalog and forcing assembly
```

It may require substantial memory even when it does not use many CPU cores.

### SFINCS solver

The solver performs the main physics-based numerical simulation. It generally
benefits most directly from multiple CPU cores through OpenMP.

### Postprocessing

Postprocessing reads model output and creates summaries or derived products. It
usually requires fewer CPUs than the solver but may still require meaningful
memory for NetCDF and raster operations.

Resource requests are configuration values and should be treated as adjustable
inputs rather than permanent constants.

---

## Logs

Each stage writes separate standard-output and standard-error logs.

The `%j` token is replaced by the Slurm job ID:

```text
logs/preprocess_<job_id>.out
logs/preprocess_<job_id>.err

logs/sfincs_<job_id>.out
logs/sfincs_<job_id>.err

logs/postprocess_<job_id>.out
logs/postprocess_<job_id>.err
```

The `.out` files normally include:

```text
job start and end timestamps
compute-node hostname
working directory
selected paths
software versions
thread settings
stage progress messages
successful completion message
```

The `.err` files contain standard error. An empty `.err` file is useful but is
not sufficient evidence of a valid scientific result.

When diagnosing a failed run, inspect the first failed stage rather than only
the final dependent job.

---

## Monitoring jobs

A user's active Slurm jobs can be viewed with:

```bash
squeue -u <onyen>
```

A more informative format is:

```bash
squeue -u <onyen> -o "%.18i %.32j %.10T %.12M %.24R"
```

A specific job can be inspected with:

```bash
scontrol show job <job_id>
```

Useful fields include:

```text
JobId
JobName
JobState
Reason
WorkDir
Command
Dependency
ExitCode
RunTime
NumCPUs
MinMemoryNode
```

After a job leaves `squeue`, scheduler accounting may be inspected with:

```bash
sacct -j <job_id> --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,MaxRSS
```

A job disappearing from `squeue` does not automatically mean it succeeded.
Check its accounting state, logs, and expected outputs.

---

## Common scheduler states

```text
PENDING
    The job is waiting for resources or a dependency.

RUNNING
    The job is currently executing.

COMPLETED
    Slurm reports a successful scheduler-level completion.

FAILED
    The job exited unsuccessfully.

CANCELLED
    The job was cancelled.

TIMEOUT
    The job exceeded its requested time limit.

OUT_OF_MEMORY
    The job exceeded its memory allocation.
```

A dependent job may remain pending while its prerequisite is active. If the
prerequisite fails, the dependent job cannot satisfy an `afterok` dependency
and will not execute normally.

---

## Failure interpretation

### Preprocessing failure

Likely evidence:

```text
preprocess job FAILED
no valid model/sfincs.inp
SFINCS job never starts
postprocess job never starts
```

Check:

```text
preprocess error log
preprocess output log
run_config.json
source paths
Python environment
HydroMT-SFINCS traceback
partially generated model folder
```

### Solver failure

Likely evidence:

```text
preprocessing completed
sfincs job FAILED, TIMEOUT, or OUT_OF_MEMORY
postprocess job never starts
```

Check:

```text
SFINCS standard-output and error logs
model/sfincs.log
sfincs.inp
container path
Apptainer module loading
thread and memory settings
partial NetCDF outputs
```

### Postprocessing failure

Likely evidence:

```text
preprocessing completed
SFINCS completed
postprocess job FAILED
raw SFINCS output remains available
Review may label the run as sfincs-completed rather than fully completed
```

Check:

```text
postprocess output and error logs
postprocess traceback
sfincs_map.nc readability
sfincs_his.nc readability
expected postprocess folder and products
```

A postprocessing failure does not necessarily require rerunning the expensive
SFINCS solver. A future or explicitly supported postprocess-only workflow may
reuse valid existing solver output.

---

## Completion is not scientific validation

Several completion layers must remain separate:

```text
Slurm completion
    The scheduler says a job exited successfully.

Stage-wrapper completion
    The shell script passed its minimum `test` checks.

Pipeline completion
    Preprocessing, solver, and postprocessing completion evidence exists.

Review status
    Review Mode recognizes expected run products.

Scientific validation
    Inputs and outputs have been audited and model results have been compared
    against appropriate observations.
```

For example, the presence of `sfincs_map.nc` does not by itself prove:

```text
the boundary stations are correct
the boundary order is correct
rainfall forcing was applied
wind and pressure settings are correct
observation points and cross sections are correct
the NetCDF contents are complete
the model agrees with observed flooding
```

The project should never use `completed` as a synonym for scientifically
validated.

---

## Current validation expectations

For current Harris County runs, post-run audits may include:

```text
exact generated BND station order and coordinates
matching BZS column order
boundary cells on msk=2
59 universal observation points
29 universal cross-section lines
correct tropical-cyclone wind and pressure settings
correct baro value
readable sfincs_map.nc
readable sfincs_his.nc
expected station and cross-section dimensions
fresh postprocess products
comparison against event observations
```

These checks belong primarily in the validation documentation rather than in
the Slurm scripts themselves.

---

## Safety and reproducibility rules

### Do not submit duplicate run names unintentionally

A run name should identify a unique model build. Submitting a second job stack
against the same active directory can cause files and logs to overlap.

### Do not delete active run directories

Before moving or deleting a run directory, check:

```bash
squeue -u <onyen>
```

Job names alone may be abbreviated. Use `scontrol show job` and inspect `WorkDir`
or `Command` when necessary.

### Keep generated scripts with the run

The three generated Slurm scripts document how the run was executed and should
remain in the run folder with the frozen configuration and logs.

### Use configured absolute executable paths

The Python stage jobs call the configured Python executable directly instead of
depending on an interactive-shell conda activation.

The solver explicitly loads Apptainer and uses the configured container path.

### Avoid heavy work on login nodes

The login node may be used to:

```text
prepare configurations
submit jobs
inspect small text files
check status
review logs
perform lightweight filesystem checks
```

Large model builds, numerical simulations, NetCDF processing, and map rendering
should run through Slurm or an appropriate interactive compute session.

---

## Current implementation status

The three-stage Slurm stack is active and has been used for the current Harris
County event-run family.

The current architecture supports:

```text
preflight without submission
script generation without submission
full dependent three-job submission
separate stage logs
run-local configuration and scripts
Python preprocessing
containerized SFINCS execution
Python postprocessing
```

The current three-job stack is the normal full-run workflow, but the workflow
planner should remain flexible enough to support future operations such as:

```text
postprocess-only reruns
existing-output validation
validation-output reruns
batch submission
additional Review-product jobs
```

These workflows should reuse the same run-directory and provenance principles
without forcing every action through a complete preprocessing–solver–
postprocessing rerun.

---

## Related documentation

- [System architecture](overview.md)
- [Python backend](python_backend/backend.md)
- [Python backend module catalog](python_backend/module_catalog.md)
- [Web Launcher architecture](web_launcher/web_launcher.md)
- [Review Mode architecture](review_mode/review_mode.md)
- [Review product and status model](review_mode/product_and_status_model.md)