from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ======================================================================================
# EXPORT AND VALIDATE THE PROJECT PYTHON ENVIRONMENTS
# ======================================================================================
#
# Installed environments:
#   sfincs             Conda
#   sfincs_contextily  Conda
#   aorc_s3            Conda
#   web_launcher       Python venv / pip
#
# This script DOES NOT modify the installed environments.
# It writes reproducibility records into the GitHub working repository.
# ======================================================================================

PIPELINE_ROOT = Path("/proj/zefflab/projects/Flooding/pipeline")
REPO_ROOT = Path(
    "/proj/zefflab/projects/Flooding/Github/physics-flood-pipeline"
)
ENV_ROOT = PIPELINE_ROOT / "envs"
OUT_ROOT = REPO_ROOT / "environments"
EXACT_ROOT = OUT_ROOT / "exact"

ENVIRONMENTS: dict[str, dict[str, Any]] = {
    "sfincs": {
        "manager": "conda",
        "path": ENV_ROOT / "sfincs",
        "imports": {
            "hydromt": "hydromt",
            "hydromt_sfincs": "hydromt-sfincs",
            "numpy": "numpy",
            "pandas": "pandas",
            "scipy": "scipy",
            "xarray": "xarray",
            "geopandas": "geopandas",
            "rasterio": "rasterio",
            "rioxarray": "rioxarray",
            "pyproj": "pyproj",
            "shapely": "shapely",
            "netCDF4": "netCDF4",
        },
    },
    "sfincs_contextily": {
        "manager": "conda",
        "path": ENV_ROOT / "sfincs_contextily",
        "imports": {
            "contextily": "contextily",
            "matplotlib": "matplotlib",
            "geopandas": "geopandas",
            "rasterio": "rasterio",
            "pyproj": "pyproj",
            "shapely": "shapely",
        },
    },
    "aorc_s3": {
        "manager": "conda",
        "path": ENV_ROOT / "aorc_s3",
        "imports": {
            "fsspec": "fsspec",
            "s3fs": "s3fs",
            "xarray": "xarray",
        },
    },
    "web_launcher": {
        "manager": "venv",
        "path": ENV_ROOT / "web_launcher",
        "imports": {
            "flask": "Flask",
            "werkzeug": "Werkzeug",
            "jinja2": "Jinja2",
        },
    },
}

KEY_PACKAGES = [
    "python",
    "hydromt",
    "hydromt-sfincs",
    "numpy",
    "pandas",
    "scipy",
    "xarray",
    "geopandas",
    "rasterio",
    "rioxarray",
    "netcdf4",
    "h5netcdf",
    "pyproj",
    "shapely",
    "contextily",
    "matplotlib",
    "flask",
    "werkzeug",
    "jinja2",
    "psutil",
    "fsspec",
    "s3fs",
    "boto3",
    "zarr",
]

# These are normal conda-forge build origins, not dependencies on the user's files.
CONDA_BUILD_ORIGINS = (
    "file:///home/conda/feedstock_root/",
    "file:///opt/conda/conda-bld/",
    "file:///tmp/",
)

# These are genuinely machine-specific origins that should be reviewed.
PROJECT_LOCAL_ORIGINS = (
    "file:///proj/",
    "file:///users/",
    "file:///work/",
    "file:///nas/",
    "file:///home/epsilon/",
)

SECRET_PATTERNS = [
    re.compile(r"https?://[^/\s:@]+:[^/\s@]+@", re.I),
    re.compile(
        r"(?i)(?:token|access_token|password|passwd|secret|api_key)"
        r"\s*[=:]\s*[^&\s,'\"]+"
    ),
]


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value.strip().lower())


def run(command: list[str], timeout: int = 900) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env={**os.environ, "PYTHONNOUSERSITE": "1"},
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stderr.strip()}"
        )

    return completed.stdout


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def find_conda() -> Path:
    candidates = [
        os.environ.get("CONDA_EXE"),
        shutil.which("conda"),
        "/nas/longleaf/rhel9/apps/anaconda/2024.02/bin/conda",
        str(Path.home() / "miniforge3/bin/conda"),
        str(Path.home() / "miniconda3/bin/conda"),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        path = Path(candidate).expanduser()

        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()

    raise FileNotFoundError("Could not find a usable Conda executable.")


def clean_yaml(text: str, name: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    lines: list[str] = []
    wrote_name = False

    for line in text.splitlines():
        if line.startswith("prefix:"):
            warnings.append("Removed machine-specific prefix line.")
            continue

        if line.startswith("name:") and not wrote_name:
            lines.append(f"name: {name}")
            wrote_name = True
        else:
            lines.append(line.rstrip())

    if not wrote_name:
        lines.insert(0, f"name: {name}")

    cleaned = "\n".join(lines).rstrip() + "\n"

    if any(value in cleaned for value in PROJECT_LOCAL_ORIGINS):
        warnings.append("Portable YAML contains a project-local file origin.")

    return cleaned, warnings


def environment_size(path: Path) -> str:
    try:
        return run(["du", "-sh", str(path)], timeout=1200).split()[0]
    except Exception:
        return "unknown"


def pip_list(python_exe: Path) -> list[dict[str, str]]:
    return json.loads(
        run(
            [
                str(python_exe),
                "-m",
                "pip",
                "list",
                "--format=json",
            ]
        )
    )


def import_checks(
    python_exe: Path,
    imports: dict[str, str],
) -> dict[str, dict[str, Any]]:
    code = r'''
import importlib
import importlib.metadata
import json
import sys

requested = json.loads(sys.argv[1])
results = {}

for module_name, distribution_name in requested.items():
    record = {
        "ok": False,
        "distribution": distribution_name,
        "version": "",
        "module_file": "",
        "error": "",
    }

    try:
        module = importlib.import_module(module_name)
        record["ok"] = True
        record["module_file"] = str(getattr(module, "__file__", "") or "")

        try:
            record["version"] = importlib.metadata.version(distribution_name)
        except Exception:
            record["version"] = str(getattr(module, "__version__", "") or "")

    except Exception as error:
        record["error"] = f"{type(error).__name__}: {error}"

    results[module_name] = record

print(json.dumps(results))
'''

    return json.loads(
        run(
            [
                str(python_exe),
                "-c",
                code,
                json.dumps(imports),
            ],
            timeout=300,
        )
    )


def classify_freeze_origins(text: str) -> dict[str, list[str]]:
    result = {
        "conda_build_origins": [],
        "project_local_origins": [],
        "other_file_origins": [],
    }

    for line in text.splitlines():
        stripped = line.strip()

        if "file://" not in stripped and not stripped.startswith("-e "):
            continue

        if any(value in stripped for value in CONDA_BUILD_ORIGINS):
            result["conda_build_origins"].append(stripped)
        elif any(value in stripped for value in PROJECT_LOCAL_ORIGINS):
            result["project_local_origins"].append(stripped)
        else:
            result["other_file_origins"].append(stripped)

    return result


def pip_only_packages(conda_records: list[dict[str, Any]]) -> list[str]:
    packages: list[tuple[str, str]] = []

    for record in conda_records:
        channel = normalize_name(str(record.get("channel", "")))
        build = normalize_name(
            str(record.get("build_string", record.get("build", "")))
        )

        if channel == "pypi" or build == "pypi-0":
            name = str(record.get("name", "")).strip()
            version = str(record.get("version", "")).strip()

            if name and version:
                packages.append((name, version))

    return [
        f"{name}=={version}"
        for name, version in sorted(
            set(packages),
            key=lambda value: normalize_name(value[0]),
        )
    ]


def version_map(
    python_text: str,
    conda_records: list[dict[str, Any]],
    pip_records: list[dict[str, str]],
) -> dict[str, str]:
    installed = {
        normalize_name(record["name"]): str(record["version"])
        for record in pip_records
    }

    for record in conda_records:
        installed[normalize_name(str(record.get("name", "")))] = str(
            record.get("version", "")
        )

    result = {
        name: installed.get(normalize_name(name), "")
        for name in KEY_PACKAGES
    }

    match = re.search(r"Python\s+([0-9.]+)", python_text)
    result["python"] = match.group(1) if match else python_text
    return result


def export_conda(
    conda: Path,
    name: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    env_path = Path(config["path"])
    python_exe = env_path / "bin/python"

    result: dict[str, Any] = {
        "name": name,
        "manager": "conda",
        "path": str(env_path),
        "status": "failed",
        "warnings": [],
        "errors": [],
    }

    try:
        if not (env_path / "conda-meta" / "history").is_file():
            raise RuntimeError("Missing conda-meta/history.")

        if not python_exe.is_file():
            raise RuntimeError(f"Missing Python executable: {python_exe}")

        result["python"] = run([str(python_exe), "--version"]).strip()
        result["size"] = environment_size(env_path)

        conda_records = json.loads(
            run(
                [
                    str(conda),
                    "list",
                    "--prefix",
                    str(env_path),
                    "--json",
                ]
            )
        )
        pip_records = pip_list(python_exe)
        raw_freeze = run(
            [str(python_exe), "-m", "pip", "freeze", "--all"]
        )

        result["package_count"] = len(conda_records)
        result["versions"] = version_map(
            result["python"],
            conda_records,
            pip_records,
        )
        result["imports"] = import_checks(python_exe, config["imports"])
        result["freeze_origins"] = classify_freeze_origins(raw_freeze)

        portable_yaml, warnings = clean_yaml(
            run(
                [
                    str(conda),
                    "env",
                    "export",
                    "--prefix",
                    str(env_path),
                    "--no-builds",
                ]
            ),
            name,
        )
        result["warnings"].extend(warnings)
        write_text(OUT_ROOT / f"{name}_environment.yml", portable_yaml)

        requested_yaml, warnings = clean_yaml(
            run(
                [
                    str(conda),
                    "env",
                    "export",
                    "--prefix",
                    str(env_path),
                    "--from-history",
                ]
            ),
            name,
        )
        result["warnings"].extend(warnings)
        write_text(
            EXACT_ROOT / f"{name}_requested_packages.yml",
            requested_yaml,
        )

        write_text(
            EXACT_ROOT / f"{name}_explicit_linux-64.txt",
            run(
                [
                    str(conda),
                    "list",
                    "--prefix",
                    str(env_path),
                    "--explicit",
                ]
            ),
        )

        write_json(EXACT_ROOT / f"{name}_conda_list.json", conda_records)
        write_json(EXACT_ROOT / f"{name}_pip_list.json", pip_records)
        write_text(EXACT_ROOT / f"{name}_pip_freeze_raw.txt", raw_freeze)
        write_json(
            EXACT_ROOT / f"{name}_pip_origin_classification.json",
            result["freeze_origins"],
        )

        pip_only = pip_only_packages(conda_records)
        result["pip_only_count"] = len(pip_only)
        write_text(
            EXACT_ROOT / f"{name}_pip_only_requirements.txt",
            "\n".join(pip_only)
            if pip_only
            else "# No pip-only packages identified by Conda metadata.",
        )

        failed_imports = [
            module
            for module, record in result["imports"].items()
            if not record["ok"]
        ]

        if failed_imports:
            result["errors"].append(
                "Failed imports: " + ", ".join(failed_imports)
            )

        origins = result["freeze_origins"]

        if origins["project_local_origins"]:
            result["warnings"].append(
                "Project-local pip origins were found; inspect the origin JSON."
            )

        if origins["other_file_origins"]:
            result["warnings"].append(
                "Unclassified file origins were found; inspect the origin JSON."
            )

        result["status"] = "success" if not result["errors"] else "failed"

    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")

    result["warnings"] = list(dict.fromkeys(result["warnings"]))
    return result


def export_venv(
    name: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    env_path = Path(config["path"])
    python_exe = env_path / "bin/python"

    result: dict[str, Any] = {
        "name": name,
        "manager": "venv",
        "path": str(env_path),
        "status": "failed",
        "warnings": [],
        "errors": [],
    }

    try:
        if not python_exe.is_file():
            raise RuntimeError(f"Missing Python executable: {python_exe}")

        if not (env_path / "pyvenv.cfg").is_file():
            result["warnings"].append(
                "pyvenv.cfg was not found, but the environment Python exists."
            )

        result["python"] = run([str(python_exe), "--version"]).strip()
        result["size"] = environment_size(env_path)

        pip_records = pip_list(python_exe)
        requirements = run([str(python_exe), "-m", "pip", "freeze"])
        exact_freeze = run(
            [str(python_exe), "-m", "pip", "freeze", "--all"]
        )

        result["package_count"] = len(pip_records)
        result["versions"] = version_map(
            result["python"],
            [],
            pip_records,
        )
        result["imports"] = import_checks(python_exe, config["imports"])
        result["freeze_origins"] = classify_freeze_origins(exact_freeze)

        write_text(OUT_ROOT / f"{name}_requirements.txt", requirements)
        write_text(EXACT_ROOT / f"{name}_pip_freeze.txt", exact_freeze)
        write_json(EXACT_ROOT / f"{name}_pip_list.json", pip_records)
        write_json(
            EXACT_ROOT / f"{name}_pip_origin_classification.json",
            result["freeze_origins"],
        )

        failed_imports = [
            module
            for module, record in result["imports"].items()
            if not record["ok"]
        ]

        if failed_imports:
            result["errors"].append(
                "Failed imports: " + ", ".join(failed_imports)
            )

        origins = result["freeze_origins"]

        if origins["project_local_origins"]:
            result["warnings"].append(
                "Project-local pip origins were found; inspect the origin JSON."
            )

        result["status"] = "success" if not result["errors"] else "failed"

    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")

    return result


def generated_file_safety_check() -> dict[str, list[str]]:
    result = {
        "secret_like_files": [],
        "yaml_prefix_files": [],
        "yaml_project_local_files": [],
    }

    for path in OUT_ROOT.rglob("*"):
        if not path.is_file():
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            result["secret_like_files"].append(str(path))

        if path.name.endswith("_environment.yml"):
            if re.search(r"(?m)^prefix:", text):
                result["yaml_prefix_files"].append(str(path))

            if any(value in text for value in PROJECT_LOCAL_ORIGINS):
                result["yaml_project_local_files"].append(str(path))

    return result


def build_report(
    conda: Path,
    results: list[dict[str, Any]],
    safety: dict[str, list[str]],
) -> str:
    lines = [
        "# Environment Export and Validation Report",
        "",
        f"**Created:** `{datetime.now(timezone.utc).isoformat()}`",
        f"**Host:** `{platform.node()}`",
        f"**Platform:** `{platform.platform()}`",
        f"**Conda:** `{conda}`",
        "",
        "## Summary",
        "",
        "| Environment | Manager | Status | Python | Size | Packages | Imports |",
        "|---|---|---|---|---:|---:|---:|",
    ]

    for result in results:
        imports = result.get("imports", {})
        passed = sum(record.get("ok", False) for record in imports.values())

        lines.append(
            "| "
            f"`{result['name']}` | "
            f"{result['manager']} | "
            f"{result['status']} | "
            f"{result.get('python', '—')} | "
            f"{result.get('size', '—')} | "
            f"{result.get('package_count', '—')} | "
            f"{passed}/{len(imports)} |"
        )

    lines += [
        "",
        "## Key package versions",
        "",
        "| Package | "
        + " | ".join(f"`{result['name']}`" for result in results)
        + " |",
        "|---|" + "---:|" * len(results),
    ]

    for package in KEY_PACKAGES:
        values = [
            result.get("versions", {}).get(package, "") or "—"
            for result in results
        ]
        lines.append(f"| `{package}` | " + " | ".join(values) + " |")

    lines += ["", "## Import checks", ""]

    for result in results:
        lines += [
            f"### `{result['name']}`",
            "",
            "| Module | Distribution | Result | Version | Location or error |",
            "|---|---|---|---:|---|",
        ]

        for module, record in result.get("imports", {}).items():
            detail = record["module_file"] if record["ok"] else record["error"]
            detail = str(detail).replace("|", r"\|")

            lines.append(
                "| "
                f"`{module}` | "
                f"`{record['distribution']}` | "
                f"{'pass' if record['ok'] else 'failed'} | "
                f"{record['version'] or '—'} | "
                f"{detail or '—'} |"
            )

        lines.append("")

    lines += [
        "## Pip-origin classification",
        "",
        "| Environment | Conda build origins | Project-local origins | Other file origins | Pip-only packages |",
        "|---|---:|---:|---:|---:|",
    ]

    for result in results:
        origins = result.get("freeze_origins", {})
        lines.append(
            "| "
            f"`{result['name']}` | "
            f"{len(origins.get('conda_build_origins', []))} | "
            f"{len(origins.get('project_local_origins', []))} | "
            f"{len(origins.get('other_file_origins', []))} | "
            f"{result.get('pip_only_count', 'n/a')} |"
        )

    lines += [
        "",
        (
            "`file:///home/conda/feedstock_root/...` entries are normal "
            "conda-forge build-origin metadata. They are retained only in "
            "raw audit snapshots and are not installation instructions."
        ),
        "",
        "## Safety checks",
        "",
        f"- Secret-like files: **{len(safety['secret_like_files'])}**",
        f"- Portable YAMLs retaining `prefix:`: **{len(safety['yaml_prefix_files'])}**",
        f"- Portable YAMLs containing project-local origins: **{len(safety['yaml_project_local_files'])}**",
        "",
        "## Warnings and errors",
        "",
    ]

    for result in results:
        lines += [f"### `{result['name']}`", ""]

        if result["warnings"]:
            lines += [f"- Warning: {value}" for value in result["warnings"]]

        if result["errors"]:
            lines += [f"- Error: {value}" for value in result["errors"]]

        if not result["warnings"] and not result["errors"]:
            lines.append("- None.")

        lines.append("")

    lines += [
        "## Interpretation",
        "",
        "- The three scientific/data environments are Conda environments and receive YAML plus exact Linux specifications.",
        "- `web_launcher` is a Python virtual environment and receives a pip requirements file.",
        "- Raw Conda-environment pip freezes are audit records, not recommended installation files.",
        "- Passing imports confirms the present environment loads its principal packages.",
        "- A recreated environment still requires a model-building and canary-run test.",
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    EXACT_ROOT.mkdir(parents=True, exist_ok=True)

    conda = find_conda()

    print("=" * 100)
    print("EXPORT AND VALIDATE PROJECT PYTHON ENVIRONMENTS")
    print("=" * 100)
    print(f"Conda:      {conda}")
    print(f"Output dir: {OUT_ROOT}")
    print("READ-ONLY: installed environments will not be modified.")
    print()

    results: list[dict[str, Any]] = []

    for name, config in ENVIRONMENTS.items():
        print(f"Processing {name} ({config['manager']}) ...")

        if config["manager"] == "conda":
            result = export_conda(conda, name, config)
        else:
            result = export_venv(name, config)

        results.append(result)

        passed = sum(
            record.get("ok", False)
            for record in result.get("imports", {}).values()
        )
        total = len(result.get("imports", {}))

        print(f"  status:  {result['status']}")
        print(f"  imports: {passed}/{total}")

        for warning in result["warnings"]:
            print(f"  warning: {warning}")

        for error in result["errors"]:
            print(f"  error:   {error}")

        print()

    safety = generated_file_safety_check()

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": platform.platform(),
        "conda": str(conda),
        "environments": results,
        "safety": safety,
    }

    write_json(OUT_ROOT / "environment_manifest.json", manifest)
    write_text(
        OUT_ROOT / "environment_export_report.md",
        build_report(conda, results, safety),
    )

    successful = sum(result["status"] == "success" for result in results)
    failed = [result["name"] for result in results if result["status"] != "success"]

    print("=" * 100)
    print("ENVIRONMENT EXPORT AND VALIDATION COMPLETE")
    print("=" * 100)
    print(f"Successful: {successful}/{len(results)}")
    print(f"Report:     {OUT_ROOT / 'environment_export_report.md'}")
    print(f"Manifest:   {OUT_ROOT / 'environment_manifest.json'}")

    if failed:
        print("Failed:      " + ", ".join(failed))
        print("The script completed without raising a traceback; inspect the report.")
    else:
        print("All four environments exported and passed their configured imports.")

    if safety["secret_like_files"]:
        print("WARNING: secret-like content was detected. Review before committing.")


if __name__ == "__main__":
    main()
