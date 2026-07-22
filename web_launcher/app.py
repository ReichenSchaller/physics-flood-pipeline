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
import shlex
import traceback
from datetime import datetime, timezone
import csv
import sys

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
    APP_DIR,
    APP_DIR.parent,
    Path.home(),
]

MAX_SCAN_DEPTH = 4
MAX_SCANNED_FILES = 10000

PIPELINE_ROOT = APP_DIR.parent
RUNNER_SCRIPT = PIPELINE_ROOT / "code" / "pipeline_runner.py"

# Optional environment override. Normal launcher behavior should use
# launcher_site_defaults.json via the Settings menu.
RUNNER_PYTHON_ENV = os.environ.get("SFINCS_RUNNER_PYTHON", "").strip()

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
GEOMETRY_CHECK_SCRIPT = PIPELINE_ROOT / "code" / "manual_geometry_check.py"
GEOMETRY_CHECK_LOCAL_TIMEOUT_SECONDS = 1800

GEOMETRY_CHECK_SLURM_TIME = "00:30:00"
GEOMETRY_CHECK_SLURM_CPUS = 4
GEOMETRY_CHECK_SLURM_MEM = "64G"

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
    "contextilyPython",
    "sfincsContainerPath",
    "browseAllowedRoots",
}

LAUNCHER_BUILTIN_DEFAULTS = {
    key: ""
    for key in LAUNCHER_DEFAULT_KEYS
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



def launcher_default_value(key: str) -> str:
    """Read one launcher setting from launcher_site_defaults.json."""
    return str(_read_launcher_site_defaults().get(key, "") or "").strip()


def split_launcher_path_list(value: Any) -> list[Path]:
    """
    Accept newline, comma, or JSON-list text from the Settings menu and return
    absolute Path objects.

    This is used for browseAllowedRoots.
    """
    if value is None:
        return []

    if isinstance(value, list):
        raw_items = value
    else:
        text = str(value or "").strip()

        if not text:
            return []

        if text.startswith("["):
            try:
                parsed = json.loads(text)
                raw_items = parsed if isinstance(parsed, list) else [text]
            except Exception:
                raw_items = re.split(r"[\n,]+", text)
        else:
            raw_items = re.split(r"[\n,]+", text)

    paths: list[Path] = []

    for raw in raw_items:
        text = str(raw or "").strip()

        if not text:
            continue

        path = Path(text).expanduser()

        if path.is_absolute():
            paths.append(path)

    return paths


def launcher_default_path_root(key: str) -> Path | None:
    """
    Convert a launcher setting into an allowed root.

    Directory-like settings are allowed as-is.
    File-like settings allow their parent directory.
    """
    value = launcher_default_value(key)

    if not value.startswith("/"):
        return None

    path = Path(value).expanduser()

    file_like_keys = {
        "condaPython",
        "contextilyPython",
        "sfincsContainerPath",
    }

    if key in file_like_keys:
        return path.parent

    if path.suffix:
        return path.parent

    return path


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
        "%Y %m %d %H:%M:%S",
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
    allowed exceptions. Curated validation .xy point files and .crs line files
    are allowed when they live in validation folders.
    """
    path = Path(path)
    name = path.name.lower()
    suffix = path.suffix.lower()
    text = str(path).lower()
    parts_l = {part.lower() for part in path.parts}

    # Curated Manual observation/CRS line inputs are allowed catalog source files.
    # They are copied later to model/sfincs.crs, but the source catalog file itself
    # is a normal Manual validation input, not contamination.
    if suffix == ".crs" and "event_validation_lines" in parts_l:
        return None

    if any(part in {"_misc", "_manifests", "_audit_reports", "_inventory_reports"} for part in parts_l):
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

    selected_allowed_paths = set()

    for key in ["obs_points_path", "obs_lines_path", "active_mask_path"]:
        value = str(cfg.get(key, "") or "").strip()
        if value:
            try:
                selected_allowed_paths.add(str(Path(value).resolve(strict=False)))
            except Exception:
                selected_allowed_paths.add(value)

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
                if _catalog_path_is_ignored(path):
                    continue

                if not (path.is_file() or path.is_symlink()):
                    continue

                try:
                    resolved_text = str(path.resolve(strict=False))
                except Exception:
                    resolved_text = str(path)

                if resolved_text in selected_allowed_paths:
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

def _catalog_path_is_ignored(path: Path) -> bool:
    """
    Return True for local quarantine/admin folders that catalog detection and
    Manual warning scans should ignore.

    Project convention:
      - _misc can live inside any catalog folder as a local quarantine/scratch folder.
      - files inside _misc must not be detected, autofilled, or flagged as Manual
        native/reference contamination.
    """
    ignored_parts = {
        "_misc",
        "_manifests",
        "_audit_reports",
        "_inventory_reports",
    }

    return any(part.lower() in ignored_parts for part in Path(path).parts)

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


def _catalog_first_top_level_file(
    root: Path,
    folder: str,
    suffixes: set[str] | None = None,
    allow_dirs: bool = False,
) -> str:
    """Return the first active top-level file in a catalog subfolder.

    Active catalog policy:
      - only top-level files in the named folder are candidates;
      - anything under _misc/_quarantine/etc. is ignored;
      - if multiple active files are exposed, use alphabetical first.
    """
    folder_path = root / folder
    if not folder_path.exists() or not folder_path.is_dir():
        return ""

    suffixes_l = {s.lower() for s in suffixes} if suffixes else None

    for path in sorted(folder_path.iterdir(), key=lambda p: p.name.lower()):
        if _catalog_path_is_ignored(path):
            continue
        if not path.is_file():
            if not (allow_dirs and path.is_dir()):
                continue
        if suffixes_l is not None and path.suffix.lower() not in suffixes_l:
            continue
        return str(path)

    return ""


def _catalog_first_match(root: Path, patterns: list[str]) -> str:
    for pattern in patterns:
        matches = sorted(
            path
            for path in root.glob(pattern)
            if (
                path.is_file()
                and not _catalog_path_is_ignored(path)
            )
        )
        if matches:
            return str(matches[0])
    return ""

def _catalog_active_mask_match(root: Path) -> str | None:
    """
    Find a preferred active-area mask for HydroMT/subgrid source builds.

    This is for Manual/HydroMT builds:
      - active_mask_path gates active cells after the grid exists
      - it does not define grid geometry
      - it is not a native SFINCS override
    """
    priority_patterns = [
        "mask/dem_valid_100m_mask_ge95_DRAFT.tif",
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

        curated_active_mask_names = {
            "dem_valid_100m_mask_ge95_draft.tif",
            "harris_county_active_mask_template_100m_epsg32615.tif",
        }

        if name in curated_active_mask_names:
            return True

        return not any(token in name for token in ["draft", "diagnostic"])

    for pattern in priority_patterns:
        for path in sorted(root.glob(pattern)):
            if _catalog_path_is_ignored(path):
                continue

            if path.is_file() and usable(path):
                return str(path)

    for pattern in draft_patterns:
        for path in sorted(root.glob(pattern)):
            if _catalog_path_is_ignored(path):
                continue

            if path.is_file() and usable(path):
                return str(path)

    return None

def _catalog_all_matches(root: Path, patterns: list[str], limit: int = 25) -> list[str]:
    found: list[Path] = []

    for pattern in patterns:
        for path in root.glob(pattern):
            if (
                path.is_file()
                and not path.name.startswith(".")
                and not _catalog_path_is_ignored(path)
            ):
                found.append(path)

    unique = sorted(dict.fromkeys(found))
    return [str(path) for path in unique[:limit]]

OPEN_BOUNDARY_AUTOFILL_KEYS = {
    "open_boundary_mask_mode",
    "open_boundary_outline_path",
    "open_boundary_outline_buffer_m",
    "open_boundary_min_cells",
    "open_boundary_max_cells",
    "open_boundary_require_edge_adjacency",
    "open_boundary_allow_overwrite_special",
}


def _read_open_boundary_outline_manifest(
    manifest_path: str,
    fallback_outline_path: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """
    Read a static-catalog open-boundary manifest and return safe launcher
    suggested_config values.

    Resolution order for the outline geometry:
      1. Use the path declared by the manifest when it exists.
      2. If the manifest path is missing or stale, use the outline file that
         catalog detection independently found.
      3. Never place a nonexistent outline path into suggested_config.

    Relative paths inside the manifest are resolved relative to the manifest
    directory. This keeps the manifest portable when the data root moves.

    The current backend enum is still named coastal_outline, but the manifest may
    describe a broader reviewed open-boundary outline containing coastal and
    inland/channel outlet segments.
    """
    warnings: list[str] = []

    if not manifest_path:
        return {}, warnings

    path = Path(manifest_path).expanduser()

    if not path.exists():
        return {}, [
            f"Open-boundary outline manifest does not exist: {path}"
        ]

    if not path.is_file():
        return {}, [
            f"Open-boundary outline manifest is not a file: {path}"
        ]

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except Exception as exc:
        return {}, [
            f"Could not read open-boundary outline manifest "
            f"{path}: {exc}"
        ]

    raw_recommended = (
        data.get("recommended_config")
        or {}
    )

    if not isinstance(
        raw_recommended,
        dict,
    ):
        return {}, [
            f"Open-boundary outline manifest "
            f"recommended_config is not an object: {path}"
        ]

    suggested: dict[str, Any] = {}

    for key in OPEN_BOUNDARY_AUTOFILL_KEYS:
        if key in raw_recommended:
            suggested[key] = raw_recommended[key]

    def resolve_outline_candidate(
        raw_value: Any,
    ) -> Path | None:
        text = str(
            raw_value
            or ""
        ).strip()

        if not text:
            return None

        candidate = Path(
            text
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                path.parent
                / candidate
            ).resolve(
                strict=False
            )
        else:
            candidate = candidate.resolve(
                strict=False
            )

        return candidate

    manifest_outline = resolve_outline_candidate(
        suggested.get(
            "open_boundary_outline_path"
        )
        or data.get(
            "default_open_boundary_outline_path"
        )
        or ""
    )

    detected_outline = resolve_outline_candidate(
        fallback_outline_path
    )

    selected_outline: Path | None = None

    if manifest_outline is not None:
        if manifest_outline.is_file():
            selected_outline = manifest_outline
        else:
            warnings.append(
                "Open-boundary outline path from manifest "
                f"does not exist: {manifest_outline}"
            )

    if (
        selected_outline is None
        and detected_outline is not None
        and detected_outline != manifest_outline
    ):
        if detected_outline.is_file():
            selected_outline = detected_outline

            if manifest_outline is not None:
                warnings.append(
                    "Using the open-boundary outline detected "
                    "directly in the catalog instead: "
                    f"{detected_outline}"
                )
        else:
            warnings.append(
                "Catalog-detected open-boundary outline "
                f"does not exist: {detected_outline}"
            )

    if selected_outline is not None:
        suggested[
            "open_boundary_outline_path"
        ] = str(
            selected_outline
        )
    else:
        # Do not let a stale manifest value override an otherwise valid
        # configuration with a nonexistent path.
        suggested.pop(
            "open_boundary_outline_path",
            None,
        )

    if suggested.get(
        "open_boundary_outline_path"
    ):
        suggested.setdefault(
            "open_boundary_mask_mode",
            "coastal_outline",
        )

        suggested.setdefault(
            "open_boundary_outline_buffer_m",
            150.0,
        )

        suggested.setdefault(
            "open_boundary_min_cells",
            50,
        )

        suggested.setdefault(
            "open_boundary_max_cells",
            500,
        )

        suggested.setdefault(
            "open_boundary_require_edge_adjacency",
            True,
        )

        suggested.setdefault(
            "open_boundary_allow_overwrite_special",
            False,
        )

    return suggested, warnings
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
        "runtime_csv": (
            _catalog_first_top_level_file(root, "event_runtime_window", {".csv"})
            or _catalog_first_match(root, [
                "event_runtime_window/event_runtime_window.csv",
                "event_runtime_window/*runtime*window*.csv",
                "event_runtime_window/*.csv",
            ])
        ),
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
        "active_mask_path": _catalog_active_mask_match(root),
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
        "open_boundary_outline_manifest_path": _catalog_first_match(root, [
            "open_boundary_outlines/open_boundary_outline_manifest.json",
        ]),
        "open_boundary_outline_path": _catalog_first_match(root, [
            "open_boundary_outlines/harris_manual_open_boundary_reviewed*.gpkg",
            "open_boundary_outlines/*.gpkg",
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
        "wind_path": (
            _catalog_first_top_level_file(root, "event_wind", {".nc", ".zarr"}, allow_dirs=True)
            or _catalog_first_match(root, [
                "event_wind/*.nc",
                "event_wind/*.zarr",
                "wind/*.nc",
                "wind/*.zarr",
            ])
        ),
        "pressure_path": (
            _catalog_first_top_level_file(root, "event_pressure", {".nc", ".zarr"}, allow_dirs=True)
            or _catalog_first_match(root, [
                "event_pressure/*.nc",
                "event_pressure/*.zarr",
                "pressure/*.nc",
                "pressure/*.zarr",
            ])
        ),
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
            "event_validation_points/*.xy",
            "event_validation_points/profiles/lite/*.xy",
            "event_validation_points/profiles/lite/*.csv",
            "obs_points/lite/*.xy",
            "obs_points/*.xy",
        ]),
        "obs_points_validation_path": (
            _catalog_first_top_level_file(root, "event_validation_points")
            or _catalog_first_match(root, [
                "event_validation_points/*.csv",
                "event_validation_points/*.xy",
                "event_validation_points/profiles/validation/*.xy",
                "event_validation_points/profiles/validation/*.csv",
            ])
        ),
        "obs_points_full_candidates_path": _catalog_first_match(root, [
            "event_validation_points/profiles/full_candidates/*.xy",
            "event_validation_points/profiles/full_candidates/*.csv",
        ]),
        "obs_lines_reviewed_plus_path": (
            _catalog_first_top_level_file(root, "event_validation_lines")
            or _catalog_first_match(root, [
                "event_validation_lines/*.csv",
                "event_validation_lines/*.crs",
                "event_validation_lines/*REVIEWED_PLUS_AUTO_CUSTOM*.crs",
                "event_validation_lines/reviewed_crs_lines/*REVIEWED_PLUS_AUTO_CUSTOM*.crs",
                "event_validation_lines/reviewed_crs_lines/*REVIEWED_PLUS_AUTO_CUSTOM*.xyxy",
            ])
        ),
        "obs_lines_reviewed_path": (
            _catalog_first_top_level_file(root, "event_validation_lines")
            or _catalog_first_match(root, [
                "event_validation_lines/*.csv",
                "event_validation_lines/*.crs",
                "event_validation_lines/reviewed_crs_lines/*REVIEWED*.crs",
                "event_validation_lines/reviewed_crs_lines/*REVIEWED*.xyxy",
                "obs_lines/*.crs",
                "obs_lines/*.xyxy",
            ])
        ),
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
        or found["wind_path"]
        or found["pressure_path"]
        or found["waterlevel_path"]
        or found["discharge_timeseries_csv_path"]
    ):
        roles.append("event")

    if (
        found["region_path"]
        or found["dem_path"]
        or found["active_mask_path"]
        or found["landcover_path"]
        or found["open_boundary_outline_manifest_path"]
        or found["open_boundary_outline_path"]
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

def _read_runtime_window_values(path_text: str) -> dict[str, str]:
    if not path_text:
        return {}

    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return {}

    import csv

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            row = next(reader, None)
    except Exception:
        return {}

    if not row:
        return {}

    row_l = {str(k).strip().lower(): v for k, v in row.items()}

    def pick(*names: str) -> str:
        for name in names:
            value = row_l.get(name.lower())
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    return {
        "tref": pick("tref", "reference_time", "ref_time"),
        "tstart": pick("tstart", "start_time", "time_start", "event_start"),
        "tstop": pick("tstop", "stop_time", "time_stop", "event_stop", "end_time"),
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
        dem_zmin = float(suggested_config.get("dem_zmin", -50.0) or -50.0)
        suggested_config["dem_zmin"] = dem_zmin
        suggested_config["hydromt_dem_sources"] = [
            {
                "elevation": dem_path,
                "zmin": dem_zmin,
            }
        ]

        # The HCFCD_DEM_5m_UTM topobathy is already the active integrated
        # elevation/topobathy source. Do not also add legacy bathy ingredients by default.
        suggested_config["hydromt_bathy_sources"] = []
        suggested_config["bathy_paths"] = []


    open_boundary_manifest_path = choose_found(
        "open_boundary_outline_manifest_path"
    )

    detected_open_boundary_outline_path = choose_found(
        "open_boundary_outline_path"
    )

    if open_boundary_manifest_path:
        (
            open_boundary_suggestions,
            open_boundary_warnings,
        ) = _read_open_boundary_outline_manifest(
            open_boundary_manifest_path,
            fallback_outline_path=(
                detected_open_boundary_outline_path
            ),
        )

        suggested_config.update(
            open_boundary_suggestions
        )

        warnings.extend(
            open_boundary_warnings
        )

    elif detected_open_boundary_outline_path:
        suggested_config[
            "open_boundary_mask_mode"
        ] = "coastal_outline"

        suggested_config[
            "open_boundary_outline_path"
        ] = detected_open_boundary_outline_path

        suggested_config[
            "open_boundary_outline_buffer_m"
        ] = 150.0

        suggested_config[
            "open_boundary_min_cells"
        ] = 50

        suggested_config[
            "open_boundary_max_cells"
        ] = 500

        suggested_config[
            "open_boundary_require_edge_adjacency"
        ] = True

        suggested_config[
            "open_boundary_allow_overwrite_special"
        ] = False

    active_mask_path = choose_found("active_mask_path")
    if active_mask_path:
        # Manual Mode uses active_mask_path, not the old mask_template_path keys.
        # This raster is sampled onto the already-created HydroMT grid; it does
        # not define x0/y0/mmax/nmax/dx/dy and does not make Manual a native run.
        suggested_config["active_mask_path"] = active_mask_path
        suggested_config["active_mask_mode"] = "sample_to_grid"
        
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

    wind_path = choose_found("wind_path")
    if wind_path:
        suggested_config["use_wind"] = True
        suggested_config["wind_path"] = wind_path
        suggested_config["wind_source"] = "local_file"

    pressure_path = choose_found("pressure_path")
    if pressure_path:
        suggested_config["use_pressure"] = True
        suggested_config["pressure_path"] = pressure_path
        suggested_config["pressure_source"] = "local_file"

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
        candidate_text = (
            _catalog_first_top_level_file(catalog_path, "event_runtime_window", {".csv"})
            or _catalog_first_match(catalog_path, [
                "event_runtime_window/event_runtime_window.csv",
                "event_runtime_window/*runtime*window*.csv",
                "event_runtime_window/*.csv",
            ])
        )

        if candidate_text:
            runtime_path = Path(candidate_text)
            event_catalog = catalog_path
            break

    if runtime_path is None:
        audit.update({
            "status": "major_warning",
            "severity": "major",
            "ui_color": "red",
            "category": "runtime_window_unverified",
            "message": "Could not verify the runtime window because no selected catalog contains a top-level event_runtime_window CSV.",
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

@app.route("/api/review/animation/info", methods=["GET"])
def api_review_animation_info():
    from flask import request, jsonify
    from pathlib import Path
    import json
    import subprocess

    try:
        run_root = _review_maps_safe_run_root(request.args.get("run", ""))

        hours_per_frame = float(request.args.get("hours_per_frame", 6.0))
        fps = float(request.args.get("fps", 10.0))

        if hours_per_frame <= 0:
            return jsonify({"ok": False, "error": "hours_per_frame must be > 0"}), 400
        if fps <= 0:
            return jsonify({"ok": False, "error": "fps must be > 0"}), 400

        py = configured_runner_python_path()
        script = configured_project_script_path("review_animation_info.py")

        proc = subprocess.run(
            [
                str(py),
                str(script),
                str(run_root),
                "--hours-per-frame",
                str(hours_per_frame),
                "--fps",
                str(fps),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
            check=False,
        )

        if proc.returncode != 0:
            return jsonify({
                "ok": False,
                "error": proc.stderr.strip() or proc.stdout.strip() or "Animation info script failed.",
            }), 500

        return jsonify(json.loads(proc.stdout))

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

@app.route("/api/review/obs-gauges/status", methods=["GET"])
def api_review_obs_gauges_status():
    from flask import request, jsonify
    from pathlib import Path
    import json
    import subprocess

    def read_json(path):
        try:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"state": "error", "error": f"{type(exc).__name__}: {exc}"}

    try:
        run_root = _review_maps_safe_run_root(request.args.get("run", ""))
        obs_dir = run_root / "review" / "obs_gauges"
        job_dir = run_root / "review" / "jobs"

        status_path = obs_dir / "obs_gauges_status.json"
        manifest_path = obs_dir / "obs_gauges_manifest.json"
        metrics_path = obs_dir / "obs_gauges_metrics.json"

        status = read_json(status_path) or {
            "state": "missing",
            "message": "No obs/gauge validation products have been generated for this run yet.",
        }

        job_id = status.get("job_id") if isinstance(status, dict) else None
        state_text = str(status.get("state", "")).lower() if isinstance(status, dict) else ""

        if job_id and state_text in {"submitting", "submitted", "pending", "queued", "running"}:
            try:
                proc = subprocess.run(
                    ["squeue", "-h", "-j", str(job_id), "-o", "%T|%M|%R"],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    parts = proc.stdout.strip().split("|", 2)
                    scheduler_state = parts[0] if len(parts) > 0 else ""
                    scheduler_elapsed = parts[1] if len(parts) > 1 else ""
                    scheduler_reason = parts[2] if len(parts) > 2 else ""
                    status["scheduler_state"] = scheduler_state
                    status["scheduler_elapsed"] = scheduler_elapsed
                    status["scheduler_reason"] = scheduler_reason
                    if scheduler_state == "RUNNING":
                        status["state"] = "running"
                        status["message"] = "Obs/gauge validation job is running."
                    elif scheduler_state in {"PENDING", "CONFIGURING"}:
                        status["state"] = "submitted"
                        status["message"] = f"Obs/gauge job is waiting: {scheduler_reason or scheduler_state}."
                else:
                    status["scheduler_state"] = "not_in_squeue"
                    if manifest_path.exists() and metrics_path.exists():
                        status["state"] = "ready"
                        status["message"] = "Obs/gauge validation job finished and saved metrics."
                    else:
                        err_files = sorted(job_dir.glob("review_obs_gauges_*.err")) if job_dir.exists() else []
                        out_files = sorted(job_dir.glob("review_obs_gauges_*.out")) if job_dir.exists() else []
                        latest_err = err_files[-1] if err_files else None
                        latest_out = out_files[-1] if out_files else None
                        err_tail = latest_err.read_text(encoding="utf-8", errors="replace")[-4000:] if latest_err and latest_err.exists() else ""
                        out_tail = latest_out.read_text(encoding="utf-8", errors="replace")[-4000:] if latest_out and latest_out.exists() else ""
                        status["state"] = "failed"
                        status["message"] = "Obs/gauge job left Slurm without producing metrics."
                        status["error"] = err_tail.strip() or out_tail.strip() or "No metrics/manifest or job error text was found."
                        status["stdout_relpath_checked"] = str(latest_out.resolve().relative_to(run_root.resolve())) if latest_out else None
                        status["stderr_relpath_checked"] = str(latest_err.resolve().relative_to(run_root.resolve())) if latest_err else None
            except Exception as exc:
                status["scheduler_check_error"] = f"{type(exc).__name__}: {exc}"

        manifest = read_json(manifest_path)
        metrics = read_json(metrics_path)

        return jsonify({
            "ok": True,
            "run": run_root.name,
            "status": status,
            "manifest": manifest,
            "metrics": metrics,
            "has_manifest": manifest is not None,
            "has_metrics": metrics is not None,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/review/obs-gauges/submit", methods=["POST"])
def api_review_obs_gauges_submit():
    from flask import request, jsonify
    from pathlib import Path
    import json
    import subprocess
    import sys

    try:
        payload = request.get_json(silent=True) or {}
        run_root = _review_maps_safe_run_root(payload.get("run", ""))
        validation_csv = str(payload.get("validation_csv", "") or "").strip()
        direct = bool(payload.get("direct", False))

        script = configured_project_script_path("review_submit_obs_gauges.py")
        cmd = [str(configured_runner_python_path()), str(script), str(run_root), "--force"]
        if validation_csv:
            cmd += ["--validation-csv", validation_csv]

        if direct:
            cmd += ["--direct"]

        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1000 if direct else 60,
            check=False,
        )
        if proc.returncode != 0:
            return jsonify({
                "ok": False,
                "error": proc.stderr.strip() or proc.stdout.strip() or "Obs/gauge submit script failed.",
            }), 500

        try:
            data = json.loads(proc.stdout)
        except Exception:
            data = {"ok": True, "stdout": proc.stdout, "stderr": proc.stderr}
        return jsonify(data)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/review/animation/status", methods=["GET"])
def api_review_animation_status():
    from flask import request, jsonify
    from pathlib import Path
    import json
    import subprocess

    def read_json(path):
        try:
            if not path.exists():
                return {}
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"state": "error", "error": f"{type(exc).__name__}: {exc}"}

    try:
        run_root = _review_maps_safe_run_root(request.args.get("run", ""))
        anim_dir = run_root / "review" / "animations"
        status_path = anim_dir / "animation_status.json"

        status = read_json(status_path)
        if not status:
            status = {
                "state": "missing",
                "message": "No Review animation has been generated for this run yet.",
            }
            


        job_id = status.get("job_id") if isinstance(status, dict) else None
        status_state = str(status.get("state", "")).lower() if isinstance(status, dict) else ""

        if job_id and status_state in {"submitting", "submitted", "pending", "running"}:
            try:
                proc = subprocess.run(
                    ["squeue", "-h", "-j", str(job_id), "-o", "%T|%M|%R"],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                )

                if proc.returncode == 0 and proc.stdout.strip():
                    parts = proc.stdout.strip().split("|", 2)
                    scheduler_state = parts[0] if len(parts) > 0 else ""
                    scheduler_elapsed = parts[1] if len(parts) > 1 else ""
                    scheduler_reason = parts[2] if len(parts) > 2 else ""

                    status["scheduler_state"] = scheduler_state
                    status["scheduler_elapsed"] = scheduler_elapsed
                    status["scheduler_reason"] = scheduler_reason

                    if scheduler_state == "RUNNING" and status_state in {"submitted", "pending"}:
                        status["state"] = "running"
                        status["message"] = "Slurm job is running."
                    elif scheduler_state in {"PENDING", "CONFIGURING"}:
                        status["state"] = "submitted"
                        status["message"] = f"Slurm job is waiting: {scheduler_reason or scheduler_state}."
                else:
                    status["scheduler_state"] = "not_in_squeue"

                    # If Slurm no longer knows the job and the status file still says
                    # submitted/running, the builder either finished without updating status,
                    # or crashed before it could write failed/ready. Surface that instead of
                    # leaving the UI stuck at "waiting for scheduler".
                    anim_dir = run_root / "review" / "animations"
                    job_dir = run_root / "review" / "jobs"

                    metas = sorted(anim_dir.glob("animation_depth_*.json")) if anim_dir.exists() else []
                    videos = sorted(anim_dir.glob("animation_depth_*.mp4")) if anim_dir.exists() else []

                    if metas and videos:
                        status["state"] = "ready"
                        status["message"] = "Animation job finished and saved a video."
                    else:
                        latest_err = None
                        latest_out = None

                        err_files = sorted(job_dir.glob("review_animation_*.err")) if job_dir.exists() else []
                        out_files = sorted(job_dir.glob("review_animation_*.out")) if job_dir.exists() else []

                        if err_files:
                            latest_err = err_files[-1]
                        if out_files:
                            latest_out = out_files[-1]

                        err_tail = ""
                        out_tail = ""

                        try:
                            if latest_err and latest_err.exists():
                                err_tail = latest_err.read_text(encoding="utf-8", errors="replace")[-4000:]
                        except Exception:
                            err_tail = ""

                        try:
                            if latest_out and latest_out.exists():
                                out_tail = latest_out.read_text(encoding="utf-8", errors="replace")[-4000:]
                        except Exception:
                            out_tail = ""

                        status["state"] = "failed"
                        status["message"] = "Animation job left Slurm without producing an MP4."
                        status["error"] = err_tail.strip() or out_tail.strip() or "No MP4 or metadata file was found."
                        status["stdout_relpath_checked"] = str(latest_out.resolve().relative_to(run_root.resolve())) if latest_out else None
                        status["stderr_relpath_checked"] = str(latest_err.resolve().relative_to(run_root.resolve())) if latest_err else None
            except Exception as exc:
                status["scheduler_check_error"] = f"{type(exc).__name__}: {exc}"




        animations = []
        if anim_dir.exists():
            for meta_path in sorted(anim_dir.glob("animation_depth_*.json")):
                meta = read_json(meta_path)
                rel = meta.get("output_relpath")
                if not rel:
                    continue

                video_path = run_root / rel
                if not video_path.exists():
                    continue

                animations.append({
                    "metadata_relpath": str(meta_path.resolve().relative_to(run_root.resolve())),
                    "output_relpath": rel,
                    "created_at": meta.get("created_at"),
                    "hours_per_frame": meta.get("hours_per_frame"),
                    "fps": meta.get("fps"),
                    "frame_count": meta.get("frame_count"),
                    "video_seconds": meta.get("video_seconds"),
                    "first_time_label": meta.get("first_time_label"),
                    "last_time_label": meta.get("last_time_label"),
                    "size_bytes": video_path.stat().st_size,
                })

        animations.sort(key=lambda x: str(x.get("created_at") or ""))

        return jsonify({
            "ok": True,
            "run": run_root.name,
            "status": status,
            "animations": animations,
            "latest_animation": animations[-1] if animations else None,
        })

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/review/animation/video", methods=["GET"])
def api_review_animation_video():
    from flask import request, send_file, abort

    try:
        run_root = _review_maps_safe_run_root(request.args.get("run", ""))
        rel = request.args.get("path", "")

        if not rel:
            abort(400)

        video_path = (run_root / rel).resolve()
        run_resolved = run_root.resolve()

        if video_path != run_resolved and run_resolved not in video_path.parents:
            abort(403)

        suffix = video_path.suffix.lower()
        if suffix not in {".mp4", ".webm"}:
            abort(400)
        
        mimetype = "video/webm" if suffix == ".webm" else "video/mp4"

        if not video_path.exists():
            abort(404)

        return send_file(
            video_path,
            mimetype=mimetype,
            as_attachment=False,
            conditional=True,
            max_age=0,
        )

    except Exception:
        abort(404)

@app.route("/api/review/animation/submit", methods=["POST"])
def api_review_animation_submit():
    from flask import request, jsonify
    from pathlib import Path
    import json
    import subprocess
    import sys

    try:
        payload = request.get_json(silent=True) or {}
        run_root = _review_maps_safe_run_root(payload.get("run", ""))

        hours_per_frame = float(payload.get("hours_per_frame", 6.0))
        fps = float(payload.get("fps", 10.0))

        if hours_per_frame <= 0:
            return jsonify({"ok": False, "error": "hours_per_frame must be > 0"}), 400
        if fps <= 0:
            return jsonify({"ok": False, "error": "fps must be > 0"}), 400
        if fps > 30:
            return jsonify({"ok": False, "error": "fps should be <= 30 for Review animations."}), 400

        script = configured_project_script_path("review_submit_animation.py")

        proc = subprocess.run(
            [
                str(configured_runner_python_path()),
                str(script),
                str(run_root),
                "--hours-per-frame",
                str(hours_per_frame),
                "--fps",
                str(fps),
                "--force",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )

        if proc.returncode != 0:
            return jsonify({
                "ok": False,
                "error": proc.stderr.strip() or proc.stdout.strip() or "Animation submit script failed.",
            }), 500

        return jsonify(json.loads(proc.stdout))

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

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



def effective_allowed_roots() -> list[Path]:
    """
    Return static safe roots plus Settings-configured roots.

    The Settings menu controls:
      - browseAllowedRoots for broad browse roots
      - each individual path default such as dataRoot, runRoot, condaPython, etc.

    This keeps machine-specific filesystem paths out of app.py.
    """
    roots: list[Path] = list(ALLOWED_ROOTS)

    try:
        defaults = _read_launcher_site_defaults()
    except Exception:
        defaults = {}

    # Broad explicit browse roots from the Settings menu.
    roots.extend(split_launcher_path_list(defaults.get("browseAllowedRoots")))

    # Specific path defaults also become allowed roots, so Browse and backend
    # validation can follow the configured launcher paths.
    for key in LAUNCHER_DEFAULT_KEYS:
        if key == "browseAllowedRoots":
            continue

        root = launcher_default_path_root(key)

        if root is not None:
            roots.append(root)

    unique: list[Path] = []
    seen: set[str] = set()

    for root in roots:
        try:
            text = str(Path(root).expanduser().resolve(strict=False))
        except Exception:
            text = str(root)

        if not text or text in seen:
            continue

        seen.add(text)
        unique.append(Path(text))

    return unique

def is_allowed_path(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    allowed_resolved = [root.resolve(strict=False) for root in effective_allowed_roots()]
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

    allowed_roots = effective_allowed_roots()
    allowed_resolved = [root.resolve(strict=False) for root in allowed_roots]

    if not any(resolved == root or root in resolved.parents for root in allowed_resolved):
        allowed_text = ", ".join(str(root) for root in allowed_roots)
        raise ValueError(f"Path is outside allowed roots: {allowed_text}")

    return resolved

def configured_project_root_path() -> Path:
    """
    Project/pipeline root comes from Launcher Settings projectRoot.

    There is intentionally no hardcoded filesystem fallback here.
    """
    value = launcher_default_value("projectRoot")

    if not value:
        raise ValueError(
            "Project root is not configured. Set projectRoot in the launcher Settings menu."
        )

    return safe_resolve(value)


def configured_run_root_path() -> Path:
    """
    Run/output root comes from Launcher Settings runRoot.

    There is intentionally no hardcoded filesystem fallback here.
    """
    value = launcher_default_value("runRoot")

    if not value:
        raise ValueError(
            "Run root is not configured. Set runRoot in the launcher Settings menu."
        )

    return safe_resolve(value)


def configured_project_script_path(script_name: str) -> Path:
    """
    Resolve a backend script under Settings projectRoot/code.
    """
    clean_name = Path(str(script_name)).name

    if not clean_name:
        raise ValueError("Script name is blank.")

    script = (configured_project_root_path() / "code" / clean_name).resolve()

    project_root = configured_project_root_path().resolve()
    try:
        script.relative_to(project_root)
    except ValueError:
        raise ValueError(f"Script escaped project root: {script}")

    if not script.exists():
        raise FileNotFoundError(f"Backend script does not exist: {script}")

    return script


def configured_runner_python_path() -> Path:
    """
    Backend runner Python comes from:
      1. SFINCS_RUNNER_PYTHON environment override, if set
      2. Settings menu condaPython value

    There is intentionally no hardcoded filesystem fallback here.
    """
    value = RUNNER_PYTHON_ENV or launcher_default_value("condaPython")

    if not value:
        raise ValueError(
            "Backend Python is not configured. Set condaPython in the launcher Settings menu."
        )

    return safe_resolve(value)


def configured_contextily_python_path() -> Path:
    """
    Review static-map Python comes from:
      1. Settings menu contextilyPython value, if set
      2. Settings menu condaPython value

    There is intentionally no hardcoded filesystem fallback here.
    """
    value = launcher_default_value("contextilyPython") or launcher_default_value("condaPython")

    if not value:
        raise ValueError(
            "Review/map Python is not configured. Set contextilyPython or condaPython in the launcher Settings menu."
        )

    return safe_resolve(value)


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

    runner_python_path = configured_runner_python_path()
    if not runner_python_path.exists():
        raise FileNotFoundError(f"Runner Python does not exist: {configured_runner_python_path()}")

    runner_script = configured_project_script_path("pipeline_runner.py")
    project_root = configured_project_root_path()

    cmd = [
        str(runner_python_path),
        str(runner_script),
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
        cwd=str(project_root),
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
        "cwd": str(project_root),
        "config_path": str(config_path),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }

def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_staged_geometry_check_config(cfg: dict[str, Any], flavor: str) -> dict[str, Any]:
    """
    Stage a Manual geometry-check config under launcher-owned folders.

    Important: do not write this into run_root/geometry_check because that would
    make inspect_run_root() think a real run artifact already exists and could
    block build/submit for overwrite_existing_run=false.
    """
    if not isinstance(cfg, dict):
        raise ValueError("Request must contain a JSON object named config.")

    if not cfg:
        raise ValueError("Config payload is empty. The page did not send getConfig() output.")

    if "run_name" not in cfg:
        raise ValueError("Config payload is missing run_name. The page likely sent an incomplete config.")

    run_name = safe_run_name(str(cfg.get("run_name", "")).strip())
    output_root = safe_resolve(str(cfg.get("output_root", "")).strip())

    cfg = dict(cfg)
    cfg["pipeline_mode"] = "preflight_only"

    run_root = output_root / run_name
    launcher_config_root = output_root / "_launcher_configs"
    geometry_root = output_root / "_launcher_logs" / run_name / "geometry_check"

    launcher_config_root.mkdir(parents=True, exist_ok=True)
    geometry_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    config_path = launcher_config_root / f"{run_name}_{stamp}_geometry_check_{flavor}.json"
    audit_path = geometry_root / f"{stamp}_manual_geometry_check_audit.json"
    stdout_log = geometry_root / f"{stamp}_manual_geometry_check_{flavor}.out"
    stderr_log = geometry_root / f"{stamp}_manual_geometry_check_{flavor}.err"
    sbatch_path = geometry_root / f"{stamp}_manual_geometry_check.sbatch"
    status_path = geometry_root / f"{stamp}_manual_geometry_check_status.json"

    config_path.write_text(
        json.dumps(cfg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "run_name": run_name,
        "run_root": run_root,
        "geometry_root": geometry_root,
        "config_path": config_path,
        "audit_path": audit_path,
        "stdout_log": stdout_log,
        "stderr_log": stderr_log,
        "sbatch_path": sbatch_path,
        "status_path": status_path,
    }


def _manual_geometry_check_command(config_path: Path, audit_path: Path) -> list[str]:
    runner_python_path = configured_runner_python_path()

    if not runner_python_path.exists():
        raise FileNotFoundError(f"Runner Python does not exist: {configured_runner_python_path()}")

    geometry_check_script = configured_project_script_path("manual_geometry_check.py")

    return [
        str(runner_python_path),
        str(geometry_check_script),
        "--config",
        str(config_path),
        "--json-out",
        str(audit_path),
    ]


def _geometry_check_optional_sbatch_lines(cfg: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    optional_directives = [
        ("slurm_account", "--account"),
        ("slurm_partition", "--partition"),
        ("slurm_qos", "--qos"),
    ]

    for key, directive in optional_directives:
        value = str(cfg.get(key) or "").strip()
        if value:
            lines.append(f"#SBATCH {directive}={value}")

    email = str(cfg.get("slurm_email") or "").strip()
    if email:
        mail_type = str(cfg.get("slurm_mail_type") or "END,FAIL").strip() or "END,FAIL"
        lines.append(f"#SBATCH --mail-user={email}")
        lines.append(f"#SBATCH --mail-type={mail_type}")

    extra = cfg.get("slurm_extra_directives") or []
    if isinstance(extra, list):
        for item in extra:
            text = str(item).strip()
            if not text:
                continue
            if text.startswith("#SBATCH"):
                lines.append(text)
            else:
                lines.append(f"#SBATCH {text}")

    return lines


@app.post("/api/manual-geometry-check-local")
def api_manual_geometry_check_local():
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config") or {}

    if not isinstance(cfg, dict):
        return jsonify({
            "ok": False,
            "error": "Request must contain a JSON object named config.",
        }), 400

    try:
        paths = _write_staged_geometry_check_config(cfg, "local")
        cmd = _manual_geometry_check_command(paths["config_path"], paths["audit_path"])
        project_root = configured_project_root_path()

        completed = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=GEOMETRY_CHECK_LOCAL_TIMEOUT_SECONDS,
        )

        paths["stdout_log"].write_text(completed.stdout or "", encoding="utf-8")
        paths["stderr_log"].write_text(completed.stderr or "", encoding="utf-8")

        audit = _read_json_if_exists(paths["audit_path"])

        return jsonify({
            "ok": completed.returncode == 0,
            "mode": "local",
            "returncode": completed.returncode,
            "command": cmd,
            "cwd": str(project_root),
            "config_path": str(paths["config_path"]),
            "audit_path": str(paths["audit_path"]),
            "stdout_log": str(paths["stdout_log"]),
            "stderr_log": str(paths["stderr_log"]),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "audit": audit,
        })

    except subprocess.TimeoutExpired as exc:
        return jsonify({
            "ok": False,
            "mode": "local",
            "error": f"Geometry check timed out after {exc.timeout} seconds.",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }), 504

    except ValueError as exc:
        return jsonify({
            "ok": False,
            "mode": "local",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }), 400

    except Exception as exc:
        return jsonify({
            "ok": False,
            "mode": "local",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }), 500


@app.post("/api/manual-geometry-check-submit")
def api_manual_geometry_check_submit():
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config") or {}

    if not isinstance(cfg, dict):
        return jsonify({
            "ok": False,
            "error": "Request must contain a JSON object named config.",
        }), 400

    try:
        paths = _write_staged_geometry_check_config(cfg, "slurm")
        cmd = _manual_geometry_check_command(paths["config_path"], paths["audit_path"])

        job_name = f"geom_{paths['run_name']}"[:120]
        quoted_cmd = " ".join(shlex.quote(part) for part in cmd)

        sbatch_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --output={paths['stdout_log']}",
            f"#SBATCH --error={paths['stderr_log']}",
            f"#SBATCH --time={GEOMETRY_CHECK_SLURM_TIME}",
            "#SBATCH --nodes=1",
            "#SBATCH --ntasks=1",
            f"#SBATCH --cpus-per-task={GEOMETRY_CHECK_SLURM_CPUS}",
            f"#SBATCH --mem={GEOMETRY_CHECK_SLURM_MEM}",
            *_geometry_check_optional_sbatch_lines(cfg),
            "",
            "set -euo pipefail",
            "",
            "echo \"Manual geometry check started: $(date)\"",
            f"echo \"Config: {paths['config_path']}\"",
            f"echo \"Audit:  {paths['audit_path']}\"",
            f"cd {shlex.quote(str(PIPELINE_ROOT))}",
            quoted_cmd,
            "echo \"Manual geometry check finished: $(date)\"",
            "",
        ]

        paths["sbatch_path"].write_text("\n".join(sbatch_lines), encoding="utf-8")

        submitted = subprocess.run(
            ["sbatch", str(paths["sbatch_path"])],
            cwd=str(PIPELINE_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        job_id = None
        match = re.search(r"Submitted batch job\s+(\d+)", submitted.stdout or "")
        if match:
            job_id = match.group(1)

        status = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "state": "submitted" if submitted.returncode == 0 else "submit_failed",
            "job_id": job_id,
            "returncode": submitted.returncode,
            "stdout": submitted.stdout,
            "stderr": submitted.stderr,
            "config_path": str(paths["config_path"]),
            "audit_path": str(paths["audit_path"]),
            "sbatch_path": str(paths["sbatch_path"]),
            "stdout_log": str(paths["stdout_log"]),
            "stderr_log": str(paths["stderr_log"]),
        }

        paths["status_path"].write_text(
            json.dumps(status, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return jsonify({
            "ok": submitted.returncode == 0,
            "mode": "slurm",
            "job_id": job_id,
            "returncode": submitted.returncode,
            "stdout": submitted.stdout,
            "stderr": submitted.stderr,
            "config_path": str(paths["config_path"]),
            "audit_path": str(paths["audit_path"]),
            "script_path": str(paths["sbatch_path"]),
            "status_path": str(paths["status_path"]),
            "stdout_log": str(paths["stdout_log"]),
            "stderr_log": str(paths["stderr_log"]),
        }), 200 if submitted.returncode == 0 else 500

    except ValueError as exc:
        return jsonify({
            "ok": False,
            "mode": "slurm",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }), 400

    except Exception as exc:
        return jsonify({
            "ok": False,
            "mode": "slurm",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }), 500

def iter_files_limited(source: Path, max_depth: int = MAX_SCAN_DEPTH):
    source = source.resolve(strict=True)

    if not source.is_dir():
        raise ValueError(f"Source is not a directory: {source}")

    count = 0
    base_depth = len(source.parts)

    for root, dirs, files in os.walk(source):
        root_path = Path(root)

        dirs[:] = [
            dirname
            for dirname in dirs
            if dirname.lower() != "_misc"
        ]

        if _catalog_path_is_ignored(root_path):
            continue

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

    if any(part in {"_misc", "_manifests", "_audit_reports", "_inventory_reports"} for part in parts_l):
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

    # Curated Manual validation line inputs are allowed to use TEKAL/SFINCS .crs.
    # This allows files such as:
    #   event_validation_lines/harvey_obs_lines_REVIEWED_PLUS_AUTO_CUSTOM.crs
    # while still treating unselected/native package files like sfincs.crs as native.
    if suffix == ".crs" and "event_validation_lines" in parts_l:
        return None

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
                if _catalog_path_is_ignored(path):
                    continue

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
            for root in effective_allowed_roots():
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
            "allowed_roots": [str(path) for path in effective_allowed_roots()],
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


def compare_manager_path() -> Path:
    return configured_project_script_path("compare_job_manager.py")


def compare_python_path() -> Path:
    return configured_runner_python_path()


def compare_root_path() -> Path:
    return (configured_run_root_path() / "_compare_jobs").resolve()


def compare_run_roots() -> list[Path]:
    return [configured_run_root_path()]


def _json_error(message, status=400, **extra):
    payload = {"status": "error", "message": str(message)}
    payload.update(extra)
    return jsonify(payload), status


def _run_manager(args):
    cmd = [str(compare_python_path()), str(compare_manager_path())] + list(args)

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
        job_dir.relative_to(compare_root_path())
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

        allowed_search_bases = effective_allowed_roots()

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
            search_roots = compare_run_roots()

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

    def safe_path(raw):
        if not raw:
            return None

        return safe_resolve(str(raw))

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


# === REVIEW V1 ROUTES BEGIN ===
# =============================================================================
# REVIEW V1 ROUTES — paste into web_launcher/app.py after app = Flask(...),
# but before the final if __name__ == "__main__" block.
#
# These routes are read-only. They do not modify runs, rebuild models, submit jobs,
# or rerun postprocess. The summary route shells out to code/review_run.py using
# the SFINCS/backend Python so app.py's lighter Flask env does not need xarray/numpy.
# =============================================================================

import json as _review_json
import subprocess as _review_subprocess
from pathlib import Path as _ReviewPath
from flask import abort as _review_abort
from flask import jsonify as _review_jsonify
from flask import request as _review_request
from flask import send_file as _review_send_file


def _review_pipeline_root() -> _ReviewPath:
    return _ReviewPath(__file__).resolve().parents[1]


def _review_web_root() -> _ReviewPath:
    return _ReviewPath(__file__).resolve().parent


def _review_default_run_root() -> _ReviewPath:
    """Review run root comes from Launcher Settings runRoot."""
    return _ReviewPath(configured_run_root_path())


def _review_backend_python() -> str:
    """Use the backend/SFINCS Python from Launcher Settings condaPython."""
    return str(configured_runner_python_path())


def _review_resolve_run(run_name: str) -> _ReviewPath:
    """Resolve a run name safely under the configured run root."""
    if not run_name:
        raise ValueError("blank run name")
    if "/" in run_name or "\\" in run_name or run_name in {".", ".."}:
        raise ValueError("run must be a run folder name, not a path")
    run_root = _review_default_run_root().resolve()
    run_dir = (run_root / run_name).resolve()
    try:
        run_dir.relative_to(run_root)
    except ValueError:
        raise ValueError("resolved run escaped run root")
    return run_dir


def _review_quick_status(run_dir: _ReviewPath) -> str:
    if (run_dir / "preprocess_failed.json").exists() or (run_dir / "sfincs_failed.json").exists() or (run_dir / "postprocess_failed.json").exists():
        return "failed"
    if (run_dir / "model" / "sfincs_map.nc").exists() and (run_dir / "model" / "sfincs_his.nc").exists():
        if (run_dir / "postprocess" / "run_summary.json").exists() or (run_dir / "postprocess" / "output_variables.txt").exists():
            return "completed"
        return "sfincs-completed"
    if (run_dir / "model" / "sfincs.inp").exists():
        return "preprocess-completed"
    scaffold_names = ["run_config.json", "saved_config.json", "launcher_config.json", "scripts", "logs", "model", "postprocess"]
    if any((run_dir / name).exists() for name in scaffold_names):
        return "scaffold-or-partial"
    return "unknown"


@app.route("/review")
def review_page():
    return render_template("review.html")


@app.route("/api/review/runs")
def api_review_runs():
    run_root = _review_default_run_root().resolve()
    if not run_root.exists():
        return _review_jsonify({"ok": False, "error": f"Run root does not exist: {run_root}", "run_root": str(run_root)}), 404

    rows = []
    for p in sorted(run_root.iterdir(), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
        if not p.is_dir():
            continue
        if p.name.startswith(".") or p.name.startswith("_"):
            # Skip diagnostic roots like _compare_jobs and _comparison_reports.
            continue
        try:
            st = p.stat()
            rows.append({
                "name": p.name,
                "path": str(p),
                "status": _review_quick_status(p),
                "mtime": st.st_mtime,
                "mtime_iso": datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
            })
        except Exception as exc:
            rows.append({"name": p.name, "path": str(p), "status": "stat-error", "error": repr(exc)})
    return _review_jsonify({"ok": True, "run_root": str(run_root), "runs": rows})


@app.route("/api/review/summary")
def api_review_summary():
    run_name = _review_request.args.get("run", "").strip()
    try:
        run_dir = _review_resolve_run(run_name)
    except ValueError as exc:
        return _review_jsonify({"ok": False, "error": str(exc)}), 400
    if not run_dir.exists():
        return _review_jsonify({"ok": False, "error": f"Run folder does not exist: {run_dir}"}), 404

    script = _review_pipeline_root() / "code" / "review_run.py"
    if not script.exists():
        return _review_jsonify({"ok": False, "error": f"Missing review script: {script}"}), 500

    cmd = [_review_backend_python(), str(script), str(run_dir)]
    proc = _review_subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    if proc.returncode != 0:
        return _review_jsonify({
            "ok": False,
            "error": "review_run.py failed",
            "returncode": proc.returncode,
            "cmd": cmd,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }), 500
    try:
        review = _review_json.loads(proc.stdout)
    except Exception as exc:
        return _review_jsonify({
            "ok": False,
            "error": f"review_run.py did not return JSON: {exc!r}",
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }), 500
    return _review_jsonify({"ok": True, "review": review})


@app.route("/api/review/file")
def api_review_file():
    """Serve an artifact file from a selected run folder, safely by relative path."""
    run_name = _review_request.args.get("run", "").strip()
    rel = _review_request.args.get("rel", "").strip()
    if not rel:
        return _review_jsonify({"ok": False, "error": "blank rel path"}), 400
    try:
        run_dir = _review_resolve_run(run_name)
    except ValueError as exc:
        return _review_jsonify({"ok": False, "error": str(exc)}), 400

    target = (run_dir / rel).resolve()
    try:
        target.relative_to(run_dir.resolve())
    except ValueError:
        _review_abort(403)
    if not target.exists() or not target.is_file():
        _review_abort(404)
    return _review_send_file(target)


# Future placeholders. Keep these read-only; wire them after V1 summary is verified.
@app.route("/api/review/timeseries")
def api_review_timeseries_placeholder():
    return _review_jsonify({
        "ok": False,
        "implemented": False,
        "message": "Timeseries graph API is planned for Review V2 after V1 run summary is verified.",
    }), 501


@app.route("/api/review/animation")
def api_review_animation_placeholder():
    return _review_jsonify({
        "ok": False,
        "implemented": False,
        "message": "Animation API is planned for Review V3 after cached map layers are implemented.",
    }), 501





# === REVIEW MAP API V1 BEGIN ===
def _review_maps_enrich_scheduler_status(run_root, status):
    import json
    import subprocess

    if not isinstance(status, dict):
        return status

    job_id = status.get("job_id")
    status_state = str(status.get("state", "")).lower()

    if not job_id or status_state not in {"submitting", "submitted", "pending", "queued", "running"}:
        return status

    try:
        proc = subprocess.run(
            ["squeue", "-h", "-j", str(job_id), "-o", "%T|%M|%R"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )

        if proc.returncode == 0 and proc.stdout.strip():
            parts = proc.stdout.strip().split("|", 2)
            scheduler_state = parts[0] if len(parts) > 0 else ""
            scheduler_elapsed = parts[1] if len(parts) > 1 else ""
            scheduler_reason = parts[2] if len(parts) > 2 else ""

            status["scheduler_state"] = scheduler_state
            status["scheduler_elapsed"] = scheduler_elapsed
            status["scheduler_reason"] = scheduler_reason

            if scheduler_state == "RUNNING":
                status["state"] = "running"
                status["message"] = "Slurm job is running. Static map products are being built."
            elif scheduler_state in {"PENDING", "CONFIGURING"}:
                status["state"] = "submitted"
                status["message"] = f"Slurm job is waiting: {scheduler_reason or scheduler_state}."

            return status

        # If Slurm no longer knows the job, inspect Review map outputs/logs.
        status["scheduler_state"] = "not_in_squeue"

        maps_dir = run_root / "review" / "maps"
        job_dir = run_root / "review" / "jobs"
        manifest_path = maps_dir / "layers_manifest.json"

        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                layers = manifest.get("layers") if isinstance(manifest, dict) else None
                if isinstance(layers, list) and layers:
                    status["state"] = "ready"
                    status["message"] = "Static map job finished and saved layer products."
                    status["manifest"] = str(manifest_path.resolve().relative_to(run_root.resolve()))
                    status["layer_ids"] = [x.get("layer_id") for x in layers if isinstance(x, dict)]
                    return status
            except Exception as exc:
                status["manifest_read_error"] = f"{type(exc).__name__}: {exc}"

        err_files = sorted(job_dir.glob("review_maps_*.err")) if job_dir.exists() else []
        out_files = sorted(job_dir.glob("review_maps_*.out")) if job_dir.exists() else []

        latest_err = err_files[-1] if err_files else None
        latest_out = out_files[-1] if out_files else None

        err_tail = ""
        out_tail = ""

        try:
            if latest_err and latest_err.exists():
                err_tail = latest_err.read_text(encoding="utf-8", errors="replace")[-4000:]
        except Exception:
            err_tail = ""

        try:
            if latest_out and latest_out.exists():
                out_tail = latest_out.read_text(encoding="utf-8", errors="replace")[-4000:]
        except Exception:
            out_tail = ""

        status["state"] = "failed"
        status["message"] = "Static map job left Slurm without producing a usable layer manifest."
        status["error"] = err_tail.strip() or out_tail.strip() or "No layers_manifest.json or map output error text was found."
        status["stdout_relpath_checked"] = str(latest_out.resolve().relative_to(run_root.resolve())) if latest_out else None
        status["stderr_relpath_checked"] = str(latest_err.resolve().relative_to(run_root.resolve())) if latest_err else None

        return status

    except Exception as exc:
        status["scheduler_check_error"] = f"{type(exc).__name__}: {exc}"
        return status
    
    
    
    
def _review_maps_safe_run_root(run_name):
    from pathlib import Path

    runs_root = configured_run_root_path().resolve()
    safe_name = Path(str(run_name or "")).name

    if not safe_name:
        raise ValueError("Missing run name.")

    run_root = (runs_root / safe_name).resolve()

    if run_root == runs_root or runs_root not in run_root.parents:
        raise ValueError("Unsafe run path.")

    if not run_root.exists():
        raise FileNotFoundError(f"Run folder not found: {safe_name}")

    return run_root


def _review_maps_read_json(path):
    import json

    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


@app.route("/api/review/maps/status", methods=["GET"])
def api_review_maps_status():
    from flask import request, jsonify

    try:
        run_root = _review_maps_safe_run_root(request.args.get("run", ""))

        status_path = run_root / "review" / "maps" / "map_status.json"
        manifest_path = run_root / "review" / "maps" / "layers_manifest.json"

        status = _review_maps_read_json(status_path)
        manifest = _review_maps_read_json(manifest_path)

        if status is None:
            status = {
                "state": "missing",
                "message": "No Review map cache has been generated for this run yet.",
            }
            
        status = _review_maps_enrich_scheduler_status(run_root, status)
        
        return jsonify({
            "ok": True,
            "run": run_root.name,
            "status": status,
            "manifest": manifest,
            "has_manifest": manifest is not None,
        })

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


@app.route("/api/review/maps/submit", methods=["POST"])
def api_review_maps_submit():
    from flask import request, jsonify
    from pathlib import Path
    from datetime import datetime, timezone
    import json
    import subprocess
    import sys

    try:
        payload = request.get_json(silent=True) or {}
        run_name = payload.get("run") or request.form.get("run") or request.args.get("run")
        force = bool(payload.get("force", False))
        direct = bool(payload.get("direct", False))

        run_root = _review_maps_safe_run_root(run_name)

        if direct:
            maps_dir = run_root / "review" / "maps"
            status_path = maps_dir / "map_status.json"
            manifest_path = maps_dir / "layers_manifest.json"
            maps_dir.mkdir(parents=True, exist_ok=True)

            status_path.write_text(json.dumps({
                "state": "running_direct",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "message": "Running static map builder locally in the web app session.",
            }, indent=2) + "\n", encoding="utf-8")

            py = configured_contextily_python_path()
            if not py.exists():
                py = Path(sys.executable)

            builder = configured_project_script_path("review_prepare_maps.py")
            cmd = [str(py), str(builder), str(run_root)]

            if force:
                cmd.append("--force")

            proc = subprocess.run(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=1200,
            )

            if proc.returncode != 0:
                status = {
                    "state": "failed",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "message": "Local static map builder failed.",
                    "error": (proc.stderr or proc.stdout)[-3000:],
                    "stdout_tail": proc.stdout[-3000:],
                    "stderr_tail": proc.stderr[-3000:],
                }
                status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
                return jsonify({"ok": False, "run": run_root.name, "status": status}), 500

            status = {
                "state": "ready",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "message": "Local static map products are ready.",
                "manifest": str(manifest_path),
                "stdout_tail": proc.stdout[-3000:],
                "stderr_tail": proc.stderr[-3000:],
            }
            status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

            manifest = _review_maps_read_json(manifest_path)

            return jsonify({
                "ok": True,
                "run": run_root.name,
                "status": status,
                "manifest": manifest,
                "has_manifest": manifest is not None,
            })

        py = configured_contextily_python_path()
        script = configured_project_script_path("review_submit_maps.py")

        cmd = [str(py), str(script), str(run_root)]

        if force:
            cmd.append("--force")

        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=45,
            check=False,
        )

        status_path = run_root / "review" / "maps" / "map_status.json"
        status = _review_maps_read_json(status_path)

        return jsonify({
            "ok": result.returncode == 0,
            "run": run_root.name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status": status,
        }), 200 if result.returncode == 0 else 500

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500
# === REVIEW MAP API V1 END ===





# =============================================================================
# END REVIEW V1 ROUTES
# =============================================================================
# === REVIEW V1 ROUTES END ===

if __name__ == "__main__":
    host = os.environ.get("WEB_LAUNCHER_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_LAUNCHER_PORT", "5000"))

    print(f"Starting SFINCS Web Launcher on http://{host}:{port}")
    print(f"App directory: {APP_DIR}")
    print("Allowed roots:")
    for root in ALLOWED_ROOTS:
        print(f"  - {root}")

    app.run(host=host, port=port, debug=True)