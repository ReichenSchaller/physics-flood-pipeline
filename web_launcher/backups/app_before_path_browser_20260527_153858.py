#!/usr/bin/env python3
"""
SFINCS Web Launcher - Flask wrapper

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

from flask import Flask, jsonify, render_template, request


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
# Helper functions
# ---------------------------------------------------------------------

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

    return {
        "ok": True,
        "source_path": str(source),
        "recognized": recognized,
        "file_count": sum(len(v) for v in files_by_name.values()),
        "recognized_count": sum(1 for item in recognized.values() if item["found"]),
    }


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
    source_path = payload.get("source_path", "")

    try:
        source = safe_resolve(source_path)
        result = detect_sfincs_files(source)
    except Exception as exc:
        return json_error(str(exc), 400)

    return jsonify(result)


@app.post("/api/save-config")
def api_save_config():
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config")

    if not isinstance(cfg, dict):
        return json_error("Request must contain a JSON object named 'config'.")

    try:
        run_name = safe_run_name(str(cfg.get("run_name", "")))
        output_root = safe_resolve(str(cfg.get("output_root", "")))
        run_root = output_root / run_name
        run_root = safe_resolve(str(run_root))

        overwrite = bool(cfg.get("overwrite_existing_run", False))
        config_path = run_root / "run_config.json"

        if run_root.exists() and not overwrite and config_path.exists():
            return json_error(
                "run_config.json already exists and overwrite_existing_run is false.",
                409,
                run_root=str(run_root),
                config_path=str(config_path),
            )

        run_root.mkdir(parents=True, exist_ok=True)

        with config_path.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
            f.write("\n")

    except Exception as exc:
        return json_error(str(exc), 400)

    return jsonify(
        {
            "ok": True,
            "run_root": str(run_root),
            "config_path": str(config_path),
        }
    )


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