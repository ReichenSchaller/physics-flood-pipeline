# SFINCS Container

The pipeline runs the SFINCS solver through an **Apptainer `.sif` container** on UNC Longleaf. The container keeps the compiled SFINCS executable and its runtime dependencies separate from the Python environments used to construct models and process results.

The container image itself is not included in this repository because it is a large binary file. Researchers working on Longleaf should obtain the established container through a **Globus transfer** or contact the project maintainer:

**Reichen Schaller**
**[epsilon@unc.edu](mailto:epsilon@unc.edu)**

## Available solver versions

Two SFINCS container versions are currently maintained by the project.

| Version       | Release name | Project status                                                                      |
| ------------- | ------------ | ----------------------------------------------------------------------------------- |
| SFINCS v2.3.0 | Faber        | Primary and most thoroughly tested pipeline baseline                                |
| SFINCS v2.4.0 | Galibier     | Successfully executed with the pipeline, but not yet tested as extensively as Faber |

The current production/default container is:

```text
/proj/zefflab/projects/Flooding/pipeline/containers/sfincs-v2.3.0-mt-Faber-Release.sif
```

The newer side-by-side container is:

```text
/proj/zefflab/projects/Flooding/pipeline/containers/sfincs-v2.4.0-Galibier-Release.sif
```

Both versions have successfully executed project models. However, most pipeline development, historical-event runs, postprocessing checks, and validation work have been performed with **SFINCS v2.3.0 Faber**. Faber should therefore be treated as the current reproducibility baseline.

SFINCS v2.4.0 Galibier may be selected for testing, but results should not automatically be assumed to be numerically or structurally identical to v2.3.0. Solver releases can change numerical behavior, supported inputs, diagnostics, and NetCDF output variables.

## Container creation

Deltares distributes SFINCS through tagged Docker images. Longleaf executes containers with Apptainer rather than Docker, so the official release image was converted into a portable `.sif` file.

The general process was:

```text
official tagged Deltares Docker image
    ↓
Apptainer pulls and converts the image
    ↓
versioned .sif file stored in the project container directory
    ↓
pipeline passes that container path to each SFINCS Slurm job
```

On Longleaf, Apptainer may first need to be loaded:

```bash
module load apptainer
```

A tagged release can then be converted using the general pattern:

```bash
apptainer pull <output-container-name>.sif docker://<official-image-tag>
```

For example, the Galibier release image can be converted with:

```bash
apptainer pull \
  sfincs-v2.4.0-Galibier-Release.sif \
  docker://deltares/sfincs-cpu:sfincs-v2.4.0-Galibier-Release
```

The Faber container was produced through the same general Docker-to-Apptainer process using its corresponding tagged Deltares release image.

The project intentionally uses **versioned release tags** rather than a moving `latest` tag. This prevents a future upstream update from silently changing the solver used by an existing workflow.

## Relationship to the Python environments

The SFINCS container and the Python environments have different responsibilities:

```text
Python / HydroMT-SFINCS environment
    builds and checks native SFINCS model inputs

SFINCS Apptainer container
    runs the hydraulic simulation

Python postprocessing environment
    reads the resulting SFINCS outputs
```

Changing the SFINCS container does not automatically update HydroMT, HydroMT-SFINCS, or the pipeline’s Python packages. Solver-container upgrades and Python-environment upgrades should be tested separately so differences can be attributed to the correct component.

## Selecting a container

The Web Launcher stores the selected container path in the run configuration. The pipeline then freezes that path into the run and uses the selected `.sif` during the SFINCS Slurm stage.

For established production and reproducibility work, use:

```text
SFINCS v2.3.0 Faber
```

Use Galibier for deliberate version testing or after confirming that the relevant model inputs, solver logs, outputs, and postprocessing behavior have been checked against the Faber baseline.

## Reproducibility note

Every run should preserve the exact SFINCS container path or version in its configuration and logs. Old native model inputs are not guaranteed to behave identically across solver versions, even when both containers successfully complete the simulation.

The container version should therefore be treated as part of the scientific run configuration rather than as an interchangeable deployment detail.
