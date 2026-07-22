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
import subprocess
from datetime import datetime


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


@app.post("/api/run-pipeline")
def api_run_pipeline():
    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config")
    mode = str(payload.get("mode", "")).strip()

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