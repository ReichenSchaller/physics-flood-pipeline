# Python Environments

## Overview

The pipeline uses three Conda environments and one Python virtual environment rather than combining every dependency into a single software stack. This separation keeps the browser server lightweight, isolates specialized data-acquisition and mapping packages, and reduces the chance that a change needed by one workflow will break the HydroMT-SFINCS model-building environment. (That and it keeps breaking when I try to merge all 4.)

The installed environments are not stored in this repository. Instead, the repository records readable environment definitions and exact package specifications needed to understand or recreate the working setup.

The current Longleaf environments are:

| Environment | Primary responsibility | Required for normal use? |
|---|---|---|
| `sfincs` | HydroMT-SFINCS model construction, preprocessing, pipeline execution, Slurm preparation, output inspection, and general postprocessing | Yes |
| `sfincs_contextily` | Specialized map generation that requires Contextily or related web-basemap packages | Only for mapping workflows that call it |
| `web_launcher` | Flask server, browser-facing APIs, safe path browsing, and handoff to pipeline helpers | Yes when using the Web Launcher |
| `aorc_s3` | Downloading and preparing AORC precipitation and atmospheric products from cloud/S3 storage | No when the required event products are already prepared |

The SFINCS hydraulic solver is not installed inside these environments. It is executed separately through the versioned Apptainer container described in [SFINCS Container](../docs/sfincs_container.md).

---

## Repository files

```text
environments/
├── environments.md
├── sfincs_environment.yml
├── sfincs_contextily_environment.yml
├── aorc_s3_environment.yml
├── web_launcher_requirements.txt
└── exact/
    ├── sfincs_explicit_linux-64.txt
    ├── sfincs_contextily_explicit_linux-64.txt
    └── aorc_s3_explicit_linux-64.txt
```

These files preserve two forms of Conda environment information and one pip-based Web Launcher specification.

### Readable Conda YAML files

The following files contain readable definitions of the three Conda-managed environments:

```text
sfincs_environment.yml
sfincs_contextily_environment.yml
aorc_s3_environment.yml
```

The exports omit package build strings and the original machine-specific installation prefix. They are the primary readable recreation files for the Conda environments.

They are easier to inspect and adapt than exact package lists, but Conda must solve the dependency graph again when creating an environment. A future solver result may therefore differ from the original Longleaf installation even when the listed package versions are unchanged.

### Exact Linux specifications

Files such as:

```text
exact/sfincs_explicit_linux-64.txt
```

record the exact Conda package builds and package URLs installed in the current environment. They provide the strongest Conda-side reproduction record for the same Linux platform.

These files are specific to Longleaf and compatible Linux systems. They should not be treated as portable specifications for Windows, macOS, another processor architecture, or an unrelated operating-system environment.

### Web Launcher requirements

The Web Launcher is not managed as a Conda environment. It is a standard Python virtual environment recorded by:

```text
web_launcher_requirements.txt
```

This file contains the pip packages and versions installed in the current Web Launcher environment.

The requirements also include Spyder and Jupyter-kernel support packages used during development. The file should therefore be understood as a reproducible snapshot of the working environment rather than a minimal Flask-only dependency list.

---

## Environment responsibilities

### `sfincs`

The `sfincs` environment is the primary scientific Python environment for the project.

It supports:

- HydroMT and HydroMT-SFINCS model construction;
- loading static and event data catalogs;
- configuration validation;
- Manual and Override preprocessing;
- generation and inspection of native SFINCS input files;
- Slurm script preparation and job orchestration;
- inspection of `sfincs_his.nc` and `sfincs_map.nc`;
- validation and comparison utilities;
- general postprocessing; and
- most backend maintenance and audit scripts.

This is the most dependency-sensitive environment. HydroMT, HydroMT-SFINCS, GDAL-related libraries, Rasterio, GeoPandas, PyProj, Shapely, Xarray, NetCDF libraries, NumPy, and related packages must remain mutually compatible.

The current installed environment is located at:

```text
/proj/zefflab/projects/Flooding/pipeline/envs/sfincs
```

Activate it interactively with:

```bash
conda activate /proj/zefflab/projects/Flooding/pipeline/envs/sfincs
```

For Slurm jobs and automated scripts, the pipeline generally uses the environment's Python executable directly:

```bash
/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python
```

Using the explicit executable avoids relying on an interactive shell activation inside every job.

---

### `sfincs_contextily`

The `sfincs_contextily` environment isolates mapping dependencies used by products that require Contextily or related web-basemap packages.

It exists because web-tile and mapping packages can place additional constraints on the geospatial stack. Keeping that work separate reduces the need to alter the primary `sfincs` environment solely for visualization features.

The environment is used only by scripts that explicitly call it. It is not a replacement for the primary model-building environment.

Current location:

```text
/proj/zefflab/projects/Flooding/pipeline/envs/sfincs_contextily
```

Interactive activation:

```bash
conda activate /proj/zefflab/projects/Flooding/pipeline/envs/sfincs_contextily
```

This environment is not the normal Spyder development environment. The project currently launches Spyder with the primary `sfincs` environment.

---

### `web_launcher`

The `web_launcher` environment is a Python virtual environment created with `venv`. It runs the local Flask application used by the browser-facing Web Launcher.

Its responsibilities include:

- serving the launcher HTML, JavaScript, images, and other static assets;
- handling launcher API requests;
- reading the deployment defaults;
- performing safe filesystem browsing;
- staging submitted JSON configurations;
- reporting run and Review status; and
- launching the appropriate backend Python helper.

The environment is intentionally narrower than the primary scientific environment. Flask does not need to contain the full HydroMT-SFINCS dependency stack when the launcher can hand scientific work to the correct external interpreter.

Current location:

```text
/proj/zefflab/projects/Flooding/pipeline/envs/web_launcher
```

It can be activated manually with:

```bash
source /proj/zefflab/projects/Flooding/pipeline/envs/web_launcher/bin/activate
```

Normal users should start the environment through:

```bash
/proj/zefflab/projects/Flooding/pipeline/web_launcher/launch_web_launcher.sh
```

The launch script activates the virtual environment and starts the local Flask server with the established project settings.

---

### `aorc_s3`

The `aorc_s3` environment supports acquisition and preparation of AORC data from cloud or S3 storage.

Its specialized dependencies include cloud-storage clients, filesystem adapters, and scientific libraries required by the AORC download and conversion workflow. Those dependencies are not required merely to run an event whose AORC products have already been downloaded and promoted into the data catalogs.

Current location:

```text
/proj/zefflab/projects/Flooding/pipeline/envs/aorc_s3
```

Interactive activation:

```bash
conda activate /proj/zefflab/projects/Flooding/pipeline/envs/aorc_s3
```

This environment is primarily part of data preparation rather than the normal Web Launcher run path.

---

## Recreating a Conda environment from YAML

A readable YAML can be used to create a new environment at a chosen path:

```bash
conda env create \
  --prefix /path/to/new/sfincs \
  --file environments/sfincs_environment.yml
```

After creation, activate it with:

```bash
conda activate /path/to/new/sfincs
```

This method asks Conda to solve the dependencies using the package versions and channels in the YAML. It is the preferred first attempt when installing the project on a compatible system.

The resulting environment must still be tested. Successful installation does not prove that HydroMT-SFINCS builds the same files or that all pipeline and postprocessing functions behave identically.

---

## Recreating the exact Longleaf Conda environment

For the closest same-platform reconstruction, use the explicit Linux specification:

```bash
conda create \
  --prefix /path/to/new/sfincs \
  --file environments/exact/sfincs_explicit_linux-64.txt
```

This avoids a new dependency solve and requests the exact Conda package builds recorded by the working environment.

The explicit files are specific to the current Linux platform and may depend on package URLs or builds that later become unavailable. They are intended as exact Longleaf reproduction records rather than portable cross-platform installation files.

Only the three Conda environments have explicit Linux specifications. The Web Launcher is recreated from `web_launcher_requirements.txt`.

---

## Recreating the Web Launcher virtual environment

Create a new Python virtual environment:

```bash
python3 -m venv /path/to/new/web_launcher
```

Activate it:

```bash
source /path/to/new/web_launcher/bin/activate
```

Upgrade pip and install the recorded packages:

```bash
python -m pip install --upgrade pip

python -m pip install \
  -r environments/web_launcher_requirements.txt
```

Confirm the principal imports:

```bash
python -c "import flask, werkzeug, jinja2; print('Web Launcher imports passed')"
```

The requirements file records the full working environment, including development and kernel-support packages. A smaller runtime-only requirements file may be created later after the launcher has been tested without those additional packages.

---

## Exporting and checking the current environments

The repository includes a read-only script that regenerates the public environment specifications and validates the principal imports in all four installed environments.

The exporter is located at:

```text
/proj/zefflab/projects/Flooding/Github/physics-flood-pipeline/audits/export_and_validate_environment_specs_v2.py
```

Run it in Spyder with:

```python
%runfile '/proj/zefflab/projects/Flooding/Github/physics-flood-pipeline/audits/export_and_validate_environment_specs_v2.py' --wdir '/proj/zefflab/projects/Flooding/Github/physics-flood-pipeline/audits'
```

The script:

- exports readable YAML files for the three Conda environments;
- exports exact Linux specifications for those environments;
- exports `web_launcher_requirements.txt` from the Python virtual environment;
- removes machine-specific Conda `prefix:` lines;
- checks the principal imports for each environment;
- distinguishes normal conda-forge build metadata from genuine project-local dependencies; and
- creates temporary audit reports for review.

The latest export completed successfully:

```text
sfincs             12/12 configured imports passed
sfincs_contextily   6/6 configured imports passed
aorc_s3             3/3 configured imports passed
web_launcher        3/3 configured imports passed
```

Temporary reports, manifests, raw package inventories, and package-origin records are local audit products. They may be reviewed after an export but are not retained in the public repository.

---

## Updating an environment safely

Do not update a production environment in place merely because a newer package version is available.

Use the following process:

```text
working production environment
    ↓
clone or recreate a separate test environment
    ↓
make the proposed dependency change
    ↓
confirm imports and package versions
    ↓
load the current data catalogs
    ↓
build or update a representative model
    ↓
run a known canary simulation
    ↓
compare generated inputs, outputs, and Review products
    ↓
promote only after compatibility is confirmed
```

A minimum HydroMT-SFINCS environment test should confirm:

- `hydromt` imports successfully;
- `hydromt_sfincs` imports successfully;
- the current static and event catalogs load;
- the configuration schema validates a known run;
- Manual preprocessing can generate native SFINCS inputs;
- Override preprocessing can import the trusted native static package;
- the expected observation points and lines are present;
- the selected SFINCS container completes a canary run;
- `sfincs_his.nc` and `sfincs_map.nc` can be opened;
- maps, animations, and validation products can be regenerated; and
- the results are compared with the established production baseline.

Solver-container changes and Python-environment changes should be tested separately whenever possible. Otherwise, a difference in results may be difficult to attribute to the correct component.

---

## Reproducibility boundary

The environment files preserve the Python dependency state, but they are only one part of a reproducible run.

A complete reproduction also depends on:

```text
pipeline source revision
launcher source revision
selected data catalogs
run configuration
SFINCS container version
Longleaf and Slurm resources
model inputs
postprocessing settings
```

Each run should preserve its own configuration and solver-container selection. The environment export files document the software stack used to create and inspect those runs.
