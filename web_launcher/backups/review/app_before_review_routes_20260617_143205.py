#!/usr/bin/env python3
"""
SFINCS Web Launcher - Flask wrapper
Author: Reichen Schaller (epsilon@unc.edu)

This is the first lightweight backend layer.
It serves the HTML pages and provides safe API endpoints for:
  - health check
  - detecting SFINCS input files inside a source folder
  - saving a normal run_config.json

It does not replace the existing pipeline. It should only wrap safe, specific
actions around the real backend runner.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
import subprocess
from datetime import datetime
import csv

from flask import Flask, jsonify, render_template, request, send_from_directory


APP_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(APP_DIR),
    static_folder=str(APP_DIR / "static"),
)

# ---------------------------------------------------------------------
# Safety settings
# ---------------------------------------------------------------------

RUN_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

ALLOWED_ROOTS = [
    Path("/proj/zefflab/projects/Flooding"),
    Path("/work/users"),
    Path.home(),
]

MAX_SCAN_DEPTH = 4
MAX_SCANNED_FILES = 10000

PIPELINE_ROOT = APP_DIR.parent
RUNNER_SCRIPT = PIPELINE_ROOT / "code" / "pipeline_runner.py"

# Use the known-good SFINCS/backend Python for now.
# Later this can switch to /proj/.../pipeline/envs/sfincs/bin/python once tested.
RUNNER_PYTHON = os.environ.get(
    "SFINCS_RUNNER_PYTHON",
    "/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python",
)

ALLOWED_RUNNER_MODES = {"preflight", "build_scripts", "submit"}

MODE_TO_PIPELINE_MODE = {
    "preflight": "preflight_only",
    "build_scripts": "build_scripts_only",
    "submit": "submit_slurm_chain",
}

RUNNER_TIMEOUT_SECONDS = {
    "preflight": 600,
    "build_scripts": 600,
    "submit": 180,
}

# ---------------------------------------------------------------------
# Known SFINCS file candidates
# Keep this aligned with override.html
# ---------------------------------------------------------------------

SFINCS_FILE_CANDIDATES: dict[str, dict[str, Any]] = {
    # Static files
    "depfile": {
        "group": "static",
        "primary": "sfincs.dep",
        "aliases": [],
        "description": "Depth / bed-level input.",
    },
    "mskfile": {
        "group": "static",
        "primary": "sfincs.msk",
        "aliases": [],
        "description": "Active/inactive mask.",
    },
    "indexfile": {
        "group": "static",
        "primary": "sfincs.ind",
        "aliases": [],
        "description": "Binary index file.",
    },
    "sbgfile": {
        "group": "static",
        "primary": "sfincs.sbg",
        "aliases": ["sfincs_subgrid.nc"],
        "description": "Subgrid data file.",
    },
    "manningfile": {
        "group": "static",
        "primary": "sfincs.manning",
        "aliases": ["sfincs.man"],
        "description": "Spatial Manning roughness.",
    },
    "scsfile": {
        "group": "static",
        "primary": "sfincs.scs",
        "aliases": [],
        "description": "SCS infiltration/storage input.",
    },
    "bndfile": {
        "group": "static",
        "primary": "sfincs.bnd",
        "aliases": [],
        "description": "Water-level boundary point geometry.",
    },
    "srcfile": {
        "group": "static",
        "primary": "sfincs.src",
        "aliases": [],
        "description": "Discharge/source point geometry.",
    },
    "obsfile": {
        "group": "static",
        "primary": "sfincs.obs",
        "aliases": [],
        "description": "Observation point geometry.",
    },
    "crsfile": {
        "group": "static",
        "primary": "sfincs.crs",
        "aliases": [],
        "description": "Cross-section / observation line geometry.",
    },
    "thdfile": {
        "group": "static",
        "primary": "sfincs.thd",
        "aliases": [],
        "description": "Thin-dam barrier file.",
    },
    "weirfile": {
        "group": "static",
        "primary": "sfincs.weir",
        "aliases": [],
        "description": "Weir structure file.",
    },
    "drnfile": {
        "group": "static",
        "primary": "sfincs.drn",
        "aliases": [],
        "description": "Drainage structure file.",
    },

    # Event files
    "bzsfile": {
        "group": "event",
        "primary": "sfincs.bzs",
        "aliases": [],
        "description": "Water-level boundary time series.",
    },
    "disfile": {
        "group": "event",
        "primary": "sfincs.dis",
        "aliases": [],
        "description": "Discharge/source time series.",
    },
    "netamprfile": {
        "group": "event",
        "primary": "precip_2d.nc",
        "aliases": ["sfincs_netampr.nc", "sfincs_netamprfile.nc"],
        "description": "NetCDF gridded rainfall.",
    },
    "precipfile": {
        "group": "event",
        "primary": "sfincs.prcp",
        "aliases": [],
        "description": "Text rainfall input.",
    },
    "amprfile": {
        "group": "event",
        "primary": "sfincs.ampr",
        "aliases": [],
        "description": "Spatial rainfall grid input.",
    },
    "amufile": {
        "group": "event",
        "primary": "sfincs.amu",
        "aliases": [],
        "description": "Wind U-component grid.",
    },
    "amvfile": {
        "group": "event",
        "primary": "sfincs.amv",
        "aliases": [],
        "description": "Wind V-component grid.",
    },
    "ampfile": {
        "group": "event",
        "primary": "sfincs.amp",
        "aliases": [],
        "description": "Pressure grid.",
    },
    "wndfile": {
        "group": "event",
        "primary": "sfincs.wnd",
        "aliases": [],
        "description": "Wind time-series file.",
    },
    "spwfile": {
        "group": "event",
        "primary": "sfincs.spw",
        "aliases": [],
        "description": "Spiderweb forcing file.",
    },
    "netspwfile": {
        "group": "event",
        "primary": "spiderweb.nc",
        "aliases": ["sfincs_netspwfile.nc"],
        "description": "NetCDF spiderweb forcing.",
    },
    "netamuamvfile": {
        "group": "event",
        "primary": "sfincs_netamuamvfile.nc",
        "aliases": [],
        "description": "NetCDF wind-vector forcing.",
    },
    "netampfile": {
        "group": "event",
        "primary": "sfincs_netampfile.nc",
        "aliases": [],
        "description": "NetCDF pressure forcing.",
    },
    "rstfile": {
        "group": "event",
        "primary": "sfincs.rst",
        "aliases": [],
        "description": "Restart file.",
    },
    "inifile": {
        "group": "event",
        "primary": "sfincs.ini",
        "aliases": [],
        "description": "Initial-condition file.",
    },

    # Other / rare files
    "sfincs.inp": {
        "group": "other",
        "primary": "sfincs.inp",
        "aliases": [],
        "description": "Full SFINCS input template. Usually leave off.",
    },
    "qinffile": {
        "group": "other",
        "primary": "sfincs.qinf",
        "aliases": [],
        "description": "Infiltration flux file.",
    },
    "smaxfile": {
        "group": "other",
        "primary": "sfincs.smax",
        "aliases": [],
        "description": "Maximum soil storage file.",
    },
    "sefffile": {
        "group": "other",
        "primary": "sfincs.seff",
        "aliases": [],
        "description": "Effective storage file.",
    },
    "ksfile": {
        "group": "other",
        "primary": "sfincs.ks",
        "aliases": [],
        "description": "Hydraulic conductivity file.",
    },
    "sigmafile": {
        "group": "other",
        "primary": "sfincs.sigma",
        "aliases": [],
        "description": "Green-Ampt sigma file.",
    },
    "psifile": {
        "group": "other",
        "primary": "sfincs.psi",
        "aliases": [],
        "description": "Green-Ampt psi file.",
    },
    "f0file": {
        "group": "other",
        "primary": "sfincs.f0",
        "aliases": [],
        "description": "Horton f0 infiltration file.",
    },
    "fcfile": {
        "group": "other",
        "primary": "sfincs.fc",
        "aliases": [],
        "description": "Horton fc infiltration file.",
    },
    "kdfile": {
        "group": "other",
        "primary": "sfincs.kd",
        "aliases": [],
        "description": "Drainage coefficient file.",
    },
    "volfile": {
        "group": "other",
        "primary": "sfincs.vol",
        "aliases": [],
        "description": "Storage volume file.",
    },
    "bzifile": {
        "group": "other",
        "primary": "sfincs.bzi",
        "aliases": [],
        "description": "Boundary initial water-level file.",
    },
    "netbndbzsbzifile": {
        "group": "other",
        "primary": "sfincs_netbndbzsbzifile.nc",
        "aliases": [],
        "description": "Combined boundary NetCDF.",
    },
    "netsrcdisfile": {
        "group": "other",
        "primary": "sfincs_netsrcdisfile.nc",
        "aliases": [],
        "description": "Combined source/discharge NetCDF.",
    },
}

# ---------------------------------------------------------------------
# Launcher site defaults
# ---------------------------------------------------------------------

LAUNCHER_DEFAULTS_PATH = Path(__file__).resolve().parent / "launcher_site_defaults.json"

LAUNCHER_DEFAULT_KEYS = {
    "dataRoot",
    "catalogRoot",
    "eventCatalogRoot",
    "nativeSfincsRoot",
    "overrideSourceRoot",
    "runRoot",
    "projectRoot",
    "condaEnvPath",
    "condaPython",
    "sfincsContainerPath",
}

LAUNCHER_BUILTIN_DEFAULTS = {
    "dataRoot": "/proj/zefflab/projects/Flooding/Data/harris_county",
    "catalogRoot": "/proj/zefflab/projects/Flooding/Data/harris_county/catalogs",
    "eventCatalogRoot": "/proj/zefflab/projects/Flooding/Data/harris_county/catalogs/events_reduced",
    "nativeSfincsRoot": "/proj/zefflab/projects/Flooding/Data/harris_county/catalogs",
    "overrideSourceRoot": "/proj/zefflab/projects/Flooding/Data/harris_county/catalogs",
    "runRoot": "/proj/zefflab/projects/Flooding/sfincs_runs",
    "sfincsContainerPath": "/proj/zefflab/projects/Flooding/pipeline/containers/sfincs-v2.3.0-mt-Faber-Release.sif",
    "condaPython": "/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python",
    "condaEnvPath": "/proj/zefflab/projects/Flooding/pipeline/envs/sfincs",
    "projectRoot": "/proj/zefflab/projects/Flooding/pipeline",
}


def _read_launcher_site_defaults() -> dict:
    defaults = dict(LAUNCHER_BUILTIN_DEFAULTS)

    if not LAUNCHER_DEFAULTS_PATH.exists():
        return defaults

    try:
        data = json.loads(LAUNCHER_DEFAULTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return defaults

    if not isinstance(data, dict):
        return defaults

    for key in LAUNCHER_DEFAULT_KEYS:
        value = str(data.get(key, "")).strip()
        if value:
            defaults[key] = value

    return defaults


def _write_launcher_site_defaults(values: dict) -> dict:
    cleaned = {}

    for key in LAUNCHER_DEFAULT_KEYS:
        value = str(values.get(key, "")).strip()
        if value:
            cleaned[key] = value

    LAUNCHER_DEFAULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = LAUNCHER_DEFAULTS_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(cleaned, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(LAUNCHER_DEFAULTS_PATH)

    return _read_launcher_site_defaults()

def _review_runtime_normalize_path_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    text = str(value).strip()
    if not text:
        return []

    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except Exception:
            pass

    parts = []
    for chunk in text.replace(",", "\n").splitlines():
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def _review_runtime_normalize_time(value):
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "nan", "nat"}:
        return ""

    # SFINCS style: 20170822 000000
    for fmt in (
        "%Y%m%d %H%M%S",
        "%Y%m%d%H%M%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    # Common ISO variants with fractional seconds or trailing Z.
    try:
        iso_text = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(iso_text)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text


# ---------------------------------------------------------------------
# Data catalog detection / autofill helpers
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Manual Mode: native-like catalog warning scan
# Compatibility route used by manual.html
# ---------------------------------------------------------------------

def _manual_catalog_native_warning_reason(path: Path, mask_template_path: str) -> str | None:
    """
    Return a warning reason for source-catalog files that look like native/reference
    SFINCS artifacts.

    Clean mask-template rasters are normal curated source products, not special
    allowed exceptions. Curated validation .xy/.xyxy products are allowed when
    they live in validation folders.
    """
    path = Path(path)
    name = path.name.lower()
    suffix = path.suffix.lower()
    text = str(path).lower()
    parts_l = {part.lower() for part in path.parts}

    if any(part in {"_manifests", "_audit_reports", "_inventory_reports"} for part in parts_l):
        return None

    if "professor_native" in text:
        return "professor_native/reference artifact"

    if "native_sfincs" in text:
        return "native_sfincs/reference artifact"

    native_exact_names = {
        "sfincs.inp",
        "sfincs.dep",
        "sfincs.msk",
        "sfincs.ind",
        "sfincs.sbg",
        "sfincs.manning",
        "sfincs.man",
        "sfincs.scs",
        "sfincs.bnd",
        "sfincs.bzs",
        "sfincs.src",
        "sfincs.dis",
        "sfincs.obs",
        "sfincs.crs",
        "sfincs.thd",
        "sfincs.weir",
        "sfincs.drn",
        "sfincs.qinf",
        "sfincs.smax",
        "sfincs.seff",
        "sfincs.ks",
        "sfincs.sigma",
        "sfincs.psi",
        "sfincs.f0",
        "sfincs.fc",
        "sfincs.kd",
        "sfincs.vol",
    }

    native_suffixes = {
        ".bnd",
        ".bzs",
        ".src",
        ".dis",
        ".obs",
        ".crs",
        ".thd",
        ".sbg",
        ".dep",
        ".msk",
        ".ind",
        ".manning",
        ".weir",
        ".drn",
        ".qinf",
        ".smax",
        ".seff",
        ".ks",
        ".sigma",
        ".psi",
        ".f0",
        ".fc",
        ".kd",
        ".vol",
    }

    if name in native_exact_names or name.startswith("sfincs."):
        return "native SFINCS filename"

    if suffix in native_suffixes:
        return "native SFINCS extension"

    if suffix in {".xy", ".xyxy"}:
        if (
            "event_validation_points" in parts_l
            or "event_validation_lines" in parts_l
            or "reviewed_crs_lines" in parts_l
            or "profiles" in parts_l
        ):
            return None

        return "SFINCS-style obs/CRS control file outside curated validation folders"

    return None

@app.post("/api/manual-catalog-native-warning")
def api_manual_catalog_native_warning_hyphen():
    """
    Yellow frontend warning scan for Manual Mode data catalogs.

    This route intentionally uses hyphens because manual.html calls:
        /api/manual-catalog-native-warning
    """
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config", {}) or {}

    catalogs = cfg.get("data_catalogs", []) or []
    mask_template_path = str(cfg.get("mask_template_path", "") or "")

    if isinstance(catalogs, str):
        try:
            parsed = json.loads(catalogs)
            catalogs = parsed if isinstance(parsed, list) else [catalogs]
        except Exception:
            catalogs = [
                item.strip()
                for item in catalogs.replace(",", "\n").splitlines()
                if item.strip()
            ]

    findings = []

    for raw_root in catalogs:
        root = Path(str(raw_root))

        if not root.exists() or not root.is_dir():
            continue

        for path in root.rglob("*"):
            try:
                if not (path.is_file() or path.is_symlink()):
                    continue

                reason = _manual_catalog_native_warning_reason(path, mask_template_path)

                if reason:
                    findings.append({
                        "path": str(path),
                        "reason": reason,
                        "allowed": reason == "allowed mask-template exception",
                    })

                if path.is_symlink():
                    findings.append({
                        "path": str(path),
                        "reason": "symlink remains in selected data catalog",
                        "allowed": False,
                    })

                if len(findings) >= 80:
                    findings.append({
                        "path": "",
                        "reason": "scan capped at 80 findings",
                        "allowed": False,
                    })
                    break

            except Exception as exc:
                findings.append({
                    "path": str(path),
                    "reason": f"scan error: {type(exc).__name__}: {exc}",
                    "allowed": False,
                })

        if len(findings) >= 80:
            break

    return jsonify({
        "ok": True,
        "findings": findings,
    })

def _catalog_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _catalog_path_list_from_config(cfg: dict[str, Any]) -> tuple[list[Path], list[str]]:
    """
    Read data_catalogs from a Manual/Override config and return safe existing
    catalog directories plus human-readable warnings.

    This accepts the same formats as the runtime-window review:
      - actual JSON list
      - stringified JSON list
      - comma/newline separated paths
    """
    warnings: list[str] = []
    catalog_paths: list[Path] = []

    raw_catalogs = _review_runtime_normalize_path_list(cfg.get("data_catalogs"))

    for raw_catalog in raw_catalogs:
        text = str(raw_catalog).strip()

        if not text:
            continue

        if not text.startswith("/"):
            _catalog_warning(
                warnings,
                f"Skipping non-absolute catalog entry {text!r}. The detector only scans real filesystem paths.",
            )
            continue

        try:
            path = safe_resolve(text)
        except Exception as exc:
            _catalog_warning(warnings, f"Skipping catalog {text!r}: {exc}")
            continue

        if not path.exists():
            _catalog_warning(warnings, f"Catalog path does not exist: {path}")
            continue

        if not path.is_dir():
            _catalog_warning(warnings, f"Catalog path is not a directory: {path}")
            continue

        if path not in catalog_paths:
            catalog_paths.append(path)

    return catalog_paths, warnings


def _catalog_first_match(root: Path, patterns: list[str]) -> str:
    for pattern in patterns:
        matches = sorted(
            path
            for path in root.glob(pattern)
            if path.is_file() and not path.name.startswith(".")
        )
        if matches:
            return str(matches[0])
    return ""

def _catalog_mask_template_match(root: Path) -> str | None:
    """
    Find a preferred mask template for HydroMT/subgrid source builds.

    Priority:
      1. promoted professor/native PPP mask in static source catalog
      2. native gis/msk.tif
      3. generic non-draft mask candidates
      4. DEM-valid draft only as last-resort diagnostic fallback
    """
    priority_patterns = [
        "mask/harris_county_active_mask_template_100m_epsg32615.tif",
        "mask/*professor*msk*.tif",
        "mask/*native*msk*.tif",
        "gis/msk.tif",
        "*/gis/msk.tif",
        "msk.tif",
        "*/msk.tif",
        "mask/*msk*.tif",
        "mask/*mask*.tif",
    ]

    draft_patterns = [
        "mask/*DRAFT*.tif",
        "mask/*dem_valid*.tif",
    ]

    def usable(path: Path) -> bool:
        name = path.name.lower()
        return not any(token in name for token in ["draft", "diagnostic"])

    for pattern in priority_patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and usable(path):
                return str(path)

    for pattern in draft_patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                return str(path)

    return None

def _catalog_all_matches(root: Path, patterns: list[str], limit: int = 25) -> list[str]:
    found: list[Path] = []

    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and not path.name.startswith("."):
                found.append(path)

    unique = sorted(dict.fromkeys(found))
    return [str(path) for path in unique[:limit]]


def _catalog_has_any(root: Path, relative_paths: list[str]) -> bool:
    return any((root / relative_path).exists() for relative_path in relative_paths)


def _read_runtime_csv_values(runtime_csv: str) -> dict[str, Any]:
    if not runtime_csv:
        return {}

    path = Path(runtime_csv)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8", newline="") as f:
        row = next(csv.DictReader(f), None)

    if not row:
        return {}

    return {
        "tref": row.get("tref") or "",
        "tstart": row.get("tstart") or "",
        "tstop": (
            row.get("tstop_recommended_end_exclusive")
            or row.get("tstop")
            or ""
        ),
        "raw": row,
    }


def _derive_hydromt_catalog_paths_from_roots(catalog_roots: list[Path]) -> list[str]:
    """
    No-op by design.

    Older versions tried to derive hydromt_catalog_paths from catalog roots, e.g.
    static_metadata/hydromt_data.yml. That is unsafe because many historical
    catalogs contain stale HydroMT schema and/or machine-specific paths.

    The launcher should stay generic:
      - data_catalogs remains directory roots for detection/runtime review.
      - file fields such as dem_paths, landcover_path, rainfall_path, etc. remain
        explicit local paths.
      - preprocess_stage.py generates a run-local HydroMT catalog from those
        selected paths at build time.
    """
    return []


def _detect_one_data_catalog(root: Path) -> dict[str, Any]:
    """
    Inspect one catalog-like folder and return a mode-neutral description.

    Manual Mode can use suggested_config to fill source paths.
    Override Mode can use the same response to validate/classify event catalogs
    without changing its native static override behavior.
    """
    found: dict[str, Any] = {
        "runtime_csv": _catalog_first_match(root, [
            "event_runtime_window/event_runtime_window.csv",
        ]),
        "region_path": _catalog_first_match(root, [
            "region_geom/*.shp",
            "region_geom/*.geojson",
            "region_geom/*.gpkg",
            "region/*.shp",
            "region/*.geojson",
            "region/*.gpkg",
        ]),
        "dem_path": _catalog_first_match(root, [
            "topobathy/HCFCD_DEM_5m_UTM.tif",
            "topobathy/*.tif",
            "dem/*.tif",
            "elevation/*.tif",
        ]),
        "mask_template_path": _catalog_mask_template_match(root),
        "bathy_paths": _catalog_all_matches(root, [
            "bathy/*.tif",
            "bathymetry/*.tif",
        ]),
        "landcover_path": _catalog_first_match(root, [
            "landcover/*.img",
            "landcover/*.tif",
            "lulc/*.img",
            "lulc/*.tif",
        ]),
        "landcover_reclass_table": _catalog_first_match(root, [
            "manning_reclass_table/*.csv",
            "roughness_mapping/*.csv",
            "landcover_reclass_table/*.csv",
        ]),
        "thin_dam_path": _catalog_first_match(root, [
            "structures_thin_dams/*.shp",
            "structures_thin_dams/*.geojson",
            "structures_thin_dams/*.gpkg",
            "thin_dams/*.shp",
            "thin_dams/*.geojson",
            "thin_dams/*.gpkg",
        ]),
        "weir_path": _catalog_first_match(root, [
            "structures_weirs/*.shp",
            "structures_weirs/*.geojson",
            "structures_weirs/*.gpkg",
            "weirs/*.shp",
            "weirs/*.geojson",
            "weirs/*.gpkg",
        ]),
        "drainage_structure_path": _catalog_first_match(root, [
            "structures_drainage/*.shp",
            "structures_drainage/*.geojson",
            "structures_drainage/*.gpkg",
            "drainage_structures/*.shp",
            "drainage_structures/*.geojson",
            "drainage_structures/*.gpkg",
        ]),
        "rainfall_path": _catalog_first_match(root, [
            "event_precip/*.nc",
            "event_precip/*.zarr",
            "event_precip/*.tif",
            "precip/*.nc",
            "rainfall/*.nc",
        ]),
        "waterlevel_path": _catalog_first_match(root, [
            "event_waterlevel/*.csv",
            "event_boundary_table/*.csv",
            "waterlevel/*.csv",
            "boundary_waterlevel/*.csv",
        ]),
        "discharge_timeseries_csv_path": _catalog_first_match(root, [
            "event_discharge/*.csv",
            "discharge/*.csv",
            "source_discharge/*.csv",
        ]),
        "discharge_points_csv_path": _catalog_first_match(root, [
            "event_source_table/*.csv",
            "source_points_static/*.csv",
            "discharge_points/*.csv",
        ]),
        "curve_number_path": _catalog_first_match(root, [
            "curve_number/cn_avg.tif",
            "curve_number/*avg*.tif",
            "curve_number/*.tif",
            "scs_infiltration/*cn*.tif",
            "infiltration/*cn*.tif",
        ]),
        "obs_points_lite_path": _catalog_first_match(root, [
            "event_validation_points/profiles/lite/*.xy",
            "event_validation_points/profiles/lite/*.csv",
            "obs_points/lite/*.xy",
            "obs_points/*.xy",
        ]),
        "obs_points_validation_path": _catalog_first_match(root, [
            "event_validation_points/profiles/validation/*.xy",
            "event_validation_points/profiles/validation/*.csv",
        ]),
        "obs_points_full_candidates_path": _catalog_first_match(root, [
            "event_validation_points/profiles/full_candidates/*.xy",
            "event_validation_points/profiles/full_candidates/*.csv",
        ]),
        "obs_lines_reviewed_plus_path": _catalog_first_match(root, [
            "event_validation_lines/reviewed_crs_lines/*REVIEWED_PLUS_AUTO_CUSTOM*.xyxy",
        ]),
        "obs_lines_reviewed_path": _catalog_first_match(root, [
            "event_validation_lines/reviewed_crs_lines/*REVIEWED*.xyxy",
            "obs_lines/*.xyxy",
        ]),
        "native_sfincs_files": _catalog_all_matches(root, [
            "sfincs.inp",
            "sfincs.dep",
            "sfincs.msk",
            "sfincs.ind",
            "sfincs.sbg",
            "sfincs.bnd",
            "sfincs.bzs",
            "sfincs.src",
            "sfincs.dis",
            "sfincs.obs",
            "sfincs.crs",
            "sfincs.thd",
            "sfincs.weir",
            "sfincs.drn",
        ]),
    }

    roles: list[str] = []

    if (
        found["runtime_csv"]
        or found["rainfall_path"]
        or found["waterlevel_path"]
        or found["discharge_timeseries_csv_path"]
    ):
        roles.append("event")

    if (
        found["region_path"]
        or found["dem_path"]
        or found["mask_template_path"]
        or found["landcover_path"]
        or found["thin_dam_path"]
    ):
        roles.append("static")

    if (
        found["obs_points_lite_path"]
        or found["obs_points_validation_path"]
        or found["obs_points_full_candidates_path"]
        or found["obs_lines_reviewed_path"]
        or found["obs_lines_reviewed_plus_path"]
    ):
        roles.append("validation")

    native_names = {Path(path).name for path in found["native_sfincs_files"]}
    if {"sfincs.inp", "sfincs.dep", "sfincs.msk"} & native_names:
        roles.append("native_sfincs_package")

    if not roles:
        roles.append("unknown")

    runtime_values = _read_runtime_csv_values(found["runtime_csv"])

    return {
        "path": str(root),
        "name": root.name,
        "roles": roles,
        "found": found,
        "runtime_values": runtime_values,
    }


def detect_data_catalogs_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    catalog_paths, warnings = _catalog_path_list_from_config(cfg)
    catalogs = [_detect_one_data_catalog(path) for path in catalog_paths]
    hydromt_catalog_paths = _derive_hydromt_catalog_paths_from_roots(catalog_paths)

    suggested_config: dict[str, Any] = {}

    if hydromt_catalog_paths:
        suggested_config["hydromt_catalog_paths"] = hydromt_catalog_paths

    def choose_found(key: str) -> str:
        for item in catalogs:
            value = item.get("found", {}).get(key)
            if value:
                return value
        return ""

    def choose_runtime_values() -> dict[str, Any]:
        for item in catalogs:
            values = item.get("runtime_values") or {}
            if values.get("tref") or values.get("tstart") or values.get("tstop"):
                return values
        return {}

    runtime_values = choose_runtime_values()

    if runtime_values.get("tref"):
        suggested_config["tref"] = _review_runtime_normalize_time(runtime_values["tref"])
    if runtime_values.get("tstart"):
        suggested_config["tstart"] = _review_runtime_normalize_time(runtime_values["tstart"])
    if runtime_values.get("tstop"):
        suggested_config["tstop"] = _review_runtime_normalize_time(runtime_values["tstop"])

    region_path = choose_found("region_path")
    if region_path:
        suggested_config["region_mode"] = "geom"
        suggested_config["region_path"] = region_path

    dem_path = choose_found("dem_path")
    if dem_path:
        suggested_config["dem_paths"] = [dem_path]

        # Backend contract:
        # preprocess_stage.py validates raw dem_paths, but HydroMT build also requires
        # a nonempty hydromt_dem_sources/hydromt_bathy_sources list. For curated local
        # topobathy rasters, use the local raster path itself as the elevation entry.
        suggested_config["hydromt_dem_sources"] = [
            {
                "elevation": dem_path,
                "zmin": 0.001,
            }
        ]

        # The HCFCD_DEM_5m_UTM topobathy is already the active integrated
        # elevation/topobathy source. Do not also add legacy bathy ingredients by default.
        suggested_config["hydromt_bathy_sources"] = []
        suggested_config["bathy_paths"] = []

    mask_template_path = choose_found("mask_template_path")
    if mask_template_path:
        suggested_config["use_mask_template"] = True
        suggested_config["mask_template_path"] = mask_template_path
        suggested_config["mask_template_mode"] = "copy"
        
    landcover_path = choose_found("landcover_path")
    if landcover_path:
        suggested_config["landcover_path"] = landcover_path
        suggested_config["landcover_source"] = "local_file"
        suggested_config["use_landcover_roughness_if_available"] = True
        suggested_config["use_spatially_variable_roughness"] = True

    landcover_reclass_table = choose_found("landcover_reclass_table")
    if landcover_reclass_table:
        suggested_config["landcover_reclass_table"] = landcover_reclass_table

    thin_dam_path = choose_found("thin_dam_path")
    if thin_dam_path:
        suggested_config["use_structures"] = True
        suggested_config["thin_dam_source_kind"] = "geodataframe"
        suggested_config["thin_dam_path"] = thin_dam_path

    weir_path = choose_found("weir_path")
    if weir_path:
        suggested_config["use_structures"] = True
        suggested_config["weir_source_kind"] = "geodataframe"
        suggested_config["weir_path"] = weir_path

    drainage_structure_path = choose_found("drainage_structure_path")
    if drainage_structure_path:
        suggested_config["use_structures"] = True
        suggested_config["drainage_structure_source_kind"] = "geodataframe"
        suggested_config["drainage_structure_path"] = drainage_structure_path

    curve_number_path = choose_found("curve_number_path")
    if curve_number_path:
        suggested_config["use_infiltration"] = True
        suggested_config["infiltration_mode"] = "curve_number"
        suggested_config["curve_number_path"] = curve_number_path
        suggested_config["qinf_mm_hr"] = 0.0
        suggested_config["qinf_zmin_m"] = 0.0
        suggested_config["scs_initial_abstraction_factor"] = 0.2

    rainfall_path = choose_found("rainfall_path")
    if rainfall_path:
        suggested_config["use_rainfall"] = True
        suggested_config["rainfall_kind"] = "spatial"
        suggested_config["rainfall_path"] = rainfall_path
        suggested_config["rainfall_source"] = "local_file"

    waterlevel_path = choose_found("waterlevel_path")
    if waterlevel_path:
        suggested_config["use_waterlevel_boundary"] = True
        suggested_config["waterlevel_source_kind"] = "event_catalog_csv"
        suggested_config["waterlevel_path"] = waterlevel_path
        suggested_config["waterlevel_source"] = "local_file"

    discharge_timeseries_csv_path = choose_found("discharge_timeseries_csv_path")
    if discharge_timeseries_csv_path:
        suggested_config["use_discharge_boundary"] = True
        suggested_config["discharge_source_kind"] = "event_catalog_csv"
        suggested_config["discharge_timeseries_csv_path"] = discharge_timeseries_csv_path
        suggested_config["discharge_source"] = "local_file"

    discharge_points_csv_path = choose_found("discharge_points_csv_path")
    if discharge_points_csv_path:
        suggested_config["discharge_points_csv_path"] = discharge_points_csv_path

    obs_points_path = (
        choose_found("obs_points_validation_path")
        or choose_found("obs_points_lite_path")
        or choose_found("obs_points_full_candidates_path")
    )
    if obs_points_path:
        suggested_config["use_obs_points"] = True
        suggested_config["obs_points_path"] = obs_points_path

    obs_lines_path = (
        choose_found("obs_lines_reviewed_plus_path")
        or choose_found("obs_lines_reviewed_path")
    )
    if obs_lines_path:
        suggested_config["use_obs_lines"] = True
        suggested_config["obs_lines_path"] = obs_lines_path

    native_catalogs = [
        item["path"]
        for item in catalogs
        if "native_sfincs_package" in item.get("roles", [])
    ]

    if native_catalogs:
        _catalog_warning(
            warnings,
            "One or more selected catalogs look like native SFINCS packages. Manual Mode should usually use source catalogs; native packages belong in Override Mode.",
        )

    return {
        "catalogs": catalogs,
        "suggested_config": suggested_config,
        "warnings": warnings,
    }


def _review_runtime_check_from_config(cfg):
    requested = {
        "tref": cfg.get("tref"),
        "tstart": cfg.get("tstart"),
        "tstop": cfg.get("tstop"),
    }

    data_catalogs = _review_runtime_normalize_path_list(cfg.get("data_catalogs"))

    audit = {
        "status": "ok",
        "severity": "ok",
        "ui_color": "green",
        "category": "runtime_window_match",
        "message": "No hybrid runtime-window mismatch detected.",
        "reason": "This check compares requested config times against the selected event catalog runtime CSV before preprocessing.",
        "requested": requested,
        "effective": dict(requested),
        "mismatches": {},
        "event_catalog": "",
        "runtime_source_csv": "",
    }

    if not data_catalogs:
        audit.update({
            "status": "not_applicable",
            "severity": "ok",
            "ui_color": "green",
            "category": "runtime_window_not_applicable",
            "message": "No data_catalogs entry is selected, so there is no event-catalog runtime window to compare.",
            "reason": "Runtime mismatch review applies to runs that use an event catalog.",
        })
        return audit

    catalog_paths, warnings = _catalog_path_list_from_config(cfg)

    runtime_path = None
    event_catalog = None

    for catalog_path in catalog_paths:
        candidate = catalog_path / "event_runtime_window" / "event_runtime_window.csv"
        if candidate.exists():
            runtime_path = candidate
            event_catalog = catalog_path
            break

    if runtime_path is None:
        audit.update({
            "status": "major_warning",
            "severity": "major",
            "ui_color": "red",
            "category": "runtime_window_unverified",
            "message": "Could not verify the runtime window because no selected catalog contains event_runtime_window/event_runtime_window.csv.",
            "reason": "The runtime-window review scanned all selected data_catalogs instead of assuming the first catalog is the event catalog."
            + (f" Warnings: {'; '.join(warnings)}" if warnings else ""),
            "event_catalog": "",
            "runtime_source_csv": "",
        })
        return audit

    audit["event_catalog"] = str(event_catalog)
    audit["runtime_source_csv"] = str(runtime_path)

    with runtime_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)

    if not row:
        audit.update({
            "status": "major_warning",
            "severity": "major",
            "ui_color": "red",
            "category": "runtime_window_unverified",
            "message": "Could not verify the runtime window because the event runtime CSV has no rows.",
            "reason": f"Runtime CSV has no readable first row: {runtime_path}",
        })
        return audit

    effective = {
        "tref": row.get("tref") or requested.get("tref"),
        "tstart": row.get("tstart") or requested.get("tstart"),
        "tstop": (
            row.get("tstop_recommended_end_exclusive")
            or row.get("tstop")
            or requested.get("tstop")
        ),
    }

    mismatches = {}
    for key in ("tref", "tstart", "tstop"):
        requested_norm = _review_runtime_normalize_time(requested.get(key))
        effective_norm = _review_runtime_normalize_time(effective.get(key))

        if requested_norm and effective_norm and requested_norm != effective_norm:
            mismatches[key] = {
                "requested_raw": requested.get(key),
                "effective_raw": effective.get(key),
                "requested_normalized": requested_norm,
                "effective_normalized": effective_norm,
            }

    audit["effective"] = effective
    audit["mismatches"] = mismatches

    if mismatches:
        audit.update({
            "status": "major_warning",
            "severity": "major",
            "ui_color": "red",
            "category": "runtime_window_mismatch",
            "message": "MAJOR RUNTIME WINDOW MISMATCH: requested config times do not match the selected event catalog runtime window.",
            "reason": "Submitting this as-is can produce a SFINCS model with a different physical event duration than requested.",
        })

    return audit



@app.route("/api/review-runtime-window", methods=["POST"])
def api_review_runtime_window():
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config") or {}

    if not isinstance(cfg, dict):
        return jsonify({
            "ok": False,
            "error": "Request must contain a JSON object named config.",
        }), 400

    try:
        audit = _review_runtime_check_from_config(cfg)
        return jsonify({
            "ok": True,
            "audit": audit,
        })
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
            "audit": {
                "status": "major_warning",
                "severity": "major",
                "ui_color": "red",
                "category": "runtime_window_review_failed",
                "message": "Runtime window review check failed.",
                "reason": str(exc),
            },
        }), 500


@app.post("/api/detect-data-catalogs")
@app.post("/api/detect-manual-catalogs")
def api_detect_data_catalogs():
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config") or {}

    if not isinstance(cfg, dict):
        return jsonify({
            "ok": False,
            "error": "Request must contain a JSON object named config.",
        }), 400

    try:
        result = detect_data_catalogs_from_config(cfg)
        return jsonify({
            "ok": True,
            **result,
        })
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
            "catalogs": [],
            "suggested_config": {},
            "warnings": [str(exc)],
        }), 500


@app.get("/api/launcher-defaults")
def api_get_launcher_defaults():
    return jsonify({
        "ok": True,
        "defaults": _read_launcher_site_defaults(),
        "defaults_path": str(LAUNCHER_DEFAULTS_PATH),
    })


@app.post("/api/launcher-defaults")
def api_set_launcher_defaults():
    payload = request.get_json(silent=True) or {}
    values = payload.get("defaults", payload)

    if not isinstance(values, dict):
        return jsonify({
            "ok": False,
            "error": "Expected a JSON object of launcher defaults.",
        }), 400

    try:
        saved = _write_launcher_site_defaults(values)
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": f"Could not write launcher defaults: {exc}",
            "defaults_path": str(LAUNCHER_DEFAULTS_PATH),
        }), 500

    return jsonify({
        "ok": True,
        "defaults": saved,
        "defaults_path": str(LAUNCHER_DEFAULTS_PATH),
    })
# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def parse_sfincs_inp_value(value: str) -> Any:
    value = str(value).strip()

    # Strip simple inline comments.
    for marker in ["!", "#"]:
        if marker in value:
            value = value.split(marker, 1)[0].strip()

    if value == "":
        return ""

    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def sfincs_time_to_launcher_time(value: Any) -> str:
    """
    Convert SFINCS time like:
      20170822 000000
    into launcher time like:
      2017-08-22 00:00:00
    """
    s = str(value).strip()

    if len(s) == 15 and s[8] == " ":
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[9:11]}:{s[11:13]}:{s[13:15]}"

    # Already launcher-style.
    if len(s) == 19 and s[4] == "-" and s[13] == ":":
        return s

    return s


def parse_sfincs_inp_file(inp_path: Path) -> dict[str, Any]:
    """
    Parse a detected sfincs.inp enough to hydrate Override Mode fields.
    This is not a full SFINCS parser; it reads simple key=value lines.
    """
    raw: dict[str, Any] = {}

    text = inp_path.read_text(encoding="utf-8", errors="replace")

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue

        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip().lower()
        raw[key] = parse_sfincs_inp_value(value)

    ui_values: dict[str, Any] = {}

    if "tref" in raw:
        ui_values["tref"] = sfincs_time_to_launcher_time(raw["tref"])
    if "tstart" in raw:
        ui_values["tstart"] = sfincs_time_to_launcher_time(raw["tstart"])
    if "tstop" in raw:
        ui_values["tstop"] = sfincs_time_to_launcher_time(raw["tstop"])

    if "dtout" in raw:
        ui_values["dtout_s"] = raw["dtout"]
    if "dthisout" in raw:
        ui_values["dthisout_s"] = raw["dthisout"]
    if "dtrstout" in raw:
        ui_values["dtrstout_s"] = raw["dtrstout"]
    if "dtmaxout" in raw:
        ui_values["dtmaxout_s"] = raw["dtmaxout"]
    if "outputformat" in raw:
        ui_values["output_format"] = raw["outputformat"]

    # Keep file-pointer keys out of advanced_config because the override
    # system manages these separately.
    skip_keys = {
        "tref", "tstart", "tstop",
        "dtout", "dtmapout", "dthisout", "dtrstout", "dtmaxout",
        "outputformat",
    }

    skip_keys.update({
        "depfile", "mskfile", "indexfile", "bndfile", "bzsfile",
        "srcfile", "disfile", "sbgfile", "obsfile", "crsfile",
        "thdfile", "weirfile", "drnfile", "manningfile", "scsfile",
        "netamprfile", "precipfile", "amprfile", "amufile", "amvfile",
        "ampfile", "wndfile", "spwfile", "netspwfile", "netamuamvfile",
        "netampfile", "rstfile", "inifile",
    })

    advanced_config = {
        key: value
        for key, value in raw.items()
        if key not in skip_keys
    }

    return {
        "path": str(inp_path),
        "raw": raw,
        "ui_values": ui_values,
        "advanced_config": advanced_config,
    }


def attach_sfincs_inp_parse(result: dict[str, Any]) -> dict[str, Any]:
    item = result.get("recognized", {}).get("sfincs.inp")

    if not item or not item.get("found") or not item.get("path"):
        return result

    try:
        inp_path = safe_resolve(str(item["path"]))
        item["parsed"] = parse_sfincs_inp_file(inp_path)
    except Exception as exc:
        item["parse_warning"] = str(exc)

    return result

def is_allowed_path(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    allowed_resolved = [root.resolve(strict=False) for root in ALLOWED_ROOTS]
    return any(resolved == root or root in resolved.parents for root in allowed_resolved)


def directory_listing(path: Path) -> dict[str, Any]:
    path = path.resolve(strict=True)

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    entries = []

    for child in path.iterdir():
        if child.name.startswith("."):
            continue

        try:
            child_resolved = child.resolve(strict=False)

            # Avoid following symlinks outside the allowed roots.
            if not is_allowed_path(child_resolved):
                continue

            is_dir = child.is_dir()
            is_file = child.is_file()

            entries.append(
                {
                    "name": child.name,
                    "path": str(child_resolved),
                    "is_dir": is_dir,
                    "is_file": is_file,
                    "size_bytes": child.stat().st_size if is_file else None,
                }
            )

        except PermissionError:
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_dir": False,
                    "is_file": False,
                    "permission_denied": True,
                    "size_bytes": None,
                }
            )
        except OSError:
            continue

    entries.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))

    parent = path.parent.resolve(strict=False)
    parent_text = str(parent) if is_allowed_path(parent) and parent != path else ""

    return {
        "ok": True,
        "path": str(path),
        "parent": parent_text,
        "entries": entries,
    }


def inspect_run_root(run_root: Path) -> dict[str, Any]:
    """
    Classify an output run folder.

    Allowed scaffold/progress:
      - run_config.json
      - saved_config.json
      - launcher_config.json
      - scripts/*.sl or scripts/*.sh
      - empty logs/
      - empty model/
      - empty postprocess/

    Real run artifacts:
      - model files such as sfincs.inp, sfincs.dep, sfincs_map.nc, sfincs_his.nc
      - logs/*.out / logs/*.err / logs/*.log, or any other visible log file
      - postprocess outputs
      - job_ids.txt / failure JSONs / unknown files or folders
    """
    if not run_root.exists():
        return {
            "exists": False,
            "has_real_run": False,
            "allowed_scaffold_paths": [],
            "artifact_paths": [],
        }

    if not run_root.is_dir():
        return {
            "exists": True,
            "has_real_run": True,
            "allowed_scaffold_paths": [],
            "artifact_paths": [str(run_root)],
        }

    allowed_scaffold_paths = []
    artifact_paths = []

    allowed_top_files = {
        "run_config.json",
        "saved_config.json",
        "launcher_config.json",
    }

    allowed_top_dirs = {
        "scripts",
        "logs",
        "model",
        "postprocess",
    }

    allowed_script_suffixes = {".sl", ".sh"}

    for child in run_root.iterdir():
        name = child.name

        if name.startswith("."):
            continue

        if child.is_file() and name in allowed_top_files:
            allowed_scaffold_paths.append(str(child))
            continue

        if child.is_file():
            artifact_paths.append(str(child))
            continue

        if child.is_dir() and name not in allowed_top_dirs:
            artifact_paths.append(str(child))
            continue

        if child.is_dir() and name == "scripts":
            bad_script_contents = []
            for p in child.rglob("*"):
                if p.name.startswith("."):
                    continue
                if p.is_file() and p.suffix in allowed_script_suffixes:
                    allowed_scaffold_paths.append(str(p))
                elif p.is_file():
                    bad_script_contents.append(str(p))

            if bad_script_contents:
                artifact_paths.extend(bad_script_contents[:10])
            else:
                allowed_scaffold_paths.append(str(child))
            continue

        if child.is_dir() and name in {"logs", "model", "postprocess"}:
            visible_files = [
                p for p in child.rglob("*")
                if p.is_file() and not p.name.startswith(".")
            ]

            if visible_files:
                artifact_paths.extend(str(p) for p in visible_files[:10])
            else:
                allowed_scaffold_paths.append(str(child))
            continue

    return {
        "exists": True,
        "has_real_run": bool(artifact_paths),
        "allowed_scaffold_paths": allowed_scaffold_paths,
        "artifact_paths": artifact_paths,
    }


def json_error(message: str, status_code: int = 400, **extra: Any):
    payload = {
        "ok": False,
        "error": message,
    }
    payload.update(extra)
    return jsonify(payload), status_code


def safe_resolve(path_text: str) -> Path:
    if not path_text or not str(path_text).strip():
        raise ValueError("Path is blank.")

    raw = Path(str(path_text)).expanduser()

    if not raw.is_absolute():
        raise ValueError("Path must be absolute.")

    try:
        resolved = raw.resolve(strict=False)
    except RuntimeError as exc:
        raise ValueError(f"Could not resolve path: {exc}") from exc

    allowed_resolved = [root.resolve(strict=False) for root in ALLOWED_ROOTS]
    if not any(resolved == root or root in resolved.parents for root in allowed_resolved):
        allowed_text = ", ".join(str(root) for root in ALLOWED_ROOTS)
        raise ValueError(f"Path is outside allowed roots: {allowed_text}")

    return resolved


def safe_run_name(run_name: str) -> str:
    if not run_name or not RUN_NAME_RE.match(run_name):
        raise ValueError("run_name must use only letters, numbers, underscores, dashes, and periods.")
    return run_name

def staged_config_path(cfg: dict[str, Any], mode: str) -> tuple[Path, Path, Path]:
    run_name = safe_run_name(str(cfg.get("run_name", "")).strip())
    output_root = safe_resolve(str(cfg.get("output_root", "")).strip())

    launcher_config_root = output_root / "_launcher_configs"
    launcher_log_root = output_root / "_launcher_logs" / run_name
    run_root = output_root / run_name

    launcher_config_root.mkdir(parents=True, exist_ok=True)
    launcher_log_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_path = launcher_config_root / f"{run_name}_{stamp}_{mode}.json"

    return config_path, launcher_log_root, run_root


def write_staged_runner_config(cfg: dict[str, Any], mode: str) -> tuple[Path, Path, Path]:
    if mode not in ALLOWED_RUNNER_MODES:
        raise ValueError(f"Unsupported runner mode: {mode}")

    cfg = dict(cfg)
    cfg["pipeline_mode"] = MODE_TO_PIPELINE_MODE[mode]

    config_path, launcher_log_root, run_root = staged_config_path(cfg, mode)

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    return config_path, launcher_log_root, run_root


def run_pipeline_runner(config_path: Path, mode: str, launcher_log_root: Path) -> dict[str, Any]:
    if mode not in ALLOWED_RUNNER_MODES:
        raise ValueError(f"Unsupported runner mode: {mode}")

    runner_python_path = Path(RUNNER_PYTHON)
    if not runner_python_path.exists():
        raise FileNotFoundError(f"Runner Python does not exist: {RUNNER_PYTHON}")

    if not RUNNER_SCRIPT.exists():
        raise FileNotFoundError(f"pipeline_runner.py does not exist: {RUNNER_SCRIPT}")

    cmd = [
        str(runner_python_path),
        str(RUNNER_SCRIPT),
        "--config",
        str(config_path),
        "--mode",
        mode,
    ]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stdout_log = launcher_log_root / f"{stamp}_{mode}.out"
    stderr_log = launcher_log_root / f"{stamp}_{mode}.err"

    completed = subprocess.run(
        cmd,
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=RUNNER_TIMEOUT_SECONDS[mode],
    )

    stdout_log.write_text(completed.stdout or "", encoding="utf-8")
    stderr_log.write_text(completed.stderr or "", encoding="utf-8")

    return {
        "ok": completed.returncode == 0,
        "mode": mode,
        "returncode": completed.returncode,
        "command": cmd,
        "cwd": str(PIPELINE_ROOT),
        "config_path": str(config_path),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }


def iter_files_limited(source: Path, max_depth: int = MAX_SCAN_DEPTH):
    source = source.resolve(strict=True)

    if not source.is_dir():
        raise ValueError(f"Source is not a directory: {source}")

    count = 0
    base_depth = len(source.parts)

    for root, dirs, files in os.walk(source):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth

        if depth >= max_depth:
            dirs[:] = []

        for filename in files:
            count += 1
            if count > MAX_SCANNED_FILES:
                raise ValueError(f"Scan stopped after {MAX_SCANNED_FILES} files. Narrow the source folder.")
            yield root_path / filename


def detect_sfincs_files(source: Path) -> dict[str, Any]:
    files_by_name: dict[str, list[str]] = {}

    for file_path in iter_files_limited(source):
        files_by_name.setdefault(file_path.name, []).append(str(file_path))

    recognized: dict[str, dict[str, Any]] = {}

    for key, info in SFINCS_FILE_CANDIDATES.items():
        candidates = [info["primary"], *info.get("aliases", [])]
        matches = []

        for candidate in candidates:
            for path_text in files_by_name.get(candidate, []):
                matches.append(
                    {
                        "filename": candidate,
                        "path": path_text,
                    }
                )

        recognized[key] = {
            "found": bool(matches),
            "key": key,
            "group": info["group"],
            "primary": info["primary"],
            "aliases": info.get("aliases", []),
            "description": info["description"],
            "matches": matches,
            "filename": matches[0]["filename"] if matches else "",
            "path": matches[0]["path"] if matches else "",
            "multiple_matches": len(matches) > 1,
        }

    return attach_sfincs_inp_parse({
        "ok": True,
        "source_path": str(source),
        "recognized": recognized,
        "file_count": sum(len(v) for v in files_by_name.values()),
        "recognized_count": sum(1 for item in recognized.values() if item["found"]),
    })

def detect_sfincs_files_multiple(sources: list[Path]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}

    for key, info in SFINCS_FILE_CANDIDATES.items():
        merged[key] = {
            "found": False,
            "key": key,
            "group": info["group"],
            "primary": info["primary"],
            "aliases": info.get("aliases", []),
            "description": info["description"],
            "matches": [],
            "filename": "",
            "path": "",
            "multiple_matches": False,
        }

    total_file_count = 0
    source_results = []
    seen_matches: set[tuple[str, str]] = set()

    for source in sources:
        result = detect_sfincs_files(source)
        total_file_count += int(result.get("file_count", 0))

        source_results.append(
            {
                "source_path": str(source),
                "file_count": result.get("file_count", 0),
                "recognized_count": result.get("recognized_count", 0),
            }
        )

        for key, item in result["recognized"].items():
            for match in item.get("matches", []):
                match_path = match.get("path", "")
                marker = (key, match_path)

                if marker in seen_matches:
                    continue

                seen_matches.add(marker)
                merged[key]["matches"].append(match)

    for key, item in merged.items():
        matches = item["matches"]
        item["found"] = bool(matches)
        item["filename"] = matches[0]["filename"] if matches else ""
        item["path"] = matches[0]["path"] if matches else ""
        item["multiple_matches"] = len(matches) > 1

    return attach_sfincs_inp_parse({
        "ok": True,
        "source_paths": [str(source) for source in sources],
        "source_count": len(sources),
        "source_results": source_results,
        "recognized": merged,
        "file_count": total_file_count,
        "recognized_count": sum(1 for item in merged.values() if item["found"]),
    })

# ---------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/index.html")
def index_html():
    return render_template("index.html")


@app.get("/manual.html")
def manual_html():
    return render_template("manual.html")


@app.get("/override.html")
def override_html():
    return render_template("override.html")


@app.get("/batch.html")
def batch_html():
    return render_template("batch.html")


@app.get("/guided.html")
def guided_html():
    return render_template("guided.html")


@app.get("/guide.html")
def guide_html():
    return render_template("guide.html")


# ---------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------



def _manual_catalog_frontend_native_reason(path: Path, mask_template_path: str) -> str | None:
    """
    Frontend review version of the Manual source-catalog native/reference scanner.

    Clean mask-template rasters are normal curated source products, not special
    allowed exceptions. Curated validation .xy/.xyxy products are allowed when
    they live in validation folders.
    """
    path = Path(path)
    name = path.name.lower()
    suffix = path.suffix.lower()
    text = str(path).lower()
    parts_l = {part.lower() for part in path.parts}

    if any(part in {"_manifests", "_audit_reports", "_inventory_reports"} for part in parts_l):
        return None

    if "professor_native" in text:
        return "professor_native/reference artifact"

    if "native_sfincs" in text:
        return "native_sfincs/reference artifact"

    native_exact_names = {
        "sfincs.inp",
        "sfincs.dep",
        "sfincs.msk",
        "sfincs.ind",
        "sfincs.sbg",
        "sfincs.manning",
        "sfincs.man",
        "sfincs.scs",
        "sfincs.bnd",
        "sfincs.bzs",
        "sfincs.src",
        "sfincs.dis",
        "sfincs.obs",
        "sfincs.crs",
        "sfincs.thd",
        "sfincs.weir",
        "sfincs.drn",
        "sfincs.qinf",
        "sfincs.smax",
        "sfincs.seff",
        "sfincs.ks",
        "sfincs.sigma",
        "sfincs.psi",
        "sfincs.f0",
        "sfincs.fc",
        "sfincs.kd",
        "sfincs.vol",
    }

    native_suffixes = {
        ".bnd",
        ".bzs",
        ".src",
        ".dis",
        ".obs",
        ".crs",
        ".thd",
        ".sbg",
        ".dep",
        ".msk",
        ".ind",
        ".manning",
        ".weir",
        ".drn",
        ".qinf",
        ".smax",
        ".seff",
        ".ks",
        ".sigma",
        ".psi",
        ".f0",
        ".fc",
        ".kd",
        ".vol",
    }

    if name in native_exact_names or name.startswith("sfincs."):
        return "native SFINCS filename"

    if suffix in native_suffixes:
        return "native SFINCS extension"

    if suffix in {".xy", ".xyxy"}:
        if (
            "event_validation_points" in parts_l
            or "event_validation_lines" in parts_l
            or "reviewed_crs_lines" in parts_l
            or "profiles" in parts_l
        ):
            return None

        return "SFINCS-style obs/CRS control file outside curated validation folders"

    return None

@app.post("/api/manual_catalog_native_warning")
def api_manual_catalog_native_warning():
    payload = request.get_json(silent=True) or {}

    raw_catalogs = payload.get("data_catalogs", []) or []
    mask_template_path = str(payload.get("mask_template_path", "") or "")

    if isinstance(raw_catalogs, str):
        try:
            parsed = json.loads(raw_catalogs)
            raw_catalogs = parsed if isinstance(parsed, list) else [raw_catalogs]
        except Exception:
            raw_catalogs = [x.strip() for x in raw_catalogs.replace(",", "\n").splitlines() if x.strip()]

    findings = []

    for raw in raw_catalogs:
        root = Path(str(raw))
        if not root.exists() or not root.is_dir():
            continue

        for path in root.rglob("*"):
            try:
                if not (path.is_file() or path.is_symlink()):
                    continue

                reason = _manual_catalog_frontend_native_reason(path, mask_template_path)
                if reason:
                    findings.append({
                        "path": str(path),
                        "reason": reason,
                        "allowed": reason == "allowed mask-template exception",
                    })

                if path.is_symlink():
                    findings.append({
                        "path": str(path),
                        "reason": "symlink remains in data catalog",
                        "allowed": False,
                    })

                if len(findings) >= 80:
                    findings.append({
                        "path": "",
                        "reason": "capped at 80 findings",
                        "allowed": False,
                    })
                    break
            except Exception as exc:
                findings.append({
                    "path": str(path),
                    "reason": f"scan error: {type(exc).__name__}: {exc}",
                    "allowed": False,
                })

        if len(findings) >= 80:
            break

    return jsonify({
        "ok": True,
        "severity": "warning" if findings else "ok",
        "findings": findings,
    })

@app.post("/api/run-pipeline")
def api_run_pipeline():
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config")
    mode = str(payload.get("mode", "")).strip()



    def _is_blank_value(value):
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        return False
    
    
    def _validate_launcher_config_for_run(cfg):
        """Fast Flask-side guard before calling pipeline_runner.py.
    
        This catches broken frontend wiring, empty payloads, and obviously blank
        configs. The backend runner/preflight remains the deeper source of truth.
        """
        if not isinstance(cfg, dict):
            return "Config payload is not a JSON object."
    
        if not cfg:
            return "Config payload is empty. The page did not send getConfig() output."
    
        # Manual has ~217 fields and Override has ~129. A tiny config means
        # frontend helper wiring is probably broken.
        if len(cfg) < 20:
            return (
                f"Config payload only has {len(cfg)} keys. "
                "This is too small for Manual/Override Mode and probably means "
                "pipeline_actions.js could not read the page getConfig() function."
            )
    
        required_present = [
            "run_name",
            "output_root",
            "project_root",
            "pipeline_mode",
            "preprocess_mode",
        ]
        missing = [key for key in required_present if key not in cfg]
        if missing:
            return "Config is missing required core key(s): " + ", ".join(missing)
    
        required_nonblank = [
            "run_name",
            "output_root",
            "project_root",
            "preprocess_mode",
        ]
        blank = [key for key in required_nonblank if _is_blank_value(cfg.get(key))]
        if blank:
            return "Config has blank required core value(s): " + ", ".join(blank)
    
        # These are especially important for actual backend execution.
        # Manual currently uses sfincs_container_path; some older/other configs may use sfincs_container.
        important_paths = [
            "conda_python",
        ]

        blank_paths = [
            key for key in important_paths
            if key in cfg and _is_blank_value(cfg.get(key))
        ]

        container_value = (
            cfg.get("sfincs_container_path")
            if "sfincs_container_path" in cfg
            else cfg.get("sfincs_container")
        )

        if _is_blank_value(container_value):
            blank_paths.append("sfincs_container_path/sfincs_container")

        if blank_paths:
            return "Config has blank backend path value(s): " + ", ".join(blank_paths)
    
        return None
    
    
    config_error = _validate_launcher_config_for_run(cfg)
    if config_error:
        return jsonify({
            "ok": False,
            "mode": mode,
            "error": config_error,
            "returncode": 2,
            "stdout": "",
            "stderr": config_error,
        }), 400
    if not isinstance(cfg, dict):
        return json_error("Request must contain a JSON object named 'config'.", 400)

    if mode not in ALLOWED_RUNNER_MODES:
        return json_error(
            f"Unsupported mode '{mode}'. Allowed modes: {sorted(ALLOWED_RUNNER_MODES)}",
            400,
        )

    run_name = str(cfg.get("run_name", "")).strip()
    if not run_name:
        return json_error("run_name is required.", 400)

    if not RUN_NAME_RE.match(run_name):
        return json_error(
            "run_name may only contain letters, numbers, underscores, hyphens, and periods.",
            400,
            run_name=run_name,
        )

    output_root_text = str(cfg.get("output_root", "")).strip()
    if not output_root_text:
        return json_error("output_root is required.", 400)

    output_root = safe_resolve(output_root_text)
    run_root = output_root / run_name

    overwrite = bool(cfg.get("overwrite_existing_run", False))
    run_state = inspect_run_root(run_root)

    if mode in {"build_scripts", "submit"} and run_state["has_real_run"] and not overwrite:
        return json_error(
            "This run folder appears to already contain real generated run artifacts. "
            "Use a new run_name, or set overwrite_existing_run=true only if you intentionally want to overwrite this run.",
            409,
            run_root=str(run_root),
            run_state=run_state,
        )

    try:
        config_path, launcher_log_root, run_root = write_staged_runner_config(cfg, mode)

        # Build/submit will create or reuse the actual run folder through pipeline_runner.py.
        # If it already exists and overwrite_existing_run is false, stop early with a clear message.
        overwrite = bool(cfg.get("overwrite_existing_run", False))
        run_state = inspect_run_root(run_root)
        
        if mode in {"build_scripts", "submit"} and run_state["has_real_run"] and not overwrite:
            return json_error(
                "This run folder appears to already contain generated run artifacts. "
                "Use a new run_name, or set overwrite_existing_run=true only if you intentionally want to overwrite this run.",
                409,
                run_root=str(run_root),
                staged_config_path=str(config_path),
                run_state=run_state,
            )

        result = run_pipeline_runner(config_path, mode, launcher_log_root)
        result["run_root"] = str(run_root)
        result["run_state_before"] = run_state

    except subprocess.TimeoutExpired as exc:
        return json_error(
            f"Runner timed out after {exc.timeout} seconds.",
            504,
        )
    except Exception as exc:
        return json_error(str(exc), 400)

    return jsonify(result)


@app.post("/api/list-directory")
def api_list_directory():
    payload = request.get_json(silent=True) or {}
    path_text = str(payload.get("path", "")).strip()

    try:
        # Blank path means show allowed starting roots.
        if not path_text:
            roots = []
            for root in ALLOWED_ROOTS:
                root_resolved = root.resolve(strict=False)
                roots.append(
                    {
                        "name": str(root_resolved),
                        "path": str(root_resolved),
                        "is_dir": True,
                        "is_file": False,
                        "size_bytes": None,
                    }
                )

            return jsonify(
                {
                    "ok": True,
                    "path": "",
                    "parent": "",
                    "entries": roots,
                }
            )

        path = safe_resolve(path_text)

        if not path.exists():
            return json_error(f"Path does not exist: {path}", 404)

        if path.is_file():
            path = path.parent

        result = directory_listing(path)

    except Exception as exc:
        return json_error(str(exc), 400)

    return jsonify(result)

@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "app_dir": str(APP_DIR),
            "allowed_roots": [str(path) for path in ALLOWED_ROOTS],
        }
    )


@app.post("/api/detect-sfincs-files")
def api_detect_sfincs_files():
    payload = request.get_json(silent=True) or {}

    raw_sources = payload.get("source_paths")

    # Backward compatibility with the old one-path version.
    if raw_sources is None:
        raw_sources = [payload.get("source_path", "")]

    if isinstance(raw_sources, str):
        raw_sources = [raw_sources]

    if not isinstance(raw_sources, list):
        return json_error("source_paths must be a list of absolute folder paths.", 400)

    try:
        sources = []
        for source_text in raw_sources:
            source_text = str(source_text).strip()
            if not source_text:
                continue
            sources.append(safe_resolve(source_text))

        if not sources:
            return json_error("No source folders were provided.", 400)

        result = detect_sfincs_files_multiple(sources)

    except Exception as exc:
        return json_error(str(exc), 400)

    return jsonify(result)


@app.post("/api/save-config")
def save_config():
    payload = request.get_json(silent=True) or {}

    cfg = payload.get("config")
    if cfg is None:
        cfg = {
            k: v for k, v in payload.items()
            if k not in {"confirm_update"}
        }

    confirm_update = bool(payload.get("confirm_update", False))

    if not isinstance(cfg, dict):
        return json_error("Expected a JSON object config.", 400)

    run_name = str(cfg.get("run_name", "")).strip()
    if not run_name:
        return json_error("run_name is required before saving.", 400)

    if not RUN_NAME_RE.match(run_name):
        return json_error(
            "run_name may only contain letters, numbers, underscores, hyphens, and periods.",
            400,
            run_name=run_name,
        )

    output_root_text = str(cfg.get("output_root", "")).strip()
    if not output_root_text:
        return json_error("output_root is required before saving.", 400)

    output_root = safe_resolve(output_root_text)
    run_root = output_root / run_name
    config_path = run_root / "run_config.json"

    run_state = inspect_run_root(run_root)
    existed_before = config_path.exists()

    if existed_before and not confirm_update:
        return jsonify({
            "ok": False,
            "needs_confirmation": True,
            "message": "A saved run_config.json already exists for this run_name. Do you want to update it?",
            "run_root": str(run_root),
            "config_path": str(config_path),
            "run_state": run_state,
        }), 409

    run_root.mkdir(parents=True, exist_ok=True)

    config_path.write_text(
        json.dumps(cfg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return jsonify({
        "ok": True,
        "saved": True,
        "updated_existing": existed_before,
        "run_root": str(run_root),
        "config_path": str(config_path),
        "run_state": inspect_run_root(run_root),
    })

#------------------------------------------------------------------------------
#comparison script
#--------------------------------------------------------------------------
# ---------------------------------------------------------------------
# Compare Runs mode
# ---------------------------------------------------------------------

WEB_LAUNCHER_DIR = Path(__file__).resolve().parent
PIPELINE_ROOT = Path("/proj/zefflab/projects/Flooding/pipeline")
COMPARE_MANAGER = PIPELINE_ROOT / "code" / "compare_job_manager.py"
COMPARE_PYTHON = PIPELINE_ROOT / "envs" / "sfincs" / "bin" / "python"
COMPARE_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs/_compare_jobs").resolve()

COMPARE_RUN_ROOTS = [
    Path("/proj/zefflab/projects/Flooding/sfincs_runs"),
    Path("/work/users/e/p/epsilon/sfincs_runs"),
]


def _json_error(message, status=400, **extra):
    payload = {"status": "error", "message": str(message)}
    payload.update(extra)
    return jsonify(payload), status


def _run_manager(args):
    cmd = [str(COMPARE_PYTHON), str(COMPARE_MANAGER)] + list(args)

    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "compare_job_manager.py failed"
        raise RuntimeError(message)

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Manager returned invalid JSON: {exc}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")


def _safe_compare_job_dir(raw_job_dir):
    if not raw_job_dir:
        raise ValueError("Missing job_dir.")

    job_dir = Path(raw_job_dir).expanduser().resolve()

    try:
        job_dir.relative_to(COMPARE_ROOT)
    except ValueError:
        raise ValueError(f"Job folder is outside compare root: {job_dir}")

    if not job_dir.exists():
        raise ValueError(f"Compare job folder does not exist: {job_dir}")

    return job_dir


@app.route("/compare")
def compare_page():
    return send_from_directory(WEB_LAUNCHER_DIR, "compare.html")


@app.route("/compare/status")
def compare_status_page():
    return send_from_directory(WEB_LAUNCHER_DIR, "compare_status.html")


@app.route("/compare/result")
def compare_result_page():
    return send_from_directory(WEB_LAUNCHER_DIR, "compare_result.html")

@app.route("/api/compare/pair-result")
def api_compare_pair_result():
    try:
        job_dir = _safe_compare_job_dir(request.args.get("job_dir", ""))
        filename = request.args.get("file", "")

        if not filename:
            return _json_error("Missing pair result file name.")

        # Only allow simple pair result filenames inside the job folder.
        if "/" in filename or "\\" in filename or not filename.startswith("pair_") or not filename.endswith("_result.json"):
            return _json_error(f"Invalid pair result filename: {filename}")

        result_path = job_dir / filename

        try:
            result_path.resolve().relative_to(job_dir.resolve())
        except ValueError:
            return _json_error("Pair result path escaped the compare job folder.")

        if not result_path.exists():
            return _json_error(f"Pair result file does not exist yet: {filename}", status=404)

        return jsonify(json.loads(result_path.read_text()))

    except Exception as exc:
        return _json_error(exc)

@app.route("/api/compare/search-runs")
def api_compare_search_runs():
    try:
        q = request.args.get("q", "").strip().lower()
        root_text = request.args.get("root", "").strip()
        out = []

        allowed_search_bases = [
            Path("/proj/zefflab/projects/Flooding"),
            Path("/work/users"),
            Path.home(),
        ]

        def is_inside_any_allowed_base(path):
            try:
                resolved = path.resolve()
            except Exception:
                return False

            for base in allowed_search_bases:
                try:
                    resolved.relative_to(base.resolve())
                    return True
                except ValueError:
                    continue

            return False

        def looks_like_run(path):
            return (
                path.is_dir()
                and (
                    (path / "model").exists()
                    or (path / "sfincs.inp").exists()
                    or (path / "model" / "sfincs.inp").exists()
                )
            )

        def summarize_run(path):
            model = path / "model"
            summary_parts = []

            if (model / "sfincs.inp").exists() or (path / "sfincs.inp").exists():
                summary_parts.append("sfincs.inp")
            if (model / "sfincs_map.nc").exists():
                summary_parts.append("sfincs_map.nc")
            if (model / "sfincs_his.nc").exists():
                summary_parts.append("sfincs_his.nc")
            if (model / "precip_2d.nc").exists():
                summary_parts.append("precip_2d.nc")

            return ", ".join(summary_parts) if summary_parts else "SFINCS-like run folder"

        # If user pasted a direct run folder into the search box, return it.
        if q.startswith("/"):
            direct = Path(q).expanduser()
            if direct.exists() and is_inside_any_allowed_base(direct) and looks_like_run(direct):
                return jsonify({
                    "runs": [{
                        "name": direct.name,
                        "path": str(direct.resolve()),
                        "summary": "Direct path match",
                    }]
                })

        # Custom root from Browse field; otherwise default roots.
        if root_text:
            search_roots = [Path(root_text).expanduser()]
        else:
            search_roots = COMPARE_RUN_ROOTS

        for root in search_roots:
            if not root.exists():
                continue

            root = root.resolve()

            if not is_inside_any_allowed_base(root):
                continue

            # If selected root itself is a run, include it.
            if looks_like_run(root):
                text = str(root).lower()
                if not q or q in text:
                    out.append({
                        "name": root.name,
                        "path": str(root),
                        "summary": summarize_run(root),
                    })

            try:
                children = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            except Exception:
                continue

            for child in children:
                if len(out) >= 80:
                    break

                if not child.is_dir():
                    continue

                if child.name.startswith("_"):
                    continue

                text = str(child).lower()
                if q and q not in text:
                    continue

                if not looks_like_run(child):
                    continue

                out.append({
                    "name": child.name,
                    "path": str(child.resolve()),
                    "summary": summarize_run(child),
                })

        return jsonify({"runs": out})

    except Exception as exc:
        return _json_error(exc)


@app.route("/api/compare/recommend", methods=["POST"])
def api_compare_recommend():
    try:
        data = request.get_json(force=True) or {}
        level = data.get("level", "quick")
        runs = data.get("runs", [])

        if not isinstance(runs, list):
            return _json_error("runs must be a list")

        args = ["recommend", "--level", str(level), "--runs"] + [str(r) for r in runs]
        result = _run_manager(args)
        return jsonify(result)

    except Exception as exc:
        return _json_error(exc)


@app.route("/api/compare/submit", methods=["POST"])
def api_compare_submit():
    try:
        data = request.get_json(force=True) or {}
        level = data.get("level", "quick")
        runs = data.get("runs", [])
        mem = str(data.get("mem", "")).strip()
        cpus = str(data.get("cpus", "")).strip()
        time = str(data.get("time", "")).strip()

        if not isinstance(runs, list):
            return _json_error("runs must be a list")

        args = ["submit", "--level", str(level), "--runs"] + [str(r) for r in runs]

        if mem:
            args += ["--mem", mem]
        if cpus:
            args += ["--cpus", cpus]
        if time:
            args += ["--time", time]

        result = _run_manager(args)
        return jsonify(result)

    except Exception as exc:
        return _json_error(exc)


@app.route("/api/compare/status")
def api_compare_status():
    try:
        job_dir = request.args.get("job_dir", "")
        result = _run_manager(["status", "--job-dir", job_dir])
        return jsonify(result)

    except Exception as exc:
        return _json_error(exc)


@app.route("/api/compare/result")
def api_compare_result():
    try:
        job_dir = _safe_compare_job_dir(request.args.get("job_dir", ""))
        result_path = job_dir / "compare_result.json"

        if not result_path.exists():
            return _json_error("compare_result.json does not exist yet.", status=404)

        return jsonify(json.loads(result_path.read_text()))

    except Exception as exc:
        return _json_error(exc)


@app.route("/api/review-native-shapes", methods=["POST"])
def review_native_shapes():
    """Basic native SFINCS file shape compatibility checks.

    Checks:
      - sfincs.bnd row count vs sfincs.bzs value columns
      - sfincs.src row count vs sfincs.dis value columns

    This is intentionally narrow and safe. It only inspects selected override
    files that were already detected by the Override page.
    """
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config") or {}

    overrides = cfg.get("sfincs_file_overrides") or {}
    manifest = cfg.get("override_detection_manifest") or {}

    allowed_roots = [
        Path("/proj/zefflab/projects/Flooding"),
        Path("/work/users/e/p/epsilon"),
        Path("/users/e/p/epsilon"),
    ]

    def safe_path(raw):
        if not raw:
            return None

        p = Path(str(raw)).expanduser().resolve()

        if not any(str(p).startswith(str(root)) for root in allowed_roots):
            raise ValueError(f"Path is outside allowed launcher roots: {p}")

        return p

    def selected_path(key):
        if not overrides.get(key):
            return None

        item = manifest.get(key) or {}
        raw = item.get("path") or ""

        if not raw:
            return None

        return safe_path(raw)

    def nonempty_data_lines(path):
        lines = []

        for line in path.read_text(errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            lines.append(s)

        return lines

    def count_geometry_rows(path):
        if not path.exists():
            raise FileNotFoundError(str(path))

        return len(nonempty_data_lines(path))

    def looks_like_date_time_row(parts):
        if len(parts) < 3:
            return False

        first = parts[0]
        second = parts[1]

        # Common date/time rows:
        #   2017-08-22 00:00:00 value...
        #   20170822 000000 value...
        if "-" in first and ":" in second:
            return True

        if first.isdigit() and len(first) == 8 and second.isdigit() and len(second) == 6:
            return True

        return False

    def count_timeseries_value_columns(path):
        if not path.exists():
            raise FileNotFoundError(str(path))

        lines = nonempty_data_lines(path)

        if not lines:
            return None, []

        sample = [line.split() for line in lines[:5]]
        first = sample[0]

        if looks_like_date_time_row(first):
            value_cols = len(first) - 2
        else:
            # Common SFINCS format:
            #   seconds_since_tref value1 value2 ...
            value_cols = len(first) - 1

        return value_cols, sample[:2]

    def check_pair(label, geometry_key, forcing_key, geometry_label, forcing_label):
        geometry_selected = bool(overrides.get(geometry_key))
        forcing_selected = bool(overrides.get(forcing_key))

        if not geometry_selected and not forcing_selected:
            return None

        if geometry_selected and not forcing_selected:
            return {
                "status": "warn",
                "title": f"{label} shape check skipped.",
                "detail": f"{geometry_label} is selected, but {forcing_label} is not selected.",
            }

        if forcing_selected and not geometry_selected:
            return {
                "status": "warn",
                "title": f"{label} shape check skipped.",
                "detail": f"{forcing_label} is selected, but {geometry_label} is not selected.",
            }

        geometry_path = selected_path(geometry_key)
        forcing_path = selected_path(forcing_key)

        if not geometry_path or not forcing_path:
            return {
                "status": "warn",
                "title": f"{label} shape check could not read selected paths.",
                "detail": (
                    f"Selected keys: {geometry_key}, {forcing_key}. "
                    "Detection manifest is missing one or both file paths. "
                    "Run Detect all again before Review Checks."
                ),
            }

        geometry_rows = count_geometry_rows(geometry_path)
        forcing_cols, sample = count_timeseries_value_columns(forcing_path)

        if forcing_cols is None:
            return {
                "status": "bad",
                "title": f"{label} shape check failed.",
                "detail": f"{forcing_path} had no readable data rows.",
            }

        if geometry_rows == forcing_cols:
            return {
                "status": "good",
                "title": f"{label} shape check passed.",
                "detail": (
                    f"{geometry_label} rows: {geometry_rows}\n"
                    f"{forcing_label} value columns: {forcing_cols}\n"
                    f"{geometry_label}: {geometry_path}\n"
                    f"{forcing_label}: {forcing_path}\n"
                    f"Sample {forcing_label} rows: {sample}"
                ),
            }

        return {
            "status": "bad",
            "title": f"{label} shape mismatch.",
            "detail": (
                f"{geometry_label} rows: {geometry_rows}\n"
                f"{forcing_label} value columns: {forcing_cols}\n"
                f"These must match. The forcing time-series columns do not match "
                f"the selected static geometry count.\n"
                f"{geometry_label}: {geometry_path}\n"
                f"{forcing_label}: {forcing_path}\n"
                f"Sample {forcing_label} rows: {sample}"
            ),
        }

    checks = []

    try:
        for item in [
            check_pair(
                "BND/BZS",
                "bndfile",
                "bzsfile",
                "sfincs.bnd",
                "sfincs.bzs",
            ),
            check_pair(
                "SRC/DIS",
                "srcfile",
                "disfile",
                "sfincs.src",
                "sfincs.dis",
            ),
        ]:
            if item:
                checks.append(item)

        if not checks:
            checks.append({
                "status": "warn",
                "title": "Native shape check skipped.",
                "detail": (
                    "No selected BND/BZS or SRC/DIS native file pairs were available. "
                    "This is expected for non-native or incomplete Review Check setups."
                ),
            })

        worst = "good"
        if any(c["status"] == "bad" for c in checks):
            worst = "bad"
        elif any(c["status"] == "warn" for c in checks):
            worst = "warn"

        return jsonify({
            "ok": True,
            "status": worst,
            "checks": checks,
        })

    except Exception as exc:
        return jsonify({
            "ok": False,
            "status": "bad",
            "checks": [{
                "status": "bad",
                "title": "Native shape check crashed.",
                "detail": str(exc),
            }],
            "error": str(exc),
        }), 200


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------

if __name__ == "__main__":
    host = os.environ.get("WEB_LAUNCHER_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_LAUNCHER_PORT", "5000"))

    print(f"Starting SFINCS Web Launcher on http://{host}:{port}")
    print(f"App directory: {APP_DIR}")
    print("Allowed roots:")
    for root in ALLOWED_ROOTS:
        print(f"  - {root}")

    app.run(host=host, port=port, debug=True)