# Usage

This repository documents the SFINCS flood-modeling pipeline, its architecture, current research use, data organization, and Web Launcher.

The repository can be cloned or pulled to inspect the source code and documentation. However, the recommended way to obtain a working Longleaf installation is currently through a **Globus transfer** of the established pipeline, environments, and supporting files.

The transfer process has not yet been tested as a public installation workflow. Contact the project maintainer before attempting it:

**Reichen Schaller**
**[epsilon@unc.edu](mailto:epsilon@unc.edu)**

## Launching the Web Launcher

After the pipeline has been transferred and configured on Longleaf, open an Open OnDemand desktop session and launch the Web Launcher with:

```bash
/proj/zefflab/projects/Flooding/pipeline/web_launcher/launch_web_launcher.sh
```

Assign at least **16 GB of memory** to the Longleaf browser session. A larger session may be appropriate for reliable use; for example:

```text
--mem=64G --ntasks=1 --cpus-per-task=4
```

Note, you must launch the weblauncher from the console inside the browser session and not through another shell as the nodes are likely different and you won't be able to connect to it.

The launch script prints the local Web Launcher address. Open that address in the browser running inside the Longleaf desktop session.

For operating instructions, configuration explanations, and workflow guidance, open the **Guide** page from the Web Launcher.


