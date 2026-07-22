#!/usr/bin/env python3
"""
Build cached obs/gauge validation products for a SFINCS run review.

Outputs under:
    <run_root>/review/obs_gauges/

This script is intentionally tolerant of early validation CSV formats. It supports:
  1) scalar gauge targets: peak water level, mean flow, peak flow
  2) optional time-series rows with a time column
  3) point gauges matched by gauge_id/site_no/station_name or nearest x/y
  4) line gauges matched by gauge_id/line_id or nearest line midpoint

It does not modify model inputs or rerun SFINCS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import subprocess
import sys
import numpy as np
import pandas as pd
import xarray as xr

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None


PRODUCT_REL = Path("review") / "obs_gauges"
STATUS_NAME = "obs_gauges_status.json"
METRICS_NAME = "obs_gauges_metrics.json"
MANIFEST_NAME = "obs_gauges_manifest.json"
GAUGE_CSV_NAME = "gauge_metrics.csv"
DIALS_NAME = "gauge_dials.json"
HEATMAP_NAME = "error_heatmap.png"
OBSERVED_TS_NAME = "observed_gauge_timeseries.csv"
TIMESERIES_NAME = "obs_gauge_timeseries.json"
PIPELINE_ROOT = Path("/proj/zefflab/projects/Flooding/pipeline")
MAPS_DIR_REL = Path("review/maps")
SATELLITE_REL = MAPS_DIR_REL / "satellite_background.png"
ACTIVE_AREA_REL = MAPS_DIR_REL / "model_active_area_overlay.png"
CONTEXT_MAP_REL = MAPS_DIR_REL / "obs_gauge_context_map.png"
FLOW_ERROR_SURFACE_REL = MAPS_DIR_REL / "obs_flow_error_surface.png"
WL_ERROR_SURFACE_REL = MAPS_DIR_REL / "obs_wl_error_surface.png"

POINT_KIND_VALUES = {
    "point",
    "point_stage",
    "point_wl",
    "obs",
    "gauge",
    "station",
    "waterlevel",
    "water_level",
    "wl",
    "stage",
    "gage_height",
    "gauge_height",
}

LINE_KIND_VALUES = {
    "line",
    "line_flow",
    "line_discharge",
    "flow",
    "discharge",
    "q",
    "crs",
    "crosssection",
    "cross_section",
    "cross-section",
    "crosssection_discharge",
    "cross_section_discharge",
}

WATERLEVEL_TARGET_COLS = [
    "obs_wl_peak_m", "observed_wl_peak_m", "wl_peak_m", "waterlevel_peak_m",
    "obs_waterlevel_peak_m", "observed_waterlevel_peak_m", "stage_peak_m",
]
WATERLEVEL_TS_COLS = [
    "obs_wl_m", "observed_wl_m", "wl_m", "waterlevel_m", "stage_m", "obs_stage_m",
]
FLOW_MEAN_TARGET_COLS = [
    "obs_flow_mean_cms", "observed_flow_mean_cms", "flow_mean_cms", "discharge_mean_cms",
    "obs_q_mean_cms", "q_mean_cms",
]
FLOW_PEAK_TARGET_COLS = [
    "obs_flow_peak_cms", "observed_flow_peak_cms", "flow_peak_cms", "discharge_peak_cms",
    "obs_q_peak_cms", "q_peak_cms",
]
FLOW_TS_COLS = [
    "obs_flow_cms", "observed_flow_cms", "flow_cms", "discharge_cms", "q_cms", "obs_q_cms",
]
TIME_COLS = ["time", "datetime", "timestamp", "date_time", "date"]
ID_COLS = ["gauge_id", "site_no", "station_id", "station", "obs_id", "point_id", "line_id", "crs_id", "name"]
NAME_COLS = ["gauge_name", "station_name", "name", "description"]
X_COLS = ["x", "x_utm15n", "coord_x", "coord_x_utm15n", "lon", "longitude"]
Y_COLS = ["y", "y_utm15n", "coord_y", "coord_y_utm15n", "lat", "latitude"]
X1_COLS = ["x1", "x_start", "x0", "line_x1"]
Y1_COLS = ["y1", "y_start", "y0", "line_y1"]
X2_COLS = ["x2", "x_end", "line_x2"]
Y2_COLS = ["y2", "y_end", "line_y2"]

POINT_SIM_VARS = [
    "point_zs", "point_waterlevel", "point_water_level", "point_stage", "station_zs",
    "obs_zs", "zs_point", "zs_obs", "zs",
]
LINE_SIM_VARS = [
    "crosssection_discharge", "crs_discharge", "cross_section_discharge", "line_discharge",
    "q_crs", "q_crosssection", "q", "discharge",
]
POINT_X_VARS = ["point_x", "station_x", "obs_x", "x_point", "x_obs", "x"]
POINT_Y_VARS = ["point_y", "station_y", "obs_y", "y_point", "y_obs", "y"]
LINE_X_VARS = ["crosssection_x", "crs_x", "line_x", "x_crs"]
LINE_Y_VARS = ["crosssection_y", "crs_y", "line_y", "y_crs"]
NAME_VARS = [
    "point_name",
    "station_id",
    "station_name",
    "obs_name",
    "name",
    "crs_name",
    "crosssection_name",
]


@dataclass
class SimSeries:
    kind: str
    index: int
    sim_id: str
    name: str
    values: np.ndarray
    times: np.ndarray | None
    x: float | None = None
    y: float | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_col(name: str) -> str:
    return str(name or "").strip().lower().replace(" ", "_").replace("-", "_")


def first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = {norm_col(c): c for c in df.columns}
    for cand in candidates:
        if norm_col(cand) in lookup:
            return lookup[norm_col(cand)]
    return None

def first_float_from_row(row: pd.Series, candidates: list[str]) -> float | None:
    lookup = {norm_col(c): c for c in row.index}

    for cand in candidates:
        col = lookup.get(norm_col(cand))

        if not col:
            continue

        value = as_float(row.get(col))

        if value is not None:
            return value

    return None

def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return v


def as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "use", "enabled"}:
        return True
    if text in {"0", "false", "f", "no", "n", "disabled", ""}:
        return False
    return default

def clean_text_cell(value: Any) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "nat"}:
        return ""

    return text

def normalize_kind_value(value: Any) -> str | None:
    text = clean_text_cell(value).lower()
    text = text.replace("-", "_").replace(" ", "_")

    if text in LINE_KIND_VALUES:
        return "line"

    if text in POINT_KIND_VALUES:
        return "point"

    return None

def safe_name_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip(" \x00")
    arr = np.asarray(value)
    if arr.dtype.kind in {"S", "U", "O"} and arr.ndim > 0:
        parts = []
        for item in arr.ravel():
            if isinstance(item, bytes):
                parts.append(item.decode("utf-8", errors="ignore"))
            else:
                parts.append(str(item))
        text = "".join(parts).strip(" \x00")
        return text
    return str(value).strip(" \x00")


def infer_time_values(ds: xr.Dataset, arr: xr.DataArray) -> np.ndarray | None:
    for dim in arr.dims:
        if "time" in dim.lower() and dim in ds.coords:
            try:
                return pd.to_datetime(ds[dim].values).to_numpy()
            except Exception:
                return np.asarray(ds[dim].values)
    if "time" in ds.coords:
        try:
            return pd.to_datetime(ds["time"].values).to_numpy()
        except Exception:
            return np.asarray(ds["time"].values)
    return None


def choose_var(ds: xr.Dataset, candidates: list[str], require_time: bool = True) -> str | None:
    exact = {k.lower(): k for k in ds.data_vars}
    for cand in candidates:
        if cand.lower() in exact:
            name = exact[cand.lower()]
            if not require_time or any("time" in d.lower() for d in ds[name].dims):
                return name
    for name, arr in ds.data_vars.items():
        lname = name.lower()
        if require_time and not any("time" in d.lower() for d in arr.dims):
            continue
        for cand in candidates:
            token = cand.lower()
            if token in lname:
                return name
    return None


def non_time_dims(arr: xr.DataArray) -> list[str]:
    return [d for d in arr.dims if "time" not in d.lower()]


def extract_names(ds: xr.Dataset, count: int, kind_hint: str) -> list[str]:
    preferred = NAME_VARS if kind_hint == "point" else ["crs_name", "crosssection_name", "line_name"] + NAME_VARS
    for var in preferred:
        if var in ds:
            raw = ds[var].values
            arr = np.asarray(raw)
            names: list[str] = []
            if arr.ndim == 1:
                for i in range(min(count, arr.shape[0])):
                    names.append(safe_name_value(arr[i]))
            elif arr.ndim >= 2:
                for i in range(min(count, arr.shape[0])):
                    names.append(safe_name_value(arr[i]))
            if names:
                while len(names) < count:
                    names.append("")
                return names[:count]
    return [f"{kind_hint}_{i + 1:03d}" for i in range(count)]


def extract_xy(ds: xr.Dataset, count: int, kind_hint: str) -> tuple[list[float | None], list[float | None]]:
    x_candidates = POINT_X_VARS if kind_hint == "point" else LINE_X_VARS + POINT_X_VARS
    y_candidates = POINT_Y_VARS if kind_hint == "point" else LINE_Y_VARS + POINT_Y_VARS

    def pick(cands: list[str]) -> list[float | None]:
        for name in cands:
            if name not in ds:
                continue
            arr = np.asarray(ds[name].values)
            vals: list[float | None] = []
            if arr.ndim == 1 and arr.shape[0] >= count:
                for i in range(count):
                    vals.append(as_float(arr[i]))
                return vals
            if arr.ndim >= 2 and arr.shape[0] >= count:
                for i in range(count):
                    flat = np.asarray(arr[i]).astype(float).ravel()
                    finite = flat[np.isfinite(flat)]
                    vals.append(float(np.nanmean(finite)) if finite.size else None)
                return vals
        return [None] * count

    return pick(x_candidates), pick(y_candidates)


def extract_sim_series(ds: xr.Dataset, var_name: str, kind: str) -> list[SimSeries]:
    arr = ds[var_name]
    nt_dims = non_time_dims(arr)
    if not nt_dims:
        values = np.asarray(arr.values).reshape(-1)
        return [SimSeries(kind=kind, index=0, sim_id=f"{kind}_001", name=f"{kind}_001", values=values, times=infer_time_values(ds, arr))]

    station_dim = nt_dims[-1]
    transposed_dims = [d for d in arr.dims if "time" in d.lower()] + [station_dim]
    # If there are extra non-time dims, flatten them into the station axis by stacking.
    try:
        if len(nt_dims) > 1:
            stacked = arr.stack(__review_station=nt_dims)
            station_dim = "__review_station"
            transposed_dims = [d for d in stacked.dims if "time" in d.lower()] + [station_dim]
            arr2 = stacked.transpose(*transposed_dims)
        else:
            arr2 = arr.transpose(*transposed_dims)
    except Exception:
        arr2 = arr
        station_dim = nt_dims[-1]

    raw = np.asarray(arr2.values)
    if raw.ndim == 1:
        raw = raw.reshape(-1, 1)
    if raw.ndim > 2:
        raw = raw.reshape(raw.shape[0], -1)

    count = raw.shape[1]
    names = extract_names(ds, count, kind)
    xs, ys = extract_xy(ds, count, kind)
    times = infer_time_values(ds, arr)

    out = []
    for i in range(count):
        name = names[i] or f"{kind}_{i + 1:03d}"
        out.append(SimSeries(
            kind=kind,
            index=i,
            sim_id=str(name),
            name=str(name),
            values=np.asarray(raw[:, i], dtype=float),
            times=times,
            x=xs[i],
            y=ys[i],
        ))
    return out


def is_good_validation_csv_candidate(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False

    if path.suffix.lower() != ".csv":
        return False

    parts = {str(part).lower() for part in path.parts}
    if "_misc" in parts or "_quarantine" in parts:
        return False

    name = path.name.lower()
    reject_tokens = [
        "draft",
        "backup",
        "stale",
        "do_not_use",
        "original",
        "candidate",
    ]

    if any(token in name for token in reject_tokens):
        return False

    return True



def validation_csv_rank(path: Path) -> tuple[int, str]:
    name = path.name.lower()

    if "validation" in name and ("timeseries" in name or "time_series" in name):
        return (0, str(path))

    if "gauge" in name and ("timeseries" in name or "time_series" in name):
        return (1, str(path))

    if "validation" in name and "gauge" in name:
        return (2, str(path))

    if "observed" in name and ("timeseries" in name or "time_series" in name):
        return (3, str(path))

    return (9, str(path))


def best_top_level_validation_csv(folder: Path) -> Path | None:
    if not folder.exists() or not folder.is_dir():
        return None

    candidates = [
        p for p in folder.glob("*.csv")
        if is_good_validation_csv_candidate(p)
    ]

    if not candidates:
        return None

    candidates.sort(key=validation_csv_rank)
    return candidates[0].resolve()

def resolve_validation_path_candidate(path: Path) -> Path | None:
    if path.exists() and path.is_dir():
        return best_top_level_validation_csv(path)

    if path.exists() and path.is_file() and is_good_validation_csv_candidate(path):
        return path.resolve()

    return None

def discover_validation_csv(run_root: Path, explicit: str | None) -> tuple[Path | None, list[str]]:
    notes: list[str] = []

    if explicit:
        p = Path(explicit).expanduser()

        if not p.is_absolute():
            p = run_root / p

        resolved = resolve_validation_path_candidate(p)

        if resolved is not None:
            if p.exists() and p.is_dir():
                notes.append(f"Using top-level validation CSV from explicit folder: {resolved}")
            else:
                notes.append(f"Using explicit validation CSV: {resolved}")

            return resolved, notes

        notes.append(f"Explicit validation path did not resolve to a usable top-level CSV: {p}")

    search_dirs: list[Path] = [
        run_root / "review" / "obs_gauges",
        run_root / "validation",
        run_root / "model",
    ]

    candidate_paths: list[Path] = []

    cfg_path = run_root / "run_config.json"

    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

            for key in [
                "obs_gauge_validation_path",
                "gauge_validation_path",
                "validation_gauge_path",
                "validation_gauge_timeseries_path",
            ]:
                val = str(cfg.get(key, "") or "").strip()

                if val:
                    candidate_paths.append(Path(val))

            catalogs = cfg.get("data_catalogs") or []

            if isinstance(catalogs, str):
                try:
                    parsed = json.loads(catalogs)
                    catalogs = parsed if isinstance(parsed, list) else [catalogs]
                except Exception:
                    catalogs = [
                        x.strip()
                        for x in catalogs.replace(",", "\n").splitlines()
                        if x.strip()
                    ]

            for root in catalogs:
                croot = Path(str(root))
                search_dirs.append(croot / "event_validation_gauges")

        except Exception as exc:
            notes.append(
                f"Could not inspect run_config.json for validation paths: "
                f"{type(exc).__name__}: {exc}"
            )

    seen: set[str] = set()

    for p in candidate_paths:
        try:
            rp = p.expanduser().resolve()
        except Exception:
            rp = p

        key = str(rp)

        if key in seen:
            continue

        seen.add(key)

        resolved = resolve_validation_path_candidate(rp)

        if resolved is not None:
            notes.append(f"Using configured validation CSV: {resolved}")
            return resolved, notes

    for folder in search_dirs:
        try:
            rf = folder.expanduser().resolve()
        except Exception:
            rf = folder

        key = str(rf)

        if key in seen:
            continue

        seen.add(key)

        best = best_top_level_validation_csv(rf)

        if best is not None:
            notes.append(f"Auto-selected top-level validation CSV: {best}")
            return best, notes

    return None, notes

def load_validation(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def validation_dataframe_has_timeseries(df: pd.DataFrame) -> bool:
    time_col = first_col(df, TIME_COLS)
    wl_ts_col = first_col(df, WATERLEVEL_TS_COLS)
    flow_ts_col = first_col(df, FLOW_TS_COLS)

    if not time_col:
        return False

    return bool(wl_ts_col or flow_ts_col)

def count_observed_timeseries_rows(records: list[dict[str, Any]]) -> int:
    count = 0

    for rec in records:
        if rec.get("time") is pd.NaT or pd.isna(rec.get("time")):
            continue

        if rec.get("obs_wl_m") is not None or rec.get("obs_flow_cms") is not None:
            count += 1

    return count


def finalize_grouped_observed_scalars(grouped: dict[str, dict[str, Any]]) -> None:
    for rec in grouped.values():
        kind = str(rec.get("kind") or "").lower()
        ts_rows = rec.get("timeseries") or []

        if not ts_rows:
            continue

        if kind == "line":
            flows = [
                as_float(row.get("obs_flow_cms"))
                for row in ts_rows
            ]
            flows = [
                float(v)
                for v in flows
                if v is not None and math.isfinite(float(v))
            ]

            if flows:
                rec["obs_flow_mean_cms"] = float(np.mean(flows))
                rec["obs_flow_peak_cms"] = float(np.max(flows))
                rec["usable_for_flow_error"] = True

        else:
            wls = [
                as_float(row.get("obs_wl_m"))
                for row in ts_rows
            ]
            wls = [
                float(v)
                for v in wls
                if v is not None and math.isfinite(float(v))
            ]

            if wls:
                rec["obs_wl_peak_m"] = float(np.max(wls))
                rec["usable_for_wl_error"] = True

def discover_observed_timeseries_csv(
    run_root: Path,
    validation_csv: Path | None = None,
) -> Path | None:
    candidates: list[Path] = [
        run_root / PRODUCT_REL / OBSERVED_TS_NAME,
    ]

    search_dirs: list[Path] = []

    if validation_csv is not None:
        search_dirs.append(validation_csv.parent)
        candidates.append(validation_csv.parent / OBSERVED_TS_NAME)

    cfg_path = run_root / "run_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

            for key in [
                "obs_gauge_timeseries_path",
                "gauge_timeseries_path",
                "observed_gauge_timeseries_path",
            ]:
                val = str(cfg.get(key, "") or "").strip()
                if val:
                    candidates.append(Path(val))

            catalogs = cfg.get("data_catalogs") or []
            if isinstance(catalogs, str):
                try:
                    parsed = json.loads(catalogs)
                    catalogs = parsed if isinstance(parsed, list) else [catalogs]
                except Exception:
                    catalogs = [
                        x.strip()
                        for x in catalogs.replace(",", "\n").splitlines()
                        if x.strip()
                    ]

            for root in catalogs:
                croot = Path(str(root))
                gauge_dir = croot / "event_validation_gauges"
                search_dirs.append(gauge_dir)
                candidates.append(gauge_dir / OBSERVED_TS_NAME)

        except Exception:
            pass

    for folder in search_dirs:
        if not folder.exists() or not folder.is_dir():
            continue

        for p in folder.glob("*.csv"):
            if p.name.lower() == OBSERVED_TS_NAME and is_good_validation_csv_candidate(p):
                candidates.append(p)

    seen: set[str] = set()

    for p in candidates:
        try:
            rp = p.expanduser().resolve()
        except Exception:
            rp = p

        key = str(rp)
        if key in seen:
            continue
        seen.add(key)

        if rp.exists() and rp.is_file() and is_good_validation_csv_candidate(rp):
            return rp

    return None

def load_observed_timeseries(path: Path) -> list[dict[str, Any]]:
    df = pd.read_csv(path, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    gauge_id_col = first_col(df, ["gauge_id", "site_no", "station_id", "station", "obs_id"])
    line_id_col = first_col(df, ["line_id", "crs_id", "crosssection_id", "cross_section_id"])
    kind_col = first_col(df, ["kind", "type", "role"])
    time_col = first_col(df, TIME_COLS)

    wl_col = first_col(df, WATERLEVEL_TS_COLS)
    flow_col = first_col(df, FLOW_TS_COLS)

    if not time_col:
        return []

    records: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        gauge_id = clean_text_cell(row.get(gauge_id_col, "") if gauge_id_col else "")
        line_id = clean_text_cell(row.get(line_id_col, "") if line_id_col else "")

        kind = normalize_kind_value(row.get(kind_col, "") if kind_col else "")

        if kind is None:
            if line_id:
                kind = "line"
            else:
                kind = "point"

        t = pd.to_datetime(row.get(time_col), errors="coerce")
        if pd.isna(t):
            continue

        rec = {
            "kind": kind,
            "gauge_id": gauge_id,
            "line_id": line_id,
            "time": t,
            "obs_wl_m": as_float(row.get(wl_col)) if wl_col else None,
            "obs_flow_cms": as_float(row.get(flow_col)) if flow_col else None,
        }

        if rec["obs_wl_m"] is None and rec["obs_flow_cms"] is None:
            continue

        records.append(rec)

    return records


def attach_observed_timeseries(
    grouped: dict[str, dict[str, Any]],
    ts_records: list[dict[str, Any]],
) -> int:
    if not ts_records:
        return 0

    attached = 0

    for ts in ts_records:
        kind = str(ts.get("kind") or "").lower()
        gauge_id = str(ts.get("gauge_id") or "").strip()
        line_id = str(ts.get("line_id") or "").strip()

        candidates: list[str] = []

        if kind == "line":
            if line_id:
                candidates.append(f"line:{line_id}")
            if gauge_id:
                candidates.append(f"line:{gauge_id}")

        elif kind == "point":
            if gauge_id:
                candidates.append(f"point:{gauge_id}")

        # Fall back across role when the observed hydrograph is keyed only by USGS site number.
        if gauge_id:
            candidates += [
                f"line:{gauge_id}",
                f"point:{gauge_id}",
            ]

        if line_id:
            candidates.append(f"line:{line_id}")

        target_key = None

        for key in candidates:
            if key in grouped:
                target_key = key
                break

        if target_key is None and gauge_id:
            for key, rec in grouped.items():
                scalar = rec.get("scalar") or rec
                scalar_kind = str(scalar.get("kind") or "").lower()
                scalar_gauge_id = str(scalar.get("gauge_id") or "").strip()

                if scalar_gauge_id != gauge_id:
                    continue

                if kind and scalar_kind and scalar_kind != kind:
                    continue

                target_key = key
                break

        if target_key is None:
            continue

        grouped[target_key].setdefault("timeseries", []).append(ts)
        attached += 1

    return attached


def infer_kind(row: pd.Series) -> str:
    for col in ["kind", "type", "role", "validation_role", "observed_parameter"]:
        if col in row.index:
            kind = normalize_kind_value(row.get(col))
            if kind is not None:
                return kind

    for col in ["line_id", "crs_id", "crosssection_id", "cross_section_id"]:
        if col in row.index and clean_text_cell(row.get(col)):
            return "line"

    has_line_xy = any(
        c in row.index and as_float(row.get(c)) is not None
        for c in X1_COLS + Y1_COLS + X2_COLS + Y2_COLS
    )

    if has_line_xy:
        return "line"

    has_flow_value = any(
        c in row.index and as_float(row.get(c)) is not None
        for c in FLOW_MEAN_TARGET_COLS + FLOW_PEAK_TARGET_COLS + FLOW_TS_COLS
    )

    has_wl_value = any(
        c in row.index and as_float(row.get(c)) is not None
        for c in WATERLEVEL_TARGET_COLS + WATERLEVEL_TS_COLS
    )

    if has_flow_value and not has_wl_value:
        return "line"

    return "point"


def make_validation_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    id_col = first_col(df, ID_COLS)
    gauge_id_col = first_col(df, ["gauge_id", "site_no", "station_id", "station", "obs_id", "point_id"])
    line_id_col = first_col(df, ["line_id", "crs_id", "crosssection_id", "cross_section_id"])
    usable_wl_col = first_col(df, ["usable_for_wl_error", "use_for_wl_error", "wl_error_enabled"])
    usable_flow_col = first_col(df, ["usable_for_flow_error", "use_for_flow_error", "flow_error_enabled"])
    name_col = first_col(df, NAME_COLS)
    time_col = first_col(df, TIME_COLS)

    wl_peak_col = first_col(df, WATERLEVEL_TARGET_COLS)
    wl_ts_col = first_col(df, WATERLEVEL_TS_COLS)
    flow_mean_col = first_col(df, FLOW_MEAN_TARGET_COLS)
    flow_peak_col = first_col(df, FLOW_PEAK_TARGET_COLS)
    flow_ts_col = first_col(df, FLOW_TS_COLS)

    x_col = first_col(df, X_COLS)
    y_col = first_col(df, Y_COLS)
    x1_col = first_col(df, X1_COLS)
    y1_col = first_col(df, Y1_COLS)
    x2_col = first_col(df, X2_COLS)
    y2_col = first_col(df, Y2_COLS)

    records: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        kind = infer_kind(row)
        gauge_id = clean_text_cell(row.get(gauge_id_col, "") if gauge_id_col else "")
        line_id = clean_text_cell(row.get(line_id_col, "") if line_id_col else "")
        fallback_id = clean_text_cell(row.get(id_col, "") if id_col else "")
        gauge_name = clean_text_cell(row.get(name_col, "") if name_col else "")

        match_id = line_id if kind == "line" and line_id else gauge_id or fallback_id or f"gauge_{i + 1:03d}"

        if not gauge_id:
            gauge_id = fallback_id or match_id

        if not gauge_name:
            gauge_name = gauge_id or match_id

        rec = {
            "record_key": f"{kind}:{match_id}",
            "match_id": match_id,
            "line_id": line_id,
            "gauge_id": gauge_id,
            "gauge_name": gauge_name,
            "kind": kind,
            "time": pd.to_datetime(row.get(time_col), errors="coerce") if time_col else pd.NaT,
            "obs_wl_peak_m": as_float(row.get(wl_peak_col)) if wl_peak_col else None,
            "obs_wl_m": as_float(row.get(wl_ts_col)) if wl_ts_col else None,
            "obs_flow_mean_cms": as_float(row.get(flow_mean_col)) if flow_mean_col else None,
            "obs_flow_peak_cms": as_float(row.get(flow_peak_col)) if flow_peak_col else None,
            "obs_flow_cms": as_float(row.get(flow_ts_col)) if flow_ts_col else None,
            "usable_for_wl_error": (
                as_bool(row.get(usable_wl_col), default=(kind == "point"))
                if usable_wl_col
                else (kind == "point")
            ),
            "usable_for_flow_error": (
                as_bool(row.get(usable_flow_col), default=(kind == "line"))
                if usable_flow_col
                else (kind == "line")
            ),
            "x": first_float_from_row(row, X_COLS),
            "y": first_float_from_row(row, Y_COLS),
            "x1": first_float_from_row(row, X1_COLS),
            "y1": first_float_from_row(row, Y1_COLS),
            "x2": first_float_from_row(row, X2_COLS),
            "y2": first_float_from_row(row, Y2_COLS),
        }
        if rec["kind"] == "line":
            xs = [v for v in [rec["x1"], rec["x2"]] if v is not None]
            ys = [v for v in [rec["y1"], rec["y2"]] if v is not None]
            if rec["x"] is None and xs:
                rec["x"] = float(np.mean(xs))
            if rec["y"] is None and ys:
                rec["y"] = float(np.mean(ys))
        records.append(rec)
    return records


def group_validation(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for rec in records:
        key = str(rec.get("record_key") or f"{rec.get('kind')}:{rec.get('match_id') or rec.get('gauge_id')}")
        g = grouped.setdefault(
            key,
            {k: rec.get(k) for k in [
                "record_key", "match_id", "line_id", "gauge_id", "gauge_name", "kind",
                "x", "y", "x1", "y1", "x2", "y2",
                "usable_for_wl_error", "usable_for_flow_error",
            ]},
        )
        for key2 in ["obs_wl_peak_m", "obs_flow_mean_cms", "obs_flow_peak_cms"]:
            if g.get(key2) is None and rec.get(key2) is not None:
                g[key2] = rec.get(key2)
        if rec.get("time") is not pd.NaT and pd.notna(rec.get("time")):
            g.setdefault("timeseries", []).append({
                "time": rec.get("time"),
                "obs_wl_m": rec.get("obs_wl_m"),
                "obs_flow_cms": rec.get("obs_flow_cms"),
            })
    return grouped


def identifier_tokens(value: Any) -> set[str]:
    text = clean_text_cell(value).lower()

    if not text:
        return set()

    tokens = {text}

    compact = (
        text.replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".", "")
    )

    if compact:
        tokens.add(compact)

    digits = "".join(ch for ch in text if ch.isdigit())

    if digits:
        tokens.add(digits)

        if len(digits) == 7:
            tokens.add("0" + digits)

        if len(digits) == 8 and digits.startswith("0"):
            tokens.add(digits[1:])

    return {t for t in tokens if t}


def match_sim(record: dict[str, Any], sims: list[SimSeries], max_distance_m: float) -> tuple[SimSeries | None, str, float | None]:
    candidate_tokens: set[str] = set()

    for key in ["match_id", "line_id", "gauge_id", "gauge_name"]:
        candidate_tokens.update(identifier_tokens(record.get(key)))

    for sim in sims:
        sim_tokens = set()
        sim_tokens.update(identifier_tokens(sim.sim_id))
        sim_tokens.update(identifier_tokens(sim.name))

        if candidate_tokens and sim_tokens and candidate_tokens.intersection(sim_tokens):
            return sim, "id_or_name", 0.0

    x = as_float(record.get("x"))
    y = as_float(record.get("y"))

    if x is None or y is None:
        return None, "unmatched", None

    best = None
    best_dist = None

    for sim in sims:
        if sim.x is None or sim.y is None:
            continue

        d = math.hypot(float(sim.x) - x, float(sim.y) - y)

        if best_dist is None or d < best_dist:
            best = sim
            best_dist = d

    if best is not None and best_dist is not None and best_dist <= max_distance_m:
        return best, "nearest_xy", best_dist

    return None, "unmatched", best_dist

def nan_rmse(values: list[float]) -> float | None:
    arr = np.asarray([v for v in values if v is not None and math.isfinite(float(v))], dtype=float)
    if arr.size == 0:
        return None
    return float(np.sqrt(np.mean(arr ** 2)))


def nan_mae(values: list[float]) -> float | None:
    arr = np.asarray([v for v in values if v is not None and math.isfinite(float(v))], dtype=float)
    if arr.size == 0:
        return None
    return float(np.mean(np.abs(arr)))

def datetime64ns_array(values: Any) -> np.ndarray:
    raw = np.asarray(values).reshape(-1)
    parsed = pd.to_datetime(raw, errors="coerce")
    return parsed.to_numpy(dtype="datetime64[ns]")

def compare_timeseries(sim: SimSeries, ts_rows: list[dict[str, Any]], obs_key: str) -> float | None:
    rows = [r for r in ts_rows if r.get(obs_key) is not None and pd.notna(r.get("time"))]
    if not rows or sim.times is None:
        return None
    sim_times = datetime64ns_array(sim.times)
    sim_values = np.asarray(sim.values, dtype=float).reshape(-1)
    n = min(len(sim_times), len(sim_values))

    if n <= 0:
        return None

    sim_df = pd.DataFrame({
        "time": sim_times[:n],
        "sim": sim_values[:n],
    })

    obs_df = pd.DataFrame({
        "time": datetime64ns_array([r["time"] for r in rows]),
        "obs": [r[obs_key] for r in rows],
    })
    sim_df = sim_df.dropna().sort_values("time")
    obs_df = obs_df.dropna().sort_values("time")
    if sim_df.empty or obs_df.empty:
        return None
    joined = pd.merge_asof(obs_df, sim_df, on="time", direction="nearest", tolerance=pd.Timedelta("45min"))
    joined = joined.dropna(subset=["sim", "obs"])
    if joined.empty:
        return None
    err = joined["sim"].astype(float) - joined["obs"].astype(float)
    return float(np.sqrt(np.mean(np.square(err))))

def safe_abs_percent(error_value: Any, observed_value: Any) -> float | None:
    err = as_float(error_value)
    obs = as_float(observed_value)

    if err is None or obs is None or abs(obs) <= 1e-12:
        return None

    return float(100.0 * abs(err) / abs(obs))


def compare_timeseries_metrics(
    sim: SimSeries,
    ts_rows: list[dict[str, Any]],
    obs_key: str,
    use_abs_sim: bool = False,
) -> dict[str, Any]:
    rows = [r for r in ts_rows if r.get(obs_key) is not None and pd.notna(r.get("time"))]

    empty = {
        "pair_count": 0,
        "rmse": None,
        "mae": None,
        "mean_bias": None,
        "pbias_pct": None,
        "nse": None,
        "kge": None,
        "peak_timing_error_hr": None,
    }

    if not rows or sim.times is None:
        return empty

    sim_values = np.asarray(sim.values, dtype=float)
    if use_abs_sim:
        sim_values = np.abs(sim_values)

    sim_times = datetime64ns_array(sim.times)
    n = min(len(sim_times), len(sim_values))

    if n <= 0:
        return empty

    sim_df = pd.DataFrame({
        "time": sim_times[:n],
        "sim": sim_values[:n],
    })

    obs_df = pd.DataFrame({
        "time": datetime64ns_array([r["time"] for r in rows]),
        "obs": [r[obs_key] for r in rows],
    })

    sim_df = sim_df.dropna().sort_values("time")
    obs_df = obs_df.dropna().sort_values("time")

    if sim_df.empty or obs_df.empty:
        return empty

    joined = pd.merge_asof(
        obs_df,
        sim_df,
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta("45min"),
    )

    joined = joined.dropna(subset=["sim", "obs"])

    if joined.empty:
        return empty

    sim_arr = joined["sim"].astype(float).to_numpy()
    obs_arr = joined["obs"].astype(float).to_numpy()
    err = sim_arr - obs_arr

    out = dict(empty)
    out["pair_count"] = int(len(joined))
    out["rmse"] = float(np.sqrt(np.mean(err ** 2)))
    out["mae"] = float(np.mean(np.abs(err)))
    out["mean_bias"] = float(np.mean(err))

    obs_sum = float(np.sum(obs_arr))
    if abs(obs_sum) > 1e-12:
        out["pbias_pct"] = float(100.0 * np.sum(err) / obs_sum)

    obs_denom = float(np.sum((obs_arr - np.mean(obs_arr)) ** 2))
    if obs_denom > 1e-12:
        out["nse"] = float(1.0 - (np.sum(err ** 2) / obs_denom))

    obs_mean = float(np.mean(obs_arr))
    sim_mean = float(np.mean(sim_arr))
    obs_std = float(np.std(obs_arr))
    sim_std = float(np.std(sim_arr))

    if len(joined) >= 2 and obs_std > 1e-12 and abs(obs_mean) > 1e-12:
        r = float(np.corrcoef(sim_arr, obs_arr)[0, 1])
        alpha = sim_std / obs_std
        beta = sim_mean / obs_mean

        if np.isfinite(r) and np.isfinite(alpha) and np.isfinite(beta):
            out["kge"] = float(1.0 - np.sqrt((r - 1.0) ** 2 + (alpha - 1.0) ** 2 + (beta - 1.0) ** 2))

    try:
        obs_peak_idx = int(np.nanargmax(obs_arr))
        sim_peak_idx = int(np.nanargmax(sim_arr))
        obs_peak_time = pd.to_datetime(joined.iloc[obs_peak_idx]["time"])
        sim_peak_time = pd.to_datetime(joined.iloc[sim_peak_idx]["time"])
        out["peak_timing_error_hr"] = float((sim_peak_time - obs_peak_time).total_seconds() / 3600.0)
    except Exception:
        pass

    return out

def json_float(value: Any) -> float | None:
    v = as_float(value)
    return float(v) if v is not None else None


def time_to_iso(value: Any) -> str:
    try:
        ts = pd.to_datetime(value)
        if pd.isna(ts):
            return str(value)
        return ts.isoformat()
    except Exception:
        return str(value)


def clean_series_values(values: Any, use_abs: bool = False) -> list[float | None]:
    arr = np.asarray(values, dtype=float).reshape(-1)

    if use_abs:
        arr = np.abs(arr)

    out: list[float | None] = []
    for value in arr:
        out.append(float(value) if np.isfinite(value) else None)

    return out


def align_observed_series_to_sim(
    sim: SimSeries,
    ts_rows: list[dict[str, Any]],
    obs_key: str,
) -> list[float | None] | None:
    if sim.times is None:
        return None

    rows = [
        r for r in ts_rows
        if r.get(obs_key) is not None and pd.notna(r.get("time"))
    ]

    if not rows:
        return None

    try:
        sim_times = datetime64ns_array(sim.times)

        sim_df = pd.DataFrame({
            "time": sim_times,
            "_order": np.arange(len(sim_times)),
        })

        obs_df = pd.DataFrame({
            "time": datetime64ns_array([r["time"] for r in rows]),
            "obs": [r.get(obs_key) for r in rows],
        })

        obs_df["obs"] = pd.to_numeric(obs_df["obs"], errors="coerce")
        sim_df = sim_df.dropna(subset=["time"]).sort_values("time")
        obs_df = obs_df.dropna(subset=["time", "obs"]).sort_values("time")

        if sim_df.empty or obs_df.empty:
            return None

        joined = pd.merge_asof(
            sim_df,
            obs_df,
            on="time",
            direction="nearest",
            tolerance=pd.Timedelta("45min"),
        ).sort_values("_order")

        values = [json_float(v) for v in joined["obs"].tolist()]
        return values if any(v is not None for v in values) else None

    except Exception:
        return None


def build_gauge_timeseries_item(
    row: dict[str, Any],
    rec: dict[str, Any],
    sim: SimSeries | None,
) -> dict[str, Any] | None:
    if sim is None or sim.times is None:
        return None

    raw_times = list(np.asarray(sim.times).reshape(-1))
    raw_values = np.asarray(sim.values, dtype=float).reshape(-1)
    n = min(len(raw_times), len(raw_values))

    if n <= 0:
        return None

    kind = str(row.get("kind") or "point").lower()
    is_line = kind == "line"
    obs_key = "obs_flow_cms" if is_line else "obs_wl_m"

    time_values = [time_to_iso(v) for v in raw_times[:n]]
    sim_values = clean_series_values(raw_values[:n], use_abs=is_line)

    obs_values = align_observed_series_to_sim(
        sim=sim,
        ts_rows=rec.get("timeseries", []),
        obs_key=obs_key,
    )

    if obs_values is not None:
        obs_values = obs_values[:n]
        if len(obs_values) < n:
            obs_values = obs_values + [None] * (n - len(obs_values))

    if is_line:
        note = (
            "Showing simulated CRS discharge over time. "
            "Observed flow hydrograph is overlaid when the validation CSV contains observed flow time-series rows; "
            "otherwise scalar observed mean/peak references are shown."
        )
        metric = "flow"
        unit = "m³/s"
    else:
        note = (
            "Showing simulated point water level over time. "
            "Observed WL hydrograph is overlaid when the validation CSV contains observed WL time-series rows; "
            "otherwise scalar observed peak WL is shown."
        )
        metric = "water_level"
        unit = "m NAVD88"

    return {
        "record_key": row.get("record_key"),
        "kind": "line" if is_line else "point",
        "gauge_id": row.get("gauge_id"),
        "line_id": row.get("line_id"),
        "match_id": row.get("match_id"),
        "gauge_name": row.get("gauge_name"),
        "sim_id": row.get("sim_id"),
        "sim_variable": row.get("sim_variable"),
        "metric": metric,
        "unit": unit,
        "time": time_values,
        "sim": sim_values,
        "obs": obs_values,
        "obs_peak": row.get("obs_flow_peak_cms") if is_line else row.get("obs_wl_peak_m"),
        "obs_mean": row.get("obs_flow_mean_cms") if is_line else None,
        "sim_peak": row.get("sim_flow_peak_cms") if is_line else row.get("sim_wl_peak_m"),
        "sim_mean": row.get("sim_flow_mean_cms") if is_line else None,
        "note": note,
    }


def severity_score(row: dict[str, Any], wl_bad_m: float, flow_bad_cms: float) -> float | None:
    parts = []
    if row.get("wl_error_m") is not None and wl_bad_m > 0:
        parts.append(abs(float(row["wl_error_m"])) / wl_bad_m)
    if row.get("flow_mean_error_cms") is not None and flow_bad_cms > 0:
        parts.append(abs(float(row["flow_mean_error_cms"])) / flow_bad_cms)
    if row.get("flow_peak_error_cms") is not None and flow_bad_cms > 0:
        parts.append(abs(float(row["flow_peak_error_cms"])) / flow_bad_cms)
    if not parts:
        return None
    return float(max(parts))


def severity_label(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 0.35:
        return "good"
    if score < 0.75:
        return "ok"
    if score < 1.25:
        return "bad"
    return "worst"


def build_heatmap(rows: list[dict[str, Any]], out_path: Path) -> str | None:
    if plt is None:
        return "matplotlib is unavailable"
    pts = [r for r in rows if r.get("x") is not None and r.get("y") is not None and r.get("severity_score") is not None]
    if not pts:
        return "No x/y gauge coordinates with severity scores were available."
    x = np.asarray([r["x"] for r in pts], dtype=float)
    y = np.asarray([r["y"] for r in pts], dtype=float)
    sev = np.asarray([r["severity_score"] for r in pts], dtype=float)
    labels = [str(r.get("gauge_id") or "") for r in pts]

    fig, ax = plt.subplots(figsize=(9, 7), dpi=160)
    sc = ax.scatter(x, y, c=sev, s=90, edgecolors="black", linewidths=0.4)
    for xi, yi, lab in zip(x, y, labels):
        ax.text(xi, yi, lab, fontsize=6, ha="left", va="bottom")
    ax.set_title("Obs/gauge validation error severity")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal", adjustable="datalim")
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label("severity score")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return None

def _first_existing_var(ds: xr.Dataset, names: list[str]) -> str | None:
    for name in names:
        if name in ds:
            return name
        if name in ds.coords:
            return name
    return None


def read_map_extent(run_root: Path) -> dict[str, Any] | None:
    manifest_path = run_root / "review" / "maps" / "layers_manifest.json"

    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            frame = manifest.get("map_frame")

            if isinstance(frame, dict):
                xmin = as_float(frame.get("xmin"))
                xmax = as_float(frame.get("xmax"))
                ymin = as_float(frame.get("ymin"))
                ymax = as_float(frame.get("ymax"))

                if (
                    xmin is not None
                    and xmax is not None
                    and ymin is not None
                    and ymax is not None
                    and xmax > xmin
                    and ymax > ymin
                ):
                    return {
                        "xmin": xmin,
                        "xmax": xmax,
                        "ymin": ymin,
                        "ymax": ymax,
                        "image": frame.get("image"),
                        "data_extent": frame.get("data_extent"),
                        "pad_frac": frame.get("pad_frac"),
                        "aspect": frame.get("aspect"),
                        "source": "review/maps/layers_manifest.json map_frame",
                    }
        except Exception:
            pass

    map_nc = run_root / "model" / "sfincs_map.nc"

    if not map_nc.exists():
        return None

    try:
        ds = xr.open_dataset(map_nc)
    except Exception:
        return None

    try:
        x_name = _first_existing_var(ds, ["x", "xc", "grid_x", "mesh2d_face_x", "lon"])
        y_name = _first_existing_var(ds, ["y", "yc", "grid_y", "mesh2d_face_y", "lat"])

        if not x_name or not y_name:
            return None

        x = np.asarray(ds[x_name].values, dtype=float)
        y = np.asarray(ds[y_name].values, dtype=float)

        x = x[np.isfinite(x)]
        y = y[np.isfinite(y)]

        if x.size == 0 or y.size == 0:
            return None

        return {
            "xmin": float(np.nanmin(x)),
            "xmax": float(np.nanmax(x)),
            "ymin": float(np.nanmin(y)),
            "ymax": float(np.nanmax(y)),
            "x_name": str(x_name),
            "y_name": str(y_name),
            "source": "fallback model/sfincs_map.nc raw extent",
        }
    finally:
        try:
            ds.close()
        except Exception:
            pass

def ensure_static_map_overlays(
    run_root: Path,
    notes: list[str],
    force: bool = False,
    require_error_surfaces: bool = False,
) -> dict[str, str | None]:
    maps_dir = run_root / MAPS_DIR_REL
    satellite = run_root / SATELLITE_REL
    active_area = run_root / ACTIVE_AREA_REL
    context_map = run_root / CONTEXT_MAP_REL
    manifest_path = maps_dir / "layers_manifest.json"

    def manifest_lists_context_map() -> bool:
        if not manifest_path.exists():
            return False

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return False

        overlays = manifest.get("optional_overlays", {})
        if not isinstance(overlays, dict):
            return False

        item = overlays.get("obs_gauge_context_map")
        if not isinstance(item, dict):
            return False

        relpath = str(item.get("relpath", "") or "").strip()
        return bool(relpath) and (run_root / relpath).exists()

    need_rebuild = (
        force
        or not satellite.exists()
        or not active_area.exists()
        or not context_map.exists()
        or not manifest_lists_context_map()
        or (
            require_error_surfaces
            and (
                not (run_root / FLOW_ERROR_SURFACE_REL).exists()
                or not (run_root / WL_ERROR_SURFACE_REL).exists()
            )
        )
    )

    if not need_rebuild:
        return {
            "satellite_background": SATELLITE_REL.as_posix() if satellite.exists() else None,
            "model_active_area": ACTIVE_AREA_REL.as_posix() if active_area.exists() else None,
            "obs_gauge_context_map": CONTEXT_MAP_REL.as_posix() if context_map.exists() else None,
            "obs_flow_error_surface": FLOW_ERROR_SURFACE_REL.as_posix() if (run_root / FLOW_ERROR_SURFACE_REL).exists() else None,
            "obs_wl_error_surface": WL_ERROR_SURFACE_REL.as_posix() if (run_root / WL_ERROR_SURFACE_REL).exists() else None,
        }

    contextily_py = PIPELINE_ROOT / "envs" / "sfincs_contextily" / "bin" / "python"
    py = contextily_py if contextily_py.exists() else Path(sys.executable)
    builder = PIPELINE_ROOT / "code" / "review_prepare_maps.py"

    if not builder.exists():
        notes.append(f"Static map builder not found: {builder}")
        return {
            "satellite_background": SATELLITE_REL.as_posix() if satellite.exists() else None,
            "model_active_area": ACTIVE_AREA_REL.as_posix() if active_area.exists() else None,
            "obs_gauge_context_map": CONTEXT_MAP_REL.as_posix() if context_map.exists() else None,
            "obs_flow_error_surface": FLOW_ERROR_SURFACE_REL.as_posix() if (run_root / FLOW_ERROR_SURFACE_REL).exists() else None,
            "obs_wl_error_surface": WL_ERROR_SURFACE_REL.as_posix() if (run_root / WL_ERROR_SURFACE_REL).exists() else None,
        }

    try:
        proc = subprocess.run(
            [str(py), str(builder), str(run_root), "--force"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=1200,
        )

        if proc.returncode != 0:
            notes.append(
                "Tried to force-build static map/context-map products for Obs/Gauges, "
                "but review_prepare_maps.py failed. "
                f"STDOUT: {proc.stdout[-1200:]} STDERR: {proc.stderr[-1200:]}"
            )
        else:
            notes.append("Force-built static map/context-map products for Obs/Gauges.")

    except Exception as exc:
        notes.append(
            "Tried to force-build static map/context-map products for Obs/Gauges, "
            f"but failed: {type(exc).__name__}: {exc}"
        )

    return {
        "satellite_background": SATELLITE_REL.as_posix() if satellite.exists() else None,
        "model_active_area": ACTIVE_AREA_REL.as_posix() if active_area.exists() else None,
        "obs_gauge_context_map": CONTEXT_MAP_REL.as_posix() if context_map.exists() else None,
        "obs_flow_error_surface": FLOW_ERROR_SURFACE_REL.as_posix() if (run_root / FLOW_ERROR_SURFACE_REL).exists() else None,
        "obs_wl_error_surface": WL_ERROR_SURFACE_REL.as_posix() if (run_root / WL_ERROR_SURFACE_REL).exists() else None,
    }


def build_point_map_records(rows: list[dict[str, Any]], extent: dict[str, float] | None) -> list[dict[str, Any]]:
    if not extent:
        return []

    def gauge_key(value: Any) -> str:
        text = str(value or "").strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) == 7:
            digits = "0" + digits
        return digits or text

    xmin = float(extent["xmin"])
    xmax = float(extent["xmax"])
    ymin = float(extent["ymin"])
    ymax = float(extent["ymax"])

    dx = xmax - xmin
    dy = ymax - ymin

    if dx <= 0 or dy <= 0:
        return []

    line_by_gauge: dict[str, dict[str, Any]] = {}

    for row in rows:
        if str(row.get("kind", "")).lower() != "line":
            continue

        key = gauge_key(row.get("gauge_id") or row.get("match_id"))
        if not key:
            continue

        line_by_gauge[key] = row

    out = []

    for row in rows:
        if str(row.get("kind", "")).lower() != "point":
            continue

        x = as_float(row.get("x"))
        y = as_float(row.get("y"))

        if x is None or y is None:
            continue

        left_pct = 100.0 * (float(x) - xmin) / dx
        top_pct = 100.0 * (1.0 - ((float(y) - ymin) / dy))

        if not np.isfinite(left_pct) or not np.isfinite(top_pct):
            continue

        if left_pct < -5 or left_pct > 105 or top_pct < -5 or top_pct > 105:
            continue

        key = gauge_key(row.get("gauge_id") or row.get("match_id"))
        paired_line = line_by_gauge.get(key, {})

        out.append({
            "gauge_id": row.get("gauge_id"),
            "gauge_name": row.get("gauge_name"),
            "x": float(x),
            "y": float(y),
            "left_pct": float(left_pct),
            "top_pct": float(top_pct),
            "sim_wl_peak_m": row.get("sim_wl_peak_m"),
            "paired_line_id": paired_line.get("line_id") or paired_line.get("match_id"),
            "flow_mean_error_cms": paired_line.get("flow_mean_error_cms"),
            "flow_peak_error_cms": paired_line.get("flow_peak_error_cms"),
        })

    return out



def build_line_map_records(rows: list[dict[str, Any]], extent: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not extent:
        return []

    xmin = float(extent["xmin"])
    xmax = float(extent["xmax"])
    ymin = float(extent["ymin"])
    ymax = float(extent["ymax"])

    dx = xmax - xmin
    dy = ymax - ymin

    if dx <= 0 or dy <= 0:
        return []

    out = []

    for row in rows:
        if str(row.get("kind", "")).lower() != "line":
            continue

        x = as_float(row.get("x"))
        y = as_float(row.get("y"))

        if x is None or y is None:
            x1 = as_float(row.get("x1"))
            y1 = as_float(row.get("y1"))
            x2 = as_float(row.get("x2"))
            y2 = as_float(row.get("y2"))

            if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                x = (x1 + x2) / 2.0
                y = (y1 + y2) / 2.0

        if x is None or y is None:
            continue

        left_pct = 100.0 * (float(x) - xmin) / dx
        top_pct = 100.0 * (1.0 - ((float(y) - ymin) / dy))

        if not np.isfinite(left_pct) or not np.isfinite(top_pct):
            continue

        if left_pct < -5 or left_pct > 105 or top_pct < -5 or top_pct > 105:
            continue

        out.append({
            "gauge_id": row.get("gauge_id"),
            "gauge_name": row.get("gauge_name"),
            "line_id": row.get("line_id") or row.get("match_id"),
            "x": float(x),
            "y": float(y),
            "left_pct": float(left_pct),
            "top_pct": float(top_pct),
            "flow_mean_error_cms": row.get("flow_mean_error_cms"),
            "flow_peak_error_cms": row.get("flow_peak_error_cms"),
        })

    return out


def build_products(run_root: Path, validation_csv: Path | None, force: bool, max_match_distance_m: float, wl_bad_m: float, flow_bad_cms: float) -> dict[str, Any]:
    out_dir = run_root / PRODUCT_REL
    status_path = out_dir / STATUS_NAME
    write_json(status_path, {
        "state": "running",
        "message": "Obs/gauge validation products are being built.",
        "updated_at": now_iso(),
    })

    notes: list[str] = []
    validation_path, discover_notes = discover_validation_csv(run_root, str(validation_csv) if validation_csv else None)
    notes.extend(discover_notes)
    if validation_path is None:
        raise FileNotFoundError(
            "No gauge validation CSV found. Expected either an explicitly selected validation CSV, "
            "an explicitly selected validation folder containing one top-level CSV, or a top-level CSV "
            "inside event_validation_gauges/. Files inside _misc are ignored."
        )

    his_path = run_root / "model" / "sfincs_his.nc"
    if not his_path.exists():
        raise FileNotFoundError(f"Missing model/sfincs_his.nc: {his_path}")

    df = load_validation(validation_path)
    records = make_validation_records(df)
    grouped = group_validation(records)

    validation_has_ts = validation_dataframe_has_timeseries(df)

    observed_ts_path: Path | None = None
    observed_ts_records: list[dict[str, Any]] = []
    observed_ts_attached = 0

    if validation_has_ts:
        observed_ts_path = validation_path
        observed_ts_attached = count_observed_timeseries_rows(records)
        notes.append(
            f"Validation CSV is long-format observed time series: {validation_path} "
            f"rows={len(records)} observed_time_rows={observed_ts_attached}"
        )

    else:
        observed_ts_path = discover_observed_timeseries_csv(run_root, validation_path)

        if observed_ts_path is not None:
            observed_ts_records = load_observed_timeseries(observed_ts_path)
            observed_ts_attached = attach_observed_timeseries(grouped, observed_ts_records)
            notes.append(
                f"Observed gauge time-series loaded: {observed_ts_path} "
                f"rows={len(observed_ts_records)} attached={observed_ts_attached}"
            )
        else:
            notes.append(
                "No observed gauge time-series CSV was found; selected-gauge chart will show "
                "simulated history plus scalar observed references only."
            )

    finalize_grouped_observed_scalars(grouped)

    ds = xr.open_dataset(his_path)
    point_var = choose_var(ds, POINT_SIM_VARS, require_time=True)
    line_var = choose_var(ds, LINE_SIM_VARS, require_time=True)

    # Build/read the static map frame early so point/line browser percentages can be computed.
    # Do not require Obs/Gauges error surfaces here because fresh metrics have not been written yet.
    overlay_files = ensure_static_map_overlays(
        run_root,
        notes,
        force=False,
        require_error_surfaces=False,
    )
    map_extent = read_map_extent(run_root)

    point_sims = extract_sim_series(ds, point_var, "point") if point_var else []
    line_sims = extract_sim_series(ds, line_var, "line") if line_var else []

    if not point_var:
        notes.append("No point water-level variable was identified in sfincs_his.nc.")
    if not line_var:
        notes.append("No line/cross-section discharge variable was identified in sfincs_his.nc.")

    rows: list[dict[str, Any]] = []
    timeseries_items: list[dict[str, Any]] = []
    for record_key, rec in grouped.items():
        kind = str(rec.get("kind") or "point").lower()
        sims = line_sims if kind == "line" else point_sims
        sim, match_method, match_distance = match_sim(rec, sims, max_distance_m=max_match_distance_m)

        row: dict[str, Any] = {
            "record_key": record_key,
            "gauge_id": rec.get("gauge_id") or rec.get("match_id") or record_key,
            "line_id": rec.get("line_id"),
            "match_id": rec.get("match_id"),
            "gauge_name": rec.get("gauge_name") or rec.get("gauge_id") or record_key,
            "kind": "line" if kind == "line" else "point",
            "x": rec.get("x"),
            "y": rec.get("y"),
            "match_method": match_method,
            "match_distance_m": match_distance,
            "sim_index": sim.index if sim else None,
            "sim_id": sim.sim_id if sim else None,
            "sim_variable": line_var if kind == "line" else point_var,
            "obs_wl_peak_m": rec.get("obs_wl_peak_m"),
            "obs_flow_mean_cms": rec.get("obs_flow_mean_cms"),
            "obs_flow_peak_cms": rec.get("obs_flow_peak_cms"),
            "usable_for_wl_error": as_bool(rec.get("usable_for_wl_error"), default=True),
            "usable_for_flow_error": as_bool(rec.get("usable_for_flow_error"), default=True),
            "quality_flag": "unmatched" if sim is None else "matched",
        }
        
        if sim is not None:
            if row["x"] is None and sim.x is not None:
                row["x"] = float(sim.x)

            if row["y"] is None and sim.y is not None:
                row["y"] = float(sim.y)

        if sim is not None:
            finite = np.asarray(sim.values, dtype=float)
            finite = finite[np.isfinite(finite)]
            if finite.size:
                if row["kind"] == "point":
                    row["sim_wl_peak_m"] = float(np.nanmax(finite))
                    if row.get("obs_wl_peak_m") is not None and row.get("usable_for_wl_error"):
                        row["wl_error_m"] = float(row["sim_wl_peak_m"] - float(row["obs_wl_peak_m"]))
                    row["wl_rmse_m"] = compare_timeseries(sim, rec.get("timeseries", []), "obs_wl_m")
                else:
                    metric_values = np.abs(finite)
                    row["sim_flow_mean_cms"] = float(np.nanmean(metric_values))
                    row["sim_flow_peak_cms"] = float(np.nanmax(metric_values))
                    row["sim_flow_signed_min_cms"] = float(np.nanmin(finite))
                    row["sim_flow_signed_max_cms"] = float(np.nanmax(finite))
                    if row.get("obs_flow_mean_cms") is not None and row.get("usable_for_flow_error"):
                        row["flow_mean_error_cms"] = float(row["sim_flow_mean_cms"] - float(row["obs_flow_mean_cms"]))
                    if row.get("obs_flow_peak_cms") is not None and row.get("usable_for_flow_error"):
                        row["flow_peak_error_cms"] = float(row["sim_flow_peak_cms"] - float(row["obs_flow_peak_cms"]))
                    row["flow_mean_error_pct"] = safe_abs_percent(
                        row.get("flow_mean_error_cms"),
                        row.get("obs_flow_mean_cms"),
                    )

                    row["flow_peak_error_pct"] = safe_abs_percent(
                        row.get("flow_peak_error_cms"),
                        row.get("obs_flow_peak_cms"),
                    )

                    flow_ts = compare_timeseries_metrics(
                        sim,
                        rec.get("timeseries", []),
                        "obs_flow_cms",
                        use_abs_sim=True,
                    )

                    row["flow_timeseries_pair_count"] = flow_ts.get("pair_count")
                    row["flow_rmse_cms"] = flow_ts.get("rmse")
                    row["flow_mae_cms"] = flow_ts.get("mae")
                    row["flow_timeseries_bias_cms"] = flow_ts.get("mean_bias")
                    row["flow_pbias_pct"] = flow_ts.get("pbias_pct")
                    row["flow_nse"] = flow_ts.get("nse")
                    row["flow_kge"] = flow_ts.get("kge")
                    row["flow_peak_timing_error_hr"] = flow_ts.get("peak_timing_error_hr")
            else:
                row["quality_flag"] = "matched_no_finite_sim_values"

        row["severity_score"] = severity_score(row, wl_bad_m=wl_bad_m, flow_bad_cms=flow_bad_cms)
        row["severity_label"] = severity_label(row["severity_score"])

        ts_item = build_gauge_timeseries_item(row, rec, sim)
        if ts_item is not None:
            timeseries_items.append(ts_item)

        rows.append(row)

    point_map = build_point_map_records(rows, map_extent)
    line_map = build_line_map_records(rows, map_extent)
    
    wl_errors = [r.get("wl_error_m") for r in rows if r.get("wl_error_m") is not None]
    flow_mean_errors = [r.get("flow_mean_error_cms") for r in rows if r.get("flow_mean_error_cms") is not None]
    flow_peak_errors = [r.get("flow_peak_error_cms") for r in rows if r.get("flow_peak_error_cms") is not None]
    wl_ts_rmses = [r.get("wl_rmse_m") for r in rows if r.get("wl_rmse_m") is not None]
    flow_ts_rmses = [r.get("flow_rmse_cms") for r in rows if r.get("flow_rmse_cms") is not None]

    worst = None
    scored = [r for r in rows if r.get("severity_score") is not None]
    if scored:
        worst = max(scored, key=lambda r: float(r["severity_score"]))



    overall = {
        "gauge_count": len(rows),
        "matched_count": sum(1 for r in rows if str(r.get("quality_flag", "")).startswith("matched")),
        "unmatched_count": sum(1 for r in rows if r.get("quality_flag") == "unmatched"),
        "point_count": sum(1 for r in rows if r.get("kind") == "point"),
        "line_count": sum(1 for r in rows if r.get("kind") == "line"),
        "waterlevel_rmse_m": nan_rmse(wl_errors),
        "waterlevel_mae_m": nan_mae(wl_errors),
        "waterlevel_timeseries_rmse_mean_m": float(np.nanmean(wl_ts_rmses)) if wl_ts_rmses else None,
        "flow_mean_rmse_cms": nan_rmse(flow_mean_errors),
        "flow_mean_mae_cms": nan_mae(flow_mean_errors),
        "flow_peak_rmse_cms": nan_rmse(flow_peak_errors),
        "flow_peak_mae_cms": nan_mae(flow_peak_errors),
        "flow_timeseries_rmse_mean_cms": float(np.nanmean(flow_ts_rmses)) if flow_ts_rmses else None,
        "worst_gauge_id": worst.get("gauge_id") if worst else None,
        "worst_gauge_name": worst.get("gauge_name") if worst else None,
        "worst_severity_score": worst.get("severity_score") if worst else None,
        "thresholds": {
            "wl_bad_m": wl_bad_m,
            "flow_bad_cms": flow_bad_cms,
            "max_match_distance_m": max_match_distance_m,
        },
    }

    heatmap_error = build_heatmap(rows, out_dir / HEATMAP_NAME)
    if heatmap_error:
        notes.append(heatmap_error)

    metrics = {
        "ok": True,
        "created_at": now_iso(),
        "run_name": run_root.name,
        "run_root": str(run_root),
        "validation_csv": str(validation_path),
        "validation_csv_sha256": file_sha256(validation_path),
        "observed_timeseries_csv": str(observed_ts_path) if observed_ts_path is not None else None,
        "observed_timeseries_rows": len(observed_ts_records) if observed_ts_records else observed_ts_attached,
        "observed_timeseries_rows_attached": observed_ts_attached,
        "validation_csv_long_format": validation_has_ts,
        "sfincs_his": str(his_path),
        "sfincs_his_size_bytes": his_path.stat().st_size,
        "variables": {
            "point_waterlevel": point_var,
            "line_discharge": line_var,
        },
        "overall": overall,
        "gauges": rows,
        "notes": notes,
        "timeseries": {
            "relpath": str((PRODUCT_REL / TIMESERIES_NAME).as_posix()),
            "item_count": len(timeseries_items),
        },
        "map_view": {
            "extent": map_extent,
            "overlays": overlay_files,
            "points": point_map,
            "lines": line_map,
        },
    }

    timeseries_product = {
        "ok": True,
        "created_at": now_iso(),
        "run_name": run_root.name,
        "run_root": str(run_root),
        "source": "model/sfincs_his.nc plus optional validation CSV time-series rows",
        "item_count": len(timeseries_items),
        "items": timeseries_items,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / GAUGE_CSV_NAME, index=False)
    write_json(out_dir / METRICS_NAME, metrics)

    # Now that fresh Obs/Gauges metrics exist on disk, force the map builder once more.
    # This is the pass that can build/register:
    #   review/maps/obs_flow_error_surface.png
    #   review/maps/obs_wl_error_surface.png
    overlay_files = ensure_static_map_overlays(
        run_root,
        notes,
        force=True,
        require_error_surfaces=True,
    )

    # Refresh map frame and browser-coordinate records after the map rebuild, in case the
    # manifest/map_frame was created or updated by review_prepare_maps.py.
    refreshed_extent = read_map_extent(run_root)
    if refreshed_extent is not None:
        map_extent = refreshed_extent
        point_map = build_point_map_records(rows, map_extent)
        line_map = build_line_map_records(rows, map_extent)

    metrics["notes"] = notes
    metrics["map_view"] = {
        "extent": map_extent,
        "overlays": overlay_files,
        "points": point_map,
        "lines": line_map,
    }

    write_json(out_dir / METRICS_NAME, metrics)
    write_json(out_dir / DIALS_NAME, {"gauges": rows, "overall": overall})
    write_json(out_dir / TIMESERIES_NAME, timeseries_product)



    manifest = {
        "ok": True,
        "created_at": now_iso(),
        "product": "obs_gauges",
        "run": run_root.name,
        "files": {
            "status": str((PRODUCT_REL / STATUS_NAME).as_posix()),
            "metrics": str((PRODUCT_REL / METRICS_NAME).as_posix()),
            "manifest": str((PRODUCT_REL / MANIFEST_NAME).as_posix()),
            "gauge_metrics_csv": str((PRODUCT_REL / GAUGE_CSV_NAME).as_posix()),
            "gauge_dials": str((PRODUCT_REL / DIALS_NAME).as_posix()),
            "timeseries": str((PRODUCT_REL / TIMESERIES_NAME).as_posix()),
            "heatmap": str((PRODUCT_REL / HEATMAP_NAME).as_posix()) if (out_dir / HEATMAP_NAME).exists() else None,
            "context_map": CONTEXT_MAP_REL.as_posix() if (run_root / CONTEXT_MAP_REL).exists() else None,
            "obs_flow_error_surface": FLOW_ERROR_SURFACE_REL.as_posix() if (run_root / FLOW_ERROR_SURFACE_REL).exists() else None,
            "obs_wl_error_surface": WL_ERROR_SURFACE_REL.as_posix() if (run_root / WL_ERROR_SURFACE_REL).exists() else None,
        },
        "overall": overall,
    }
    write_json(out_dir / MANIFEST_NAME, manifest)
    write_json(status_path, {
        "state": "ready",
        "message": "Obs/gauge validation products are ready.",
        "updated_at": now_iso(),
        "manifest": str((PRODUCT_REL / MANIFEST_NAME).as_posix()),
        "metrics": str((PRODUCT_REL / METRICS_NAME).as_posix()),
        "timeseries": str((PRODUCT_REL / TIMESERIES_NAME).as_posix()),
        "validation_csv": str(validation_path),
        "observed_timeseries_csv": str(observed_ts_path) if observed_ts_path is not None else None,
        "observed_timeseries_rows": len(observed_ts_records) if observed_ts_records else observed_ts_attached,
        "observed_timeseries_rows_attached": observed_ts_attached,
        "validation_csv_long_format": validation_has_ts,
        "gauge_count": len(rows),
        "matched_count": overall["matched_count"],
        "unmatched_count": overall["unmatched_count"],
    })
    return {"ok": True, "status": _read_json(status_path), "manifest": manifest, "metrics": metrics}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", help="SFINCS run folder")
    parser.add_argument("--validation-csv", default="", help="Optional gauge validation CSV path")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-match-distance-m", type=float, default=250.0)
    parser.add_argument("--wl-bad-m", type=float, default=1.0)
    parser.add_argument("--flow-bad-cms", type=float, default=1000.0)
    args = parser.parse_args()

    run_root = Path(args.run_root).expanduser().resolve()
    out_dir = run_root / PRODUCT_REL
    status_path = out_dir / STATUS_NAME

    try:
        result = build_products(
            run_root=run_root,
            validation_csv=Path(args.validation_csv) if args.validation_csv else None,
            force=args.force,
            max_match_distance_m=args.max_match_distance_m,
            wl_bad_m=args.wl_bad_m,
            flow_bad_cms=args.flow_bad_cms,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0
    except Exception as exc:
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(status_path, {
            "state": "failed",
            "message": "Obs/gauge validation job failed.",
            "updated_at": now_iso(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        print(json.dumps({"ok": False, "error": str(exc), "status": _read_json(status_path)}, indent=2, default=str))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
