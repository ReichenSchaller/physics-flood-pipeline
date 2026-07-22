#!/usr/bin/env python3
"""
review_run.py — read-only SFINCS run review utility, V1 draft.

Purpose
-------
Inspect an existing SFINCS pipeline run folder and produce a compact JSON summary
for the web launcher's future Review tab.

Design rules
------------
- Read-only by default.
- Does not rebuild HydroMT.
- Does not run SFINCS.
- Does not rerun postprocessing.
- Writes only under <run>/review/ when --write-json is explicitly passed.

Typical use
-----------
PY=/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/python
SCRIPT=/proj/zefflab/projects/Flooding/pipeline/code/review_run.py
RUN=/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_020
"$PY" "$SCRIPT" "$RUN" --pretty
"$PY" "$SCRIPT" "$RUN" --write-json --pretty
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import math
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Iterable

DEFAULT_RUN_ROOT = Path("/proj/zefflab/projects/Flooding/sfincs_runs")

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_SUFFIXES = {".txt", ".log", ".out", ".err", ".json", ".csv", ".md"}
MODEL_BINARY_SUFFIXES = {".dep", ".msk", ".ind", ".sbg", ".manning", ".man", ".scs", ".bnd", ".src", ".obs", ".crs", ".thd", ".bzs", ".dis"}


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


def rel_to(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def file_info(path: Path, root: Path | None = None) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
    }
    if root is not None:
        info["relpath"] = rel_to(path, root)
    if not path.exists():
        return info
    try:
        st = path.stat()
        info.update(
            {
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "size_bytes": st.st_size,
                "mtime": _dt.datetime.fromtimestamp(st.st_mtime, _dt.UTC).replace(microsecond=0).isoformat(),
            }
        )
    except Exception as exc:
        info["stat_error"] = repr(exc)
    return info


def safe_read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def safe_read_text(path: Path, max_chars: int = 8000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"<read failed: {exc!r}>"
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return head + "\n\n... [middle truncated by review_run.py] ...\n\n" + tail


def parse_sfincs_inp(path: Path) -> dict[str, str]:
    """Parse simple SFINCS inp key/value lines into lowercase keys."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lower()
        value = value.split("#", 1)[0].split("!", 1)[0].strip()
        if key:
            result[key] = value
    return result


def add_warning(warnings: list[dict[str, Any]], severity: str, title: str, message: str, next_step: str = "", details: Any = None) -> None:
    warnings.append(
        {
            "severity": severity,
            "title": title,
            "message": message,
            "next_step": next_step,
            "details": details,
        }
    )


def classify_run_status(run_root: Path) -> dict[str, Any]:
    model = run_root / "model"
    logs = run_root / "logs"
    post = run_root / "postprocess"

    failure_files = {
        "preprocess": run_root / "preprocess_failed.json",
        "sfincs": run_root / "sfincs_failed.json",
        "postprocess": run_root / "postprocess_failed.json",
    }

    stages: dict[str, Any] = {}
    stages["preprocess"] = {
        "failed": failure_files["preprocess"].exists(),
        "failure_file": str(failure_files["preprocess"]) if failure_files["preprocess"].exists() else None,
        "complete_evidence": [
            rel_to(p, run_root)
            for p in [run_root / "preprocess_manifest.json", model / "sfincs.inp"]
            if p.exists()
        ],
    }
    stages["sfincs"] = {
        "failed": failure_files["sfincs"].exists(),
        "failure_file": str(failure_files["sfincs"]) if failure_files["sfincs"].exists() else None,
        "complete_evidence": [
            rel_to(p, run_root)
            for p in [model / "sfincs_map.nc", model / "sfincs_his.nc", model / "sfincs.log"]
            if p.exists()
        ],
    }
    stages["postprocess"] = {
        "failed": failure_files["postprocess"].exists(),
        "failure_file": str(failure_files["postprocess"]) if failure_files["postprocess"].exists() else None,
        "complete_evidence": [
            rel_to(p, run_root)
            for p in [post / "run_summary.json", post / "run_summary.txt", post / "output_variables.txt"]
            if p.exists()
        ],
    }

    real_artifacts = []
    for p in [run_root / "job_ids.txt", model / "sfincs.inp", model / "sfincs_map.nc", model / "sfincs_his.nc"]:
        if p.exists():
            real_artifacts.append(rel_to(p, run_root))
    if logs.exists():
        real_artifacts.extend(rel_to(p, run_root) for p in logs.glob("*.out"))
        real_artifacts.extend(rel_to(p, run_root) for p in logs.glob("*.err"))
        real_artifacts.extend(rel_to(p, run_root) for p in logs.glob("*.log"))
    if post.exists():
        real_artifacts.extend(rel_to(p, run_root) for p in post.rglob("*") if p.is_file())

    scaffold_evidence = [
        rel_to(p, run_root)
        for p in [run_root / "run_config.json", run_root / "saved_config.json", run_root / "launcher_config.json", run_root / "scripts", logs, model, post]
        if p.exists()
    ]

    if any(v["failed"] for v in stages.values()):
        label = "failed"
    elif (model / "sfincs_map.nc").exists() and (model / "sfincs_his.nc").exists() and stages["postprocess"]["complete_evidence"]:
        label = "completed"
    elif (model / "sfincs_map.nc").exists() or (model / "sfincs_his.nc").exists():
        label = "sfincs-completed-postprocess-missing-or-partial"
    elif (model / "sfincs.inp").exists():
        label = "preprocess-completed-sfincs-missing-or-running"
    elif scaffold_evidence and not real_artifacts:
        label = "scaffold-only"
    else:
        label = "unknown-or-empty"

    return {
        "label": label,
        "stages": stages,
        "real_artifacts_count": len(real_artifacts),
        "real_artifacts_sample": sorted(real_artifacts)[:30],
        "scaffold_evidence": scaffold_evidence,
    }


def short_config_summary(cfg: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "run_name",
        "event_name",
        "run_series",
        "pipeline_mode",
        "preprocess_mode",
        "output_root",
        "project_root",
        "data_root",
        "tref",
        "tstart",
        "tstop",
        "dtout_s",
        "dthisout_s",
        "dtmaxout_s",
        "use_rainfall",
        "use_waterlevel_boundary",
        "use_discharge_boundary",
        "use_infiltration",
        "infiltration_mode",
        "curve_number_path",
        "dem_zmin",
        "use_mask_template",
        "mask_template_path",
        "sfincs_container_path",
        "sfincs_container",
        "conda_python",
        "preprocess_mem",
        "sfincs_mem",
        "postprocess_mem",
        "sfincs_cpus_per_task",
    ]
    out = {k: cfg.get(k) for k in keys if k in cfg}
    if isinstance(cfg.get("data_catalogs"), list):
        out["data_catalogs"] = cfg.get("data_catalogs")
    if isinstance(cfg.get("hydromt_dem_sources"), list):
        out["hydromt_dem_sources"] = cfg.get("hydromt_dem_sources")
    return out


def collect_known_files(run_root: Path, sfincs_inp: dict[str, str]) -> dict[str, Any]:
    model = run_root / "model"
    post = run_root / "postprocess"
    out: dict[str, Any] = {
        "run_level": {},
        "model_core": {},
        "netcdf_outputs": {},
        "postprocess_core": {},
        "sfincs_inp_file_pointers": [],
    }
    for name in ["run_config.json", "saved_config.json", "launcher_config.json", "job_ids.txt", "preprocess_manifest.json", "preprocess_failed.json", "sfincs_failed.json", "postprocess_failed.json"]:
        out["run_level"][name] = file_info(run_root / name, run_root)
    for name in ["sfincs.inp", "sfincs.dep", "sfincs.msk", "sfincs.ind", "sfincs.sbg", "sfincs.manning", "sfincs.man", "sfincs.scs", "sfincs.bnd", "sfincs.src", "sfincs.obs", "sfincs.crs", "sfincs.thd", "sfincs.bzs", "sfincs.dis", "precip_2d.nc", "sfincs.log"]:
        out["model_core"][name] = file_info(model / name, run_root)
    for name in ["sfincs_map.nc", "sfincs_his.nc"]:
        out["netcdf_outputs"][name] = file_info(model / name, run_root)
    for name in ["run_summary.json", "run_summary.txt", "output_variables.txt"]:
        out["postprocess_core"][name] = file_info(post / name, run_root)

    for key, value in sorted(sfincs_inp.items()):
        if not key.endswith("file"):
            continue
        # Some SFINCS values can be blank, numeric flags, or whitespace.
        value = value.strip().strip('"').strip("'")
        if not value or value in {"0", "none", "None"}:
            continue
        p = model / value
        out["sfincs_inp_file_pointers"].append(
            {
                "key": key,
                "value": value,
                "exists": p.exists(),
                "relpath": rel_to(p, run_root),
                "size_bytes": p.stat().st_size if p.exists() and p.is_file() else None,
            }
        )
    return out


def try_import_numpy():
    try:
        import numpy as np  # type: ignore

        return np, None
    except Exception as exc:  # pragma: no cover - environment dependent
        return None, repr(exc)


def binary_float_stats(path: Path, dtype: str = "float32") -> dict[str, Any]:
    np, import_error = try_import_numpy()
    if np is None:
        return {"available": False, "error": f"numpy import failed: {import_error}"}
    if not path.exists():
        return {"available": False, "error": "file does not exist"}
    try:
        arr = np.fromfile(path, dtype=dtype)
        if arr.size == 0:
            return {"available": False, "error": "empty file", "count": 0}
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return {"available": False, "error": "no finite values", "count": int(arr.size)}
        # Avoid treating inactive zeros as the whole story, but keep both sets.
        positive = finite[finite > 0]
        sample = positive if positive.size else finite
        stats = {
            "available": True,
            "dtype": dtype,
            "count": int(arr.size),
            "finite_count": int(finite.size),
            "positive_count": int(positive.size),
            "min": float(np.nanmin(finite)),
            "max": float(np.nanmax(finite)),
            "mean": float(np.nanmean(finite)),
            "p05": float(np.nanpercentile(sample, 5)),
            "median": float(np.nanpercentile(sample, 50)),
            "p95": float(np.nanpercentile(sample, 95)),
            "positive_mean": float(np.nanmean(positive)) if positive.size else None,
        }
        return stats
    except Exception as exc:
        return {"available": False, "error": repr(exc), "traceback": traceback.format_exc(limit=3)}


def check_scs(run_root: Path, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    path = run_root / "model" / "sfincs.scs"
    stats = binary_float_stats(path)
    result = {"path": str(path), "stats_float32": stats, "interpretation": "not checked"}
    if not path.exists():
        result["interpretation"] = "missing"
        return result
    if not stats.get("available"):
        add_warning(
            warnings,
            "minor",
            "Could not read sfincs.scs stats",
            "The Review utility could not interpret model/sfincs.scs as float32 binary.",
            "If the run uses Curve Number/SCS infiltration, inspect this file manually or with the existing comparison script.",
            stats,
        )
        result["interpretation"] = "unreadable"
        return result

    max_v = stats.get("max")
    med_v = stats.get("median")
    mean_pos = stats.get("positive_mean")
    if isinstance(max_v, (int, float)) and isinstance(med_v, (int, float)):
        if max_v > 20 and med_v > 20:
            result["interpretation"] = "suspicious_raw_curve_number_written_to_scs"
            add_warning(
                warnings,
                "critical",
                "SCS file looks like raw Curve Number values",
                "model/sfincs.scs has large positive values that look like CN values, not SCS retention/storage values.",
                "Verify that Curve Number was converted with S=(1000/CN)-10 before writing sfincs.scs. Re-run preprocessing after the fix if needed.",
                stats,
            )
        elif max_v <= 10 and (mean_pos is None or mean_pos <= 10):
            result["interpretation"] = "looks_like_converted_scs_storage"
        else:
            result["interpretation"] = "mixed_or_needs_manual_review"
            add_warning(
                warnings,
                "major",
                "SCS values need review",
                "model/sfincs.scs is present, but the value range is not clearly the expected converted SCS storage range.",
                "Compare against the known-good/native SCS file or inspect the Curve Number conversion audit.",
                stats,
            )
    return result


def check_dep(run_root: Path, cfg: dict[str, Any], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    path = run_root / "model" / "sfincs.dep"
    stats = binary_float_stats(path)
    result = {"path": str(path), "stats_float32": stats, "interpretation": "not checked"}
    if not path.exists() or not stats.get("available"):
        return result
    min_v = stats.get("min")
    max_v = stats.get("max")
    dem_zmin = cfg.get("dem_zmin")
    hydromt_sources = cfg.get("hydromt_dem_sources")
    result["configured_dem_zmin"] = dem_zmin
    result["configured_hydromt_dem_sources"] = hydromt_sources
    if isinstance(min_v, (int, float)):
        if min_v >= 0:
            result["interpretation"] = "no_negative_bed_values_seen_possible_zmin_clipping_or_dry_domain"
            add_warning(
                warnings,
                "major",
                "DEP has no negative values",
                "model/sfincs.dep does not show negative bed elevations. For the Harris County reproduction path, that can indicate zmin clipping or lost bathymetry/topobathy depth.",
                "Check dem_zmin and hydromt_dem_sources[*].zmin. For the current manual reproduction test, confirm zmin around -50 before trusting plots.",
                {"stats": stats, "dem_zmin": dem_zmin, "hydromt_dem_sources": hydromt_sources},
            )
        elif isinstance(max_v, (int, float)) and max_v == 0 and min_v == 0:
            result["interpretation"] = "all_zero_dep_suspicious"
        else:
            result["interpretation"] = "has_negative_values"
    return result


def check_sfincs_inp_semantics(sfincs_inp: dict[str, str], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "epsg": sfincs_inp.get("epsg"),
        "crsgeo": sfincs_inp.get("crsgeo"),
        "coriolis": sfincs_inp.get("coriolis"),
        "tref": sfincs_inp.get("tref"),
        "tstart": sfincs_inp.get("tstart"),
        "tstop": sfincs_inp.get("tstop"),
        "dtout": sfincs_inp.get("dtout"),
        "dtmapout": sfincs_inp.get("dtmapout"),
        "dthisout": sfincs_inp.get("dthisout"),
    }
    crsgeo = str(sfincs_inp.get("crsgeo", "")).strip()
    epsg = str(sfincs_inp.get("epsg", "")).strip()
    coriolis = str(sfincs_inp.get("coriolis", "")).strip()
    if crsgeo not in {"", "0", "0.0", "false", "False"} and epsg in {"32615", "32615.0"}:
        add_warning(
            warnings,
            "critical",
            "sfincs.inp may interpret UTM grid as geographic coordinates",
            "crsgeo is nonzero while epsg looks like UTM 32615. Under the current v2.3 Apptainer workflow, this can trigger geographic-coordinate/Coriolis behavior and solver blowup.",
            "For the current Harris County container path, expected compatibility settings are epsg=32615, crsgeo=0, coriolis=0 unless intentionally testing something else.",
            result,
        )
    if epsg in {"32615", "32615.0"} and crsgeo in {"0", "0.0"} and coriolis not in {"", "0", "0.0", "false", "False"}:
        add_warning(
            warnings,
            "major",
            "Coriolis is enabled for UTM Harris County run",
            "coriolis is not zero even though the model appears to be a projected UTM 32615 setup.",
            "Confirm this is intentional. The validated compatibility path used coriolis=0.",
            result,
        )
    dtmapout_raw = sfincs_inp.get("dtmapout")
    dtout_raw = sfincs_inp.get("dtout")

    dtmapout_missing = str(dtmapout_raw).strip() in {"", "0", "0.0", "None", "none", "null"}
    dtout_missing = str(dtout_raw).strip() in {"", "0", "0.0", "None", "none", "null"}

    if dtmapout_missing and dtout_missing:
        add_warning(
            warnings,
            "major",
            "map output interval is blank or zero",
            "Both dtmapout and dtout appear missing/zero. That can prevent useful sfincs_map.nc time frames and animation review.",
            "Check setup_time_and_config / run_config dtout_s and ensure a positive map-output interval is written.",
            result,
        )
    return result


def check_file_pointers(files_summary: dict[str, Any], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [row for row in files_summary.get("sfincs_inp_file_pointers", []) if not row.get("exists")]
    if missing:
        add_warning(
            warnings,
            "critical",
            "sfincs.inp points to missing model files",
            f"{len(missing)} file pointer(s) in sfincs.inp do not exist in the model folder.",
            "Open sfincs.inp and verify the referenced native files were written/copied correctly before running or trusting outputs.",
            missing,
        )
    return {"missing_count": len(missing), "missing": missing}


def summarize_netcdf(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "path": str(path), "error": "file does not exist"}
    try:
        import xarray as xr  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"available": False, "path": str(path), "error": f"xarray import failed: {exc!r}"}
    try:
        with xr.open_dataset(path, decode_times=True) as ds:
            dims = {str(k): int(v) for k, v in ds.sizes.items()}
            variables: dict[str, Any] = {}
            for name, var in ds.data_vars.items():
                variables[str(name)] = {
                    "dims": [str(d) for d in var.dims],
                    "shape": [int(s) for s in var.shape],
                    "dtype": str(var.dtype),
                    "units": str(var.attrs.get("units", "")),
                    "long_name": str(var.attrs.get("long_name", "")),
                }
            coords = {str(k): {"dims": [str(d) for d in v.dims], "shape": [int(s) for s in v.shape], "dtype": str(v.dtype)} for k, v in ds.coords.items()}
            time_summary: dict[str, Any] = {}
            for tname in ["time", "timemax", "t"]:
                if tname in ds.coords or tname in ds.variables:
                    arr = ds[tname].values
                    try:
                        n = len(arr)
                    except TypeError:
                        n = 1
                    time_summary[tname] = {"count": int(n)}
                    try:
                        if n:
                            time_summary[tname]["first"] = str(arr[0])
                            time_summary[tname]["last"] = str(arr[-1])
                    except Exception:
                        pass
            return {
                "available": True,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "dims": dims,
                "coords": coords,
                "variables": variables,
                "time": time_summary,
            }
    except Exception as exc:
        return {"available": False, "path": str(path), "error": repr(exc), "traceback": traceback.format_exc(limit=4)}


def check_netcdf_outputs(run_root: Path, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    model = run_root / "model"
    out = {
        "sfincs_map.nc": summarize_netcdf(model / "sfincs_map.nc"),
        "sfincs_his.nc": summarize_netcdf(model / "sfincs_his.nc"),
    }
    if not out["sfincs_map.nc"].get("available"):
        add_warning(
            warnings,
            "major",
            "sfincs_map.nc is missing or unreadable",
            "The Review page cannot make map layers or an animation without model/sfincs_map.nc.",
            "Confirm SFINCS completed and produced map outputs. If dtmapout was zero, fix that before rerunning.",
            out["sfincs_map.nc"],
        )
    if not out["sfincs_his.nc"].get("available"):
        add_warning(
            warnings,
            "minor",
            "sfincs_his.nc is missing or unreadable",
            "Obs-point and cross-section graphs need model/sfincs_his.nc.",
            "Confirm obs/cross-section output was enabled and SFINCS completed.",
            out["sfincs_his.nc"],
        )
    return out


def discover_artifacts(run_root: Path) -> dict[str, Any]:
    artifacts: dict[str, Any] = {
        "images": [],
        "text": [],
        "netcdf": [],
        "geotiff": [],
        "other": [],
    }
    roots = [run_root / "postprocess", run_root / "review", run_root / "model", run_root / "logs"]
    for base in roots:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            suffix = p.suffix.lower()
            row = file_info(p, run_root)
            if suffix in IMAGE_SUFFIXES:
                artifacts["images"].append(row)
            elif suffix in TEXT_SUFFIXES:
                artifacts["text"].append(row)
            elif suffix == ".nc":
                artifacts["netcdf"].append(row)
            elif suffix in {".tif", ".tiff"}:
                artifacts["geotiff"].append(row)
            else:
                artifacts["other"].append(row)
    for key in list(artifacts):
        artifacts[key] = artifacts[key][:200]
    return artifacts


def collect_log_snippets(run_root: Path) -> dict[str, Any]:
    logs: dict[str, Any] = {}
    candidates = []
    for base in [run_root / "logs", run_root / "model"]:
        if base.exists():
            candidates.extend(p for p in base.glob("*.out"))
            candidates.extend(p for p in base.glob("*.err"))
            candidates.extend(p for p in base.glob("*.log"))
    for p in sorted(candidates)[:30]:
        logs[rel_to(p, run_root)] = {
            "info": file_info(p, run_root),
            "snippet": safe_read_text(p, max_chars=4000),
        }
    return logs


def csv_header(path: Path) -> list[str] | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            return next(reader)
    except Exception:
        return None


def scan_config_paths(cfg: dict[str, Any], run_root: Path) -> dict[str, Any]:
    """Collect likely user-supplied file paths from config without assuming all key names."""
    rows = []
    for key, value in sorted(cfg.items()):
        if isinstance(value, str) and ("/" in value or value.endswith((".csv", ".nc", ".tif", ".json", ".yml", ".yaml"))):
            p = Path(value)
            if not p.is_absolute():
                p = run_root / value
            row = file_info(p)
            row["key"] = key
            if p.suffix.lower() == ".csv" and p.exists() and p.is_file():
                row["csv_header"] = csv_header(p)
            rows.append(row)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str) and "/" in item:
                    p = Path(item)
                    row = file_info(p)
                    row["key"] = f"{key}[{i}]"
                    rows.append(row)
                elif isinstance(item, dict):
                    for subkey, subvalue in item.items():
                        if isinstance(subvalue, str) and "/" in subvalue:
                            p = Path(subvalue)
                            row = file_info(p)
                            row["key"] = f"{key}[{i}].{subkey}"
                            rows.append(row)
    return {"paths": rows[:300]}


def check_discharge_config(config_paths: dict[str, Any], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    """Very light V1 discharge audit: preserve/show leading-zero headers if CSVs are visible."""
    discharge_like = []
    for row in config_paths.get("paths", []):
        key = str(row.get("key", "")).lower()
        path = str(row.get("path", "")).lower()
        if "discharge" in key or "source_table" in key or "source" in key or "discharge" in path:
            discharge_like.append(row)
    headers = []
    for row in discharge_like:
        header = row.get("csv_header")
        if header:
            headers.append({"key": row.get("key"), "path": row.get("path"), "header": header})
            numeric_lost = [h for h in header if re.fullmatch(r"8072600|8073100|8067650", str(h))]
            if numeric_lost:
                add_warning(
                    warnings,
                    "major",
                    "Possible lost leading zero in discharge CSV header",
                    "A discharge-related CSV header contains USGS-like IDs without the leading zero.",
                    "Read discharge IDs as strings and resolve against the selected source table; do not let pandas convert IDs to numbers.",
                    {"row": row, "numeric_lost_headers": numeric_lost},
                )
    return {"discharge_like_paths": discharge_like, "headers": headers}


def build_review(run_root: Path) -> dict[str, Any]:
    run_root = run_root.resolve()
    warnings: list[dict[str, Any]] = []

    cfg_path = run_root / "run_config.json"
    cfg = safe_read_json(cfg_path) if cfg_path.exists() else {}
    if not cfg_path.exists():
        add_warning(
            warnings,
            "major",
            "run_config.json is missing",
            "The run folder does not contain run_config.json, so Review can only inspect files and cannot explain the intended setup.",
            "Confirm this is a real pipeline run folder, not a copied model-only folder.",
        )
    elif isinstance(cfg, dict) and cfg.get("_read_error"):
        add_warning(
            warnings,
            "critical",
            "run_config.json could not be read",
            "The run config exists but could not be parsed as JSON.",
            "Open run_config.json and repair or restore it from a backup.",
            cfg,
        )
    if not isinstance(cfg, dict):
        cfg = {"_unexpected_config_type": str(type(cfg))}

    sfincs_inp_path = run_root / "model" / "sfincs.inp"
    sfincs_inp = parse_sfincs_inp(sfincs_inp_path)
    if not sfincs_inp_path.exists():
        add_warning(
            warnings,
            "major",
            "model/sfincs.inp is missing",
            "No written SFINCS input file was found. This run probably did not complete preprocessing.",
            "Check preprocess logs and preprocess_failed.json.",
        )

    status = classify_run_status(run_root)
    files = collect_known_files(run_root, sfincs_inp)
    pointer_check = check_file_pointers(files, warnings)
    inp_check = check_sfincs_inp_semantics(sfincs_inp, warnings)
    scs_check = check_scs(run_root, warnings)
    dep_check = check_dep(run_root, cfg, warnings)
    netcdf = check_netcdf_outputs(run_root, warnings)
    artifacts = discover_artifacts(run_root)
    config_paths = scan_config_paths(cfg, run_root)
    discharge = check_discharge_config(config_paths, warnings)
    logs = collect_log_snippets(run_root)

    # Sort warnings by rough severity.
    severity_rank = {"critical": 0, "major": 1, "minor": 2, "info": 3}
    warnings = sorted(warnings, key=lambda w: severity_rank.get(str(w.get("severity")), 99))

    return {
        "review_version": "review_v1_1_2026-06-17",
        "created_at_utc": utc_now_iso(),
        "run_name": run_root.name,
        "run_root": str(run_root),
        "status": status,
        "run_config": cfg,
        "config_summary": short_config_summary(cfg),
        "config_path_scan": config_paths,
        "sfincs_inp": inp_check,
        "checks": {
            "sfincs_inp_file_pointers": pointer_check,
            "scs": scs_check,
            "dep": dep_check,
            "discharge_config": discharge,
        },
        "netcdf": netcdf,
        "files": files,
        "artifacts": artifacts,
        "warnings": warnings,
        "logs": logs,
    }


def resolve_run_arg(run_arg: str, run_root: Path | None = None) -> Path:
    p = Path(run_arg)
    if p.exists() or p.is_absolute() or "/" in run_arg:
        return p
    base = run_root or DEFAULT_RUN_ROOT
    return base / run_arg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only SFINCS run review utility.")
    parser.add_argument("run", help="Run folder path or run name under --run-root.")
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT), help="Run root used when RUN is a name, not a path.")
    parser.add_argument("--write-json", action="store_true", help="Write <run>/review/review_summary.json.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    args = parser.parse_args(argv)

    run_path = resolve_run_arg(args.run, Path(args.run_root)).resolve()
    if not run_path.exists():
        print(json.dumps({"error": "run folder does not exist", "run_path": str(run_path)}, indent=2), file=sys.stderr)
        return 2
    if not run_path.is_dir():
        print(json.dumps({"error": "run path is not a directory", "run_path": str(run_path)}, indent=2), file=sys.stderr)
        return 2

    review = build_review(run_path)

    if args.write_json:
        review_dir = run_path / "review"
        review_dir.mkdir(exist_ok=True)
        out_path = review_dir / "review_summary.json"
        out_path.write_text(json.dumps(review, indent=2, sort_keys=True), encoding="utf-8")
        review["written_json"] = str(out_path)

    print(json.dumps(review, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
