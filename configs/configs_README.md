# Example Run Configurations

This directory contains two example Web Launcher run configurations representing the pipeline's two primary model-construction workflows.

```text
configs/
└── examples/
    ├── harvey_manual_example_config.json
    └── beryl_override_example_config.json
```

## Harvey Manual example

`harvey_manual_example.json` is based on a successful Manual Mode run for Hurricane Harvey.

Manual Mode constructs the model from source-oriented static and event data catalogs. It demonstrates the full model-building workflow, including the generation of native SFINCS inputs from the configured datasets.

This example is useful for understanding:

- Manual Mode configuration structure;
- static and event catalog selection;
- model geometry settings;
- precipitation and boundary forcing;
- observation points and lines;
- Slurm and SFINCS settings; and
- the paths required for a complete source-based build.

## Beryl Override example

`beryl_override_example.json` is based on a successful Override Mode run for Hurricane Beryl.

Override Mode begins from a trusted set of existing native SFINCS static files and replaces or updates only selected model components. This avoids repeating expensive static preprocessing when the established geometry and static inputs remain appropriate.

This example is useful for understanding:

- Override Mode configuration structure;
- trusted native static-file reuse;
- event-specific forcing replacement;
- output and run-directory settings;
- Slurm and SFINCS settings; and
- the difference between Manual and Override workflows.

## Deployment-specific paths

The examples preserve the structure of real working configurations, but many paths refer to the current UNC Longleaf deployment.

Data paths may point beneath:

```text
/users/e/p/epsilon/Data/Data/harris_county
```

Pipeline, run, environment, and container paths may also refer to locations beneath:

```text
/proj/zefflab/projects/Flooding
```

These paths will not work unchanged on another system.

Before submitting either example, review and replace paths associated with:

- the pipeline root;
- static and event data catalogs;
- trusted Override inputs;
- the run-output root;
- Python environments;
- the SFINCS Apptainer container; and
- any deployment-specific temporary or staging directories.

The Web Launcher's Settings page defines the default deployment paths and allowed filesystem roots. After adapting those settings, the example configurations can be loaded into the appropriate launcher mode and modified for another event or installation.

## Using the examples

The examples are intended as working references rather than universal templates. They show the configuration fields and path relationships used by successful Harris County runs, but they do not include the large model datasets, SFINCS container, or installed Python environments.

Users should review each configuration in the Web Launcher before submission rather than treating it as immediately portable.

For field-level explanations and launcher instructions, see the Web Launcher Guide.
