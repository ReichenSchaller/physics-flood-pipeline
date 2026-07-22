#!/usr/bin/env python
# coding: utf-8

"""
Author: Reichen Schaller (epsilon@unc.edu)
SFINCS / HydroMT-SFINCS post-processing stage.

This file is NOT meant to be edited by normal users.
Users edit sfincs_launcher.py. The launcher writes run_config.json and submits
this script as Slurm job 3, after the SFINCS solver job completes successfully.

Purpose
-------
Read SFINCS raw outputs and create a first-layer QA/QC postprocess folder:

- run_summary.txt
- run_summary.json
- output_variables.txt
- quicklook PNG maps when possible
- observation hydrograph PNGs when possible
- postprocess_failed.json if anything critical fails

This is intentionally not the final science-analysis layer. It is the boring,
useful layer that answers:

- Did SFINCS produce readable output?
- What variables and dimensions are present?
- What are the basic max/min values?
- Can we make quicklook maps for water level / flood depth?
- Did observation/history output exist?

Important regular vs subgrid note
---------------------------------
For regular SFINCS models, h/hmax may be available directly in sfincs_map.nc.
For subgrid SFINCS models, hmax may not be present; zs/zsmax water levels may be
present instead. Proper subgrid flood depth mapping should downscale zsmax onto a
higher-resolution elevation raster such as subgrid/dep_subgrid.tif or gis/dep.tif.

This script tries to do the safe thing:

1. Use hmax/max-depth variables directly when available.
2. If subgrid output has zsmax, try HydroMT-SFINCS utils.downscale_floodmap.
3. If downscaling is not possible, optionally create a coarse approximate depth
   from max water level minus bed level and clearly mark it as approximate.

The script should exit nonzero only if the raw SFINCS output cannot be read or
basic postprocessing cannot complete at all.
"""

from __future__ import annotations

import json
import math
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional


# ============================================================
# SMALL UTILS
# ============================================================


def normalize_basemap_zoomlevel_global(value):

    """Normalize postprocess_basemap_zoomlevel at module/global scope.



    Accepts auto/Auto/AUTO/etc. as "auto".

    Numeric strings become numbers. Blank/None become "auto".

    """

    if value is None:

        return "auto"



    if isinstance(value, str):

        value = value.strip()

        if not value:

            return "auto"

        if value.lower() == "auto":

            return "auto"



        try:

            number = float(value)

        except ValueError:

            return value



        return int(number) if number.is_integer() else number



    return value





def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def json_safe(obj: Any) -> Any:
    """Convert common Python/xarray/numpy objects to JSON-safe values."""
    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [json_safe(v) for v in obj]

    if isinstance(obj, tuple):
        return [json_safe(v) for v in obj]

    # numpy arrays, pandas indexes, xarray coordinate values, etc.
    if hasattr(obj, "tolist"):
        try:
            return obj.tolist()
        except Exception:
            pass

    # numpy scalar values
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass

    # Final fallback for weird metadata objects
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)

def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(json_safe(data), f, indent=2)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cfg_get(cfg: dict[str, Any], key: str, default: Any = None) -> Any:
    return cfg.get(key, default)


def cfg_path(cfg: dict[str, Any], key: str, default: Optional[str] = None) -> Optional[Path]:
    value = cfg.get(key, default)
    if value is None or str(value).strip() == "":
        return None
    return Path(value)


def run_root(cfg: dict[str, Any]) -> Path:
    return Path(cfg["output_root"]) / cfg["run_name"]


def model_root(cfg: dict[str, Any]) -> Path:
    return run_root(cfg) / "model"


def postprocess_root(cfg: dict[str, Any]) -> Path:
    return run_root(cfg) / "postprocess"


def postprocess_failure_path(cfg: dict[str, Any]) -> Path:
    return run_root(cfg) / "postprocess_failed.json"


def summary_txt_path(cfg: dict[str, Any]) -> Path:
    return postprocess_root(cfg) / "run_summary.txt"


def summary_json_path(cfg: dict[str, Any]) -> Path:
    return postprocess_root(cfg) / "run_summary.json"


def output_variables_path(cfg: dict[str, Any]) -> Path:
    return postprocess_root(cfg) / "output_variables.txt"


def quicklook_dir(cfg: dict[str, Any]) -> Path:
    return postprocess_root(cfg) / "quicklooks"


def safe_float(value: Any) -> Optional[float]:
    try:
        if hasattr(value, "values"):
            value = value.values
        if hasattr(value, "item"):
            value = value.item()
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return None
        return out
    except Exception:
        return None


def safe_stat(da: Any, stat: str) -> Optional[float]:
    """Compute simple stats on xarray DataArray safely."""
    try:
        if stat == "min":
            return safe_float(da.min(skipna=True))
        if stat == "max":
            return safe_float(da.max(skipna=True))
        if stat == "mean":
            return safe_float(da.mean(skipna=True))
        if stat == "sum":
            return safe_float(da.sum(skipna=True))
    except Exception:
        return None
    return None


def import_xarray():
    try:
        import xarray as xr
    except Exception as exc:
        raise ImportError("xarray is required for post-processing sfincs_map.nc") from exc
    return xr


def configure_matplotlib(cfg: dict[str, Any]) -> None:
    """Set non-interactive backend before importing pyplot."""
    backend = cfg_get(cfg, "postprocess_matplotlib_backend", "Agg")
    import matplotlib
    matplotlib.use(backend, force=True)


def import_pyplot(cfg: dict[str, Any]):
    configure_matplotlib(cfg)
    import matplotlib.pyplot as plt
    return plt


# ============================================================
# OUTPUT DATA BUNDLE
# ============================================================

@dataclass
class OutputBundle:
    """Container for model and xarray output datasets."""

    mod: Any
    map_data: Any
    his_data: Any
    read_method: str
    warnings: list[str]


# ============================================================
# BASIC VALIDATION
# ============================================================

def validate_raw_outputs(cfg: dict[str, Any]) -> None:
    print_section("POSTPROCESS RAW OUTPUT VALIDATION")

    root = model_root(cfg)
    map_nc = root / "sfincs_map.nc"
    his_nc = root / "sfincs_his.nc"
    log_file = root / "sfincs.log"

    if not root.exists():
        raise FileNotFoundError(f"Model root does not exist: {root}")
    print(f"FOUND: model root: {root}")

    if not map_nc.exists():
        raise FileNotFoundError(f"Required output not found: {map_nc}")
    print(f"FOUND: sfincs_map.nc: {map_nc}")

    if log_file.exists():
        print(f"FOUND: sfincs.log: {log_file}")
    else:
        print(f"WARNING: sfincs.log not found: {log_file}")

    if his_nc.exists():
        print(f"FOUND: sfincs_his.nc: {his_nc}")
    else:
        print("No sfincs_his.nc found. This is okay if no observation points/lines were configured.")


# ============================================================
# READ MODEL OUTPUTS
# ============================================================

def initialize_readonly_model(cfg: dict[str, Any]):
    """Initialize HydroMT-SFINCS model in read mode."""
    try:
        from hydromt_sfincs import SfincsModel
    except Exception as exc:
        raise ImportError(
            "Could not import hydromt_sfincs. Make sure the Slurm job activated the sfincs conda env."
        ) from exc

    data_catalogs = cfg_get(cfg, "data_catalogs", []) or []
    root = model_root(cfg)
    print(f"Opening SfincsModel in read mode: {root}")
    return SfincsModel(str(root), data_libs=data_catalogs, mode="r")


def read_outputs(cfg: dict[str, Any]) -> OutputBundle:
    """Read sfincs_map.nc and sfincs_his.nc using HydroMT first, xarray fallback second."""
    print_section("READ SFINCS OUTPUTS")

    warnings: list[str] = []
    root = model_root(cfg)
    map_nc = root / "sfincs_map.nc"
    his_nc = root / "sfincs_his.nc"

    mod = None
    map_data = None
    his_data = None

    # Preferred path: HydroMT-SFINCS knows how to interpret SGRID/staggered output.
    try:
        mod = initialize_readonly_model(cfg)
        mod.output.read()
        map_data = mod.output.data
        read_method = "hydromt_sfincs.SfincsModel.output.read"
        print("Read output using HydroMT-SFINCS mod.output.read().")
    except Exception as exc:
        read_method = "xarray.open_dataset fallback"
        msg = f"HydroMT-SFINCS output read failed, falling back to xarray: {exc}"
        print(f"WARNING: {msg}")
        warnings.append(msg)
        xr = import_xarray()
        map_data = xr.open_dataset(map_nc)
        print("Read sfincs_map.nc with xarray.open_dataset().")

        try:
            mod = initialize_readonly_model(cfg)
        except Exception as mod_exc:
            warnings.append(f"Could not initialize read-only SfincsModel after xarray fallback: {mod_exc}")
            mod = None

    # History output may or may not exist. If HydroMT read included it in map_data,
    # this extra dataset is still useful for direct variable inspection.
    if his_nc.exists():
        try:
            xr = import_xarray()
            his_data = xr.open_dataset(his_nc)
            print("Read sfincs_his.nc with xarray.open_dataset().")
        except Exception as exc:
            msg = f"Could not read sfincs_his.nc: {exc}"
            print(f"WARNING: {msg}")
            warnings.append(msg)
    else:
        print("Skipping history output read because sfincs_his.nc does not exist.")

    return OutputBundle(mod=mod, map_data=map_data, his_data=his_data, read_method=read_method, warnings=warnings)


# ============================================================
# VARIABLE HELPERS
# ============================================================

def dataset_var_names(ds: Any) -> list[str]:
    try:
        return list(ds.data_vars)
    except Exception:
        try:
            return list(ds.keys())
        except Exception:
            return []


def dataset_coord_names(ds: Any) -> list[str]:
    try:
        return list(ds.coords)
    except Exception:
        return []


def find_var(ds: Any, candidates: Iterable[str]) -> tuple[Optional[str], Optional[Any]]:
    """Return first available variable by candidate names."""
    names = set(dataset_var_names(ds))
    for name in candidates:
        if name in names:
            return name, ds[name]
    return None, None


def time_like_dims(da: Any) -> list[str]:
    """Identify dimensions that probably represent time or max-time."""
    dims = list(getattr(da, "dims", []))
    out = []
    for dim in dims:
        low = dim.lower()
        if low in {"time", "timemax"} or "time" in low:
            out.append(dim)
    return out


def max_over_time_dims(da: Any) -> Any:
    """Max over any time-like dimensions if present."""
    out = da
    for dim in time_like_dims(out):
        if dim in out.dims:
            out = out.max(dim=dim, skipna=True)
    return out


def final_time_slice(da: Any) -> Any:
    """Select final time-like slice if present."""
    out = da
    for dim in time_like_dims(out):
        if dim in out.dims and out.sizes.get(dim, 0) > 0:
            out = out.isel({dim: -1})
    return out


def squeeze_to_dataarray(da: Any) -> Any:
    try:
        return da.squeeze(drop=True)
    except Exception:
        return da


def reduce_to_2d_for_plot(da: Any) -> Any:
    """
    Convert a DataArray to something 2D-ish for plotting.

    Intended for already-time-reduced maps. If more than 2 dimensions remain,
    select the first index along extra dimensions rather than failing outright.
    """
    out = squeeze_to_dataarray(da)
    dims = list(getattr(out, "dims", []))

    while len(dims) > 2:
        dim = dims[0]
        out = out.isel({dim: 0})
        out = squeeze_to_dataarray(out)
        dims = list(getattr(out, "dims", []))

    return out


def downsample_for_plot(da: Any, max_cells: int) -> Any:
    """Coarsen very large arrays before plotting to avoid memory/PNG issues."""
    try:
        size = int(da.size)
    except Exception:
        return da

    if size <= max_cells:
        return da

    factor = max(2, int(math.ceil(math.sqrt(size / max_cells))))
    dims = list(getattr(da, "dims", []))
    coarsen_spec = {dim: factor for dim in dims if da.sizes.get(dim, 0) >= factor}
    if not coarsen_spec:
        return da

    print(f"Downsampling plot array from {size} cells using coarsen factor {factor}")
    try:
        return da.coarsen(coarsen_spec, boundary="trim").mean(skipna=True)
    except Exception as exc:
        print(f"WARNING: coarsen failed, plotting original array: {exc}")
        return da


def describe_dataarray(da: Any) -> dict[str, Any]:
    """Basic variable metadata and stats."""
    info = {
        "dims": dict(getattr(da, "sizes", {})),
        "attrs": dict(getattr(da, "attrs", {})),
        "min": safe_stat(da, "min"),
        "max": safe_stat(da, "max"),
        "mean": safe_stat(da, "mean"),
    }
    return info


# ============================================================
# DERIVED MAPS
# ============================================================

def get_max_water_level(bundle: OutputBundle, cfg: dict[str, Any]) -> tuple[Optional[str], Optional[Any], str]:
    """Get max water level map from zsmax or zs-like variables."""
    ds = bundle.map_data
    candidates = cfg_get(cfg, "postprocess_max_waterlevel_var_candidates", ["zsmax", "max_zs", "waterlevel_max"])
    name, da = find_var(ds, candidates)
    if da is not None:
        return name, max_over_time_dims(da), "direct maximum water-level variable"

    candidates = cfg_get(cfg, "postprocess_waterlevel_var_candidates", ["zs", "waterlevel", "water_level"])
    name, da = find_var(ds, candidates)
    if da is not None:
        return name, max_over_time_dims(da), "computed max over time from water-level variable"

    return None, None, "no water-level variable found"


def get_final_water_level(bundle: OutputBundle, cfg: dict[str, Any]) -> tuple[Optional[str], Optional[Any], str]:
    """Get final water level map from zs-like variables."""
    ds = bundle.map_data
    candidates = cfg_get(cfg, "postprocess_waterlevel_var_candidates", ["zs", "waterlevel", "water_level"])
    name, da = find_var(ds, candidates)
    if da is not None:
        return name, final_time_slice(da), "final time slice from water-level variable"
    return None, None, "no water-level variable found"


def get_bed_level(bundle: OutputBundle, cfg: dict[str, Any]) -> tuple[Optional[str], Optional[Any]]:
    ds = bundle.map_data
    candidates = cfg_get(cfg, "postprocess_bedlevel_var_candidates", ["zb", "bedlevel", "bed_level", "dep"])
    return find_var(ds, candidates)


def find_high_res_dep_file(cfg: dict[str, Any]) -> Optional[Path]:
    """Find best available high-resolution dep raster for subgrid downscaling."""
    root = model_root(cfg)
    candidates = [
        root / "subgrid" / "dep_subgrid.tif",
        root / "subgrid" / "dep.tif",
        root / "gis" / "dep_subgrid.tif",
        root / "gis" / "dep.tif",
        root / "dep_subgrid.tif",
        root / "dep.tif",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def try_downscale_subgrid_flood_depth(
    bundle: OutputBundle,
    cfg: dict[str, Any],
    zsmax_da: Any,
) -> tuple[Optional[Any], dict[str, Any]]:
    """
    Try proper subgrid flood-depth downscaling using HydroMT-SFINCS utils.

    Returns (dataarray, metadata). If it cannot downscale, returns (None, metadata).
    """
    meta: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "method": "hydromt_sfincs.utils.downscale_floodmap",
        "dep_file": None,
        "message": None,
    }

    dep_file = find_high_res_dep_file(cfg)
    if dep_file is None:
        meta["message"] = "No dep_subgrid.tif or dep.tif found for downscaling"
        return None, meta

    if bundle.mod is None:
        meta["message"] = "SfincsModel object unavailable; cannot read dep raster through data catalog"
        return None, meta

    meta["attempted"] = True
    meta["dep_file"] = str(dep_file)

    try:
        from hydromt_sfincs import utils

        hmin = float(cfg_get(cfg, "postprocess_min_flood_depth_m", 0.05))
        da_dep = bundle.mod.data_catalog.get_rasterdataset(str(dep_file))

        # Proper masking can be added later once we have a stable land/water mask.
        # For first pass, do no permanent-water masking.
        floodmap_tif = postprocess_root(cfg) / "max_flood_depth_downscaled.tif"
        da_hmax = utils.downscale_floodmap(
            zsmax=zsmax_da,
            dep=da_dep,
            hmin=hmin,
            floodmap_fn=str(floodmap_tif),
        )
        da_hmax.attrs.update(long_name="downscaled maximum flood depth", unit="m")
        meta["success"] = True
        meta["message"] = f"Downscaled flood map written to {floodmap_tif}"
        return da_hmax, meta
    except Exception as exc:
        meta["message"] = f"Downscaling failed: {exc}"
        return None, meta


def get_max_flood_depth(bundle: OutputBundle, cfg: dict[str, Any]) -> tuple[Optional[str], Optional[Any], dict[str, Any]]:
    """
    Find or derive maximum flood depth.

    Priority:
    1. Direct hmax-like variable.
    2. h-like depth variable max over time.
    3. For subgrid/zsmax, try downscale_floodmap.
    4. Fallback approximate coarse depth = zsmax - zb, clearly marked approximate.
    """
    ds = bundle.map_data
    meta: dict[str, Any] = {
        "method": None,
        "source_variable": None,
        "is_approximate": False,
        "warnings": [],
        "downscale": None,
    }

    # 1. Direct max-depth variable.
    max_depth_candidates = cfg_get(cfg, "postprocess_max_depth_var_candidates", ["hmax", "max_h", "flood_depth_max"])
    name, da = find_var(ds, max_depth_candidates)
    if da is not None:
        meta.update({
            "method": "direct maximum-depth variable",
            "source_variable": name,
            "is_approximate": False,
        })
        out = max_over_time_dims(da)
        out.attrs.update(long_name="maximum flood depth", unit="m")
        return name, out, meta

    # 2. Depth variable over time.
    depth_candidates = cfg_get(cfg, "postprocess_depth_var_candidates", ["h", "depth", "flood_depth"])
    name, da = find_var(ds, depth_candidates)
    if da is not None:
        meta.update({
            "method": "max over time from depth variable",
            "source_variable": name,
            "is_approximate": False,
        })
        out = max_over_time_dims(da)
        out.attrs.update(long_name="maximum flood depth", unit="m")
        return name, out, meta

    # 3. Subgrid-style zsmax downscaling.
    zsmax_name, zsmax_da, zsmax_how = get_max_water_level(bundle, cfg)
    if zsmax_da is not None:
        downscaled, downscale_meta = try_downscale_subgrid_flood_depth(bundle, cfg, zsmax_da)
        meta["downscale"] = downscale_meta
        if downscaled is not None:
            meta.update({
                "method": "downscaled from maximum water level and high-resolution dep raster",
                "source_variable": zsmax_name,
                "is_approximate": False,
            })
            return zsmax_name, downscaled, meta

        meta["warnings"].append(downscale_meta.get("message", "Downscaling unavailable"))

    # 4. Coarse approximate fallback: max water level - bed level.
    bed_name, bed_da = get_bed_level(bundle, cfg)
    if zsmax_da is not None and bed_da is not None:
        try:
            hmin = float(cfg_get(cfg, "postprocess_min_flood_depth_m", 0.05))
            approx = zsmax_da - bed_da
            approx = approx.where(approx > hmin)
            approx.attrs.update(long_name="approximate coarse maximum flood depth", unit="m")
            meta.update({
                "method": "approximate coarse depth = max water level - bed level",
                "source_variable": f"{zsmax_name} - {bed_name}",
                "is_approximate": True,
            })
            meta["warnings"].append(
                "This is a coarse fallback. For subgrid models, proper flood depth should be downscaled onto high-resolution elevation."
            )
            return f"{zsmax_name}_minus_{bed_name}", approx, meta
        except Exception as exc:
            meta["warnings"].append(f"Approximate depth fallback failed: {exc}")

    meta["method"] = "not available"
    return None, None, meta


# ============================================================
# OUTPUT VARIABLE LISTING / SUMMARY
# ============================================================

def summarize_dataset(ds: Any, label: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "label": label,
        "dims": {},
        "coords": [],
        "data_vars": {},
        "attrs": {},
    }

    try:
        summary["dims"] = {str(k): int(v) for k, v in ds.sizes.items()}
    except Exception:
        pass

    try:
        summary["coords"] = [str(c) for c in ds.coords]
    except Exception:
        pass

    try:
        summary["attrs"] = dict(ds.attrs)
    except Exception:
        pass

    for name in dataset_var_names(ds):
        try:
            da = ds[name]
            summary["data_vars"][name] = describe_dataarray(da)
        except Exception as exc:
            summary["data_vars"][name] = {"error": str(exc)}

    return summary


def write_output_variables(bundle: OutputBundle, cfg: dict[str, Any]) -> None:
    if not cfg_get(cfg, "postprocess_list_output_variables", True):
        return

    print_section("WRITE OUTPUT VARIABLES")

    lines: list[str] = []
    lines.append("SFINCS output variable listing")
    lines.append(f"created_at: {now_iso()}")
    lines.append(f"read_method: {bundle.read_method}")
    lines.append("")

    def add_dataset(ds: Any, label: str) -> None:
        lines.append(f"[{label}]")
        try:
            lines.append(f"dims: {dict(ds.sizes)}")
        except Exception:
            lines.append("dims: <unavailable>")
        try:
            lines.append(f"coords: {list(ds.coords)}")
        except Exception:
            lines.append("coords: <unavailable>")
        lines.append("variables:")
        for name in dataset_var_names(ds):
            try:
                da = ds[name]
                lines.append(f"  - {name}")
                lines.append(f"      dims: {dict(da.sizes)}")
                if da.attrs:
                    lines.append(f"      attrs: {dict(da.attrs)}")
                mn = safe_stat(da, "min")
                mx = safe_stat(da, "max")
                mean = safe_stat(da, "mean")
                lines.append(f"      min/max/mean: {mn} / {mx} / {mean}")
            except Exception as exc:
                lines.append(f"  - {name}: ERROR reading metadata: {exc}")
        lines.append("")

    add_dataset(bundle.map_data, "sfincs_map.nc / mod.output.data")
    if bundle.his_data is not None:
        add_dataset(bundle.his_data, "sfincs_his.nc")

    write_text(output_variables_path(cfg), "\n".join(lines) + "\n")
    print(f"Wrote output variable list: {output_variables_path(cfg)}")


# ============================================================
# PLOTTING HELPERS
# ============================================================


def read_model_crs_from_inp(cfg: dict[str, Any]) -> Optional[str]:
    """
    Read model CRS from sfincs.inp.

    SFINCS usually stores this as:
        epsg = 32633
    """
    inp = model_root(cfg) / "sfincs.inp"
    if not inp.exists():
        return None

    try:
        for line in inp.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean = line.strip().lower()
            if not clean.startswith("epsg"):
                continue

            parts = line.replace("=", " ").split()
            for part in parts:
                if part.isdigit():
                    return f"EPSG:{part}"
    except Exception as exc:
        print(f"WARNING: could not read EPSG from sfincs.inp: {exc}")

    return None


def get_da_crs(da: Any, cfg: dict[str, Any]) -> Optional[str]:
    """
    Try to get CRS from the DataArray itself, then fall back to sfincs.inp.
    """
    try:
        crs = getattr(getattr(da, "rio", None), "crs", None)
        if crs:
            return str(crs)
    except Exception:
        pass

    try:
        crs = da.raster.crs
        if crs:
            return str(crs)
    except Exception:
        pass

    return read_model_crs_from_inp(cfg)


def find_xy_coords_for_map(da: Any) -> tuple[Optional[Any], Optional[Any]]:
    """
    Find x/y coordinates for a result map.

    Handles:
    - 2D x/y coordinate arrays for rotated grids
    - 1D x/y coordinate arrays for regular grids

    Returns X, Y arrays matching the plotted data shape when possible.
    """
    try:
        import numpy as np
    except Exception:
        return None, None

    x_candidates = ["x", "xc", "xcenter", "x_center", "lon", "longitude"]
    y_candidates = ["y", "yc", "ycenter", "y_center", "lat", "latitude"]

    coords = getattr(da, "coords", {})
    dims = list(getattr(da, "dims", []))
    shape = tuple(getattr(da, "shape", ()))

    x_coord = None
    y_coord = None

    for name in x_candidates:
        if name in coords:
            x_coord = coords[name]
            break

    for name in y_candidates:
        if name in coords:
            y_coord = coords[name]
            break

    if x_coord is None or y_coord is None:
        return None, None

    try:
        x = x_coord.values
        y = y_coord.values

        # Best case: rotated/grid-aware 2D coordinates.
        if x.shape == shape and y.shape == shape:
            return x, y

        # Common regular-grid case: 1D x and 1D y.
        if x.ndim == 1 and y.ndim == 1 and len(shape) == 2:
            # Try to infer orientation from dimension order.
            if len(dims) == 2:
                dim0, dim1 = dims

                if x_coord.dims and y_coord.dims:
                    x_dim = x_coord.dims[0]
                    y_dim = y_coord.dims[0]

                    if dim0 == y_dim and dim1 == x_dim:
                        X, Y = np.meshgrid(x, y)
                        return X, Y

                    if dim0 == x_dim and dim1 == y_dim:
                        X, Y = np.meshgrid(x, y, indexing="ij")
                        return X, Y

            # Fallback assumption: data is [y, x].
            X, Y = np.meshgrid(x, y)
            if X.shape == shape and Y.shape == shape:
                return X, Y

    except Exception as exc:
        print(f"WARNING: could not interpret x/y coordinates for map plot: {exc}")
        return None, None

    return None, None




def transform_xy_to_web_mercator(x: Any, y: Any, source_crs: str) -> tuple[Any, Any]:

    """

    Transform model coordinates to EPSG:3857 for web tile basemaps.

    Kept for future/debug use; contextily can also transform from a supplied CRS.

    """

    from pyproj import Transformer



    transformer = Transformer.from_crs(source_crs, "EPSG:3857", always_xy=True)

    return transformer.transform(x, y)





def contextily_source_from_name(name: Optional[str]) -> Any:

    """

    Convert simple source names to contextily providers.

    """

    import contextily as cx



    if name is None:

        return None



    low = str(name).strip().lower()



    if low in {"sat", "satellite", "imagery"}:

        return cx.providers.Esri.WorldImagery



    if low in {"osm", "openstreetmap"}:

        return cx.providers.OpenStreetMap.Mapnik



    return name





def add_satellite_basemap(

    ax: Any,

    cfg: dict[str, Any],

    crs: Any = None,

    force: bool = False,

) -> None:

    """

    Add a web-tile basemap behind a result map.



    If crs is supplied, contextily transforms the current axis extent from that CRS.

    If crs is None, it assumes the axis is already Web Mercator.

    This is non-critical: if it fails, the result map should still save.

    """

    if (not force) and (not cfg_get(cfg, "postprocess_use_basemap_on_result_maps", False)):

        return



    try:

        import contextily as cx

    except Exception as exc:

        print(f"WARNING: contextily unavailable; skipping result-map basemap: {exc}")

        return



    try:

        source_name = cfg_get(cfg, "postprocess_basemap_source", "sat")

        source = contextily_source_from_name(source_name)

        zoomlevel = normalize_basemap_zoomlevel_global(

            cfg_get(cfg, "postprocess_basemap_zoomlevel", "auto")

        )



        if crs is None:

            crs = "EPSG:3857"



        print(f"Adding result-map web basemap: source={source_name}, zoom={zoomlevel}, crs={crs}")



        cx.add_basemap(

            ax,

            source=source,

            zoom=zoomlevel,

            crs=crs,

            attribution_size=6,

            reset_extent=True,

            zorder=0,

        )

    except Exception as exc:

        print(f"WARNING: failed to add basemap to result map: {exc}")







def save_simple_dataarray_plot(
    da: Any,
    cfg: dict[str, Any],
    filename: str,
    title: str,
    long_name: Optional[str] = None,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> Optional[Path]:
    """
    Old robust fallback plot.

    This is kept so postprocessing still produces maps even if the smarter
    rotated/basemap plotting path fails.
    """
    if da is None:
        return None

    plt = import_pyplot(cfg)
    out_dir = quicklook_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    try:
        plot_da = reduce_to_2d_for_plot(da)
        plot_da = downsample_for_plot(
            plot_da,
            int(cfg_get(cfg, "postprocess_max_plot_cells", 2_000_000)),
        )

        if long_name:
            plot_da.attrs["long_name"] = long_name

        fig, ax = plt.subplots(figsize=(10, 7))
        kwargs: dict[str, Any] = {}
        if vmin is not None:
            kwargs["vmin"] = vmin
        if vmax is not None:
            kwargs["vmax"] = vmax

        plot_da.plot(ax=ax, **kwargs)
        ax.set_title(title)
        fig.tight_layout()
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved fallback plot: {out_path}")
        return out_path

    except Exception as exc:
        plt.close("all")
        print(f"WARNING: failed to save fallback plot {filename}: {exc}")
        return None


def save_dataarray_plot(
    bundle: OutputBundle,
    da: Any,
    cfg: dict[str, Any],
    filename: str,
    title: str,
    long_name: Optional[str] = None,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> Optional[Path]:
    """
    Save a result map.

    Preferred behavior:
    - use model/result x-y coordinates
    - preserve rotated-grid geometry when coordinates allow it
    - optionally add satellite/OpenStreetMap basemap
    - write to the normal filename, replacing the old simple plot

    Fallback:
    - if smart plotting fails, use the old simple xarray plot.
    """
    if da is None:
        return None

    if not cfg_get(cfg, "postprocess_use_rotated_map_plots", True):
        return save_simple_dataarray_plot(
            da=da,
            cfg=cfg,
            filename=filename,
            title=title,
            long_name=long_name,
            vmin=vmin,
            vmax=vmax,
        )

    plt = import_pyplot(cfg)
    out_dir = quicklook_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    try:
        import numpy as np

        plot_da = reduce_to_2d_for_plot(da)
        plot_da = downsample_for_plot(
            plot_da,
            int(cfg_get(cfg, "postprocess_max_plot_cells", 2_000_000)),
        )

        if long_name:
            plot_da.attrs["long_name"] = long_name

        x, y = find_xy_coords_for_map(plot_da)
        if x is None or y is None:
            print(f"WARNING: no usable x/y coordinates for {filename}; using fallback plot.")
            return save_simple_dataarray_plot(
                da=da,
                cfg=cfg,
                filename=filename,
                title=title,
                long_name=long_name,
                vmin=vmin,
                vmax=vmax,
            )

        values = np.asarray(plot_da.values)

        # Mask invalid values so basemap can show through where there is no data.
        values = np.ma.masked_invalid(values)

        use_basemap = cfg_get(cfg, "postprocess_use_basemap_on_result_maps", False)
        x_plot, y_plot = x, y

        # Prefer HydroMT-SFINCS basemap plotting, because this already works for model_layout.png.
        if use_basemap and bundle.mod is not None and cfg_get(cfg, "postprocess_result_map_use_hydromt_basemap", False):
            try:
                bmap = cfg_get(cfg, "postprocess_basemap_source", "sat")
                zoomlevel = normalize_basemap_zoomlevel_global(cfg_get(cfg, "postprocess_basemap_zoomlevel", "auto"))
        
                show_model_features = cfg_get(cfg, "postprocess_result_map_show_model_features", False)
                show_obs = cfg_get(cfg, "postprocess_result_map_show_obs", False)
                show_boundaries = cfg_get(cfg, "postprocess_result_map_show_boundaries", False)
                show_dep_layer = cfg_get(cfg, "postprocess_result_map_show_dep_layer", False)
                show_layout_legend = cfg_get(cfg, "postprocess_result_map_show_layout_legend", False)
        
                # For result maps, default to a clean basemap:
                # no dep layer, no observation clutter, no boundary clutter.
                basemap_kwargs = {
                    "fn_out": None,
                    "bmap": bmap,
                    "zoomlevel": zoomlevel,
                    "figsize": (10, 7),
                    "plot_bounds": bool(show_boundaries or show_model_features),
                    "plot_region": bool(show_model_features),
                    "plot_geoms": bool(show_obs or show_model_features),
                    "legend_kwargs": {},
                }
        
                # Try to suppress the default dep layer on result maps.
                # If this fails in HydroMT-SFINCS, the except block below will retry safely.
               # Always use dep internally to give HydroMT-SFINCS a real map extent.
# If the user does not want to show dep, we remove the dep layer right after.
                basemap_kwargs["variable"] = "dep"
                
                fig, ax = bundle.mod.plot_basemap(**basemap_kwargs)
                
                # If dep layer is only being used to establish the map extent,
                # remove the dep-colored collections but DO NOT remove ax.images,
                # because satellite/OSM tiles may live in ax.images.
                if not show_dep_layer:
                    for artist in list(ax.collections):
                        try:
                            artist.remove()
                        except Exception:
                            pass
                
                    # Remove extra colorbar axes created by the dep layer.
                    for extra_ax in list(fig.axes):
                        if extra_ax is not ax:
                            fig.delaxes(extra_ax)
        
                # Remove layout legend if requested.
                if not show_layout_legend:
                    leg = ax.get_legend()
                    if leg is not None:
                        leg.remove()
        
                # Decouple satellite/OSM tiles from HydroMT layout clutter.

                # HydroMT-SFINCS plot_basemap sometimes only establishes the map

                # through dep/bounds/geoms layers. If those layers are hidden for a

                # clean presentation figure, make sure the web-tile basemap is still

                # added using the already-established axis extent.

                if use_basemap and not list(ax.images):

                    print("Result-map basemap: no tile image found after HydroMT plot_basemap; adding contextily basemap directly.")

                    add_satellite_basemap(ax, cfg)



                # Remove extra colorbar axes created by the layout basemap,
                # especially the dep colorbar, before adding our result colorbar.
            
        
                print(f"Using HydroMT-SFINCS basemap for {filename}.")
        
            except Exception as exc:
                print(f"WARNING: HydroMT-SFINCS clean basemap failed for {filename}: {exc}")
                fig, ax = plt.subplots(figsize=(10, 7))
        else:
            fig, ax = plt.subplots(figsize=(10, 7))

        kwargs: dict[str, Any] = {
            "shading": "auto",
            "alpha": float(cfg_get(cfg, "postprocess_result_map_alpha", 1.0)),
            "zorder": 2,
        }
        if vmin is not None:
            kwargs["vmin"] = vmin
        if vmax is not None:
            kwargs["vmax"] = vmax


        from matplotlib.patches import Rectangle
        
        fade_alpha = float(cfg_get(cfg, "postprocess_result_map_background_fade_alpha", 0.0))
        if use_basemap and fade_alpha > 0:
            ax.add_patch(
                Rectangle(
                    (0, 0),
                    1,
                    1,
                    transform=ax.transAxes,
                    facecolor="white",
                    edgecolor="none",
                    alpha=fade_alpha,
                    zorder=1,
                )
            )
            
        mesh = ax.pcolormesh(x_plot, y_plot, values, **kwargs)


        # Add satellite/OSM directly to the final result-map axis.
        # This is independent of model-feature, boundary, obs, dep, and legend overlays.
        if use_basemap:
            model_crs = get_da_crs(plot_da, cfg)
            print(f"Result-map direct basemap for {filename}: model_crs={model_crs}")
            add_satellite_basemap(ax, cfg, crs=model_crs, force=True)
        label = long_name or str(getattr(plot_da, "name", "")) or "value"
        cbar = fig.colorbar(mesh, ax=ax, shrink=0.85)
        cbar.set_label(label)

        ax.set_title(title)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("")
        ax.set_ylabel("")

        fig.tight_layout()
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)

        print(f"Saved smart map plot: {out_path}")
        return out_path

    except Exception as exc:
        plt.close("all")
        print(f"WARNING: smart map plot failed for {filename}: {exc}")
        return save_simple_dataarray_plot(
            da=da,
            cfg=cfg,
            filename=filename,
            title=title,
            long_name=long_name,
            vmin=vmin,
            vmax=vmax,
        )


def save_model_layout_plot(bundle: OutputBundle, cfg: dict[str, Any]) -> Optional[Path]:
    """Try HydroMT-SFINCS model layout plot; fallback is no plot."""
    if bundle.mod is None:
        return None

    if not cfg_get(cfg, "postprocess_make_quicklook_plots", True):
        return None

    plt = import_pyplot(cfg)
    out_dir = quicklook_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "model_layout.png"

    try:
        bmap = cfg_get(cfg, "postprocess_basemap_source", None)
        if not cfg_get(cfg, "postprocess_use_basemap", False):
            bmap = None

        zoomlevel = normalize_basemap_zoomlevel_global(cfg_get(cfg, "postprocess_basemap_zoomlevel", "auto"))

        fig, ax = bundle.mod.plot_basemap(
            fn_out=None,
            bmap=bmap,
            zoomlevel=zoomlevel,
            figsize=(10, 7),
        )
        ax.set_title("SFINCS model layout")
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved model layout plot: {out_path}")
        return out_path
    except Exception as exc:
        plt.close("all")
        print(f"WARNING: failed to save model layout plot: {exc}")
        return None


def save_observation_hydrographs(bundle: OutputBundle, cfg: dict[str, Any]) -> list[Path]:
    """Plot observation/history variables if sfincs_his.nc or point_* vars exist."""
    if not cfg_get(cfg, "postprocess_plot_obs_hydrographs", True):
        return []

    print_section("OBSERVATION HYDROGRAPHS")

    plt = import_pyplot(cfg)
    out_dir = quicklook_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    candidate_datasets: list[tuple[str, Any]] = []
    if bundle.his_data is not None:
        candidate_datasets.append(("his", bundle.his_data))
    if bundle.map_data is not None:
        # HydroMT sometimes includes point_* data in mod.output.data.
        candidate_datasets.append(("map_output", bundle.map_data))

    if not candidate_datasets:
        print("No history/observation dataset available.")
        return saved

    for dataset_label, ds in candidate_datasets:
        for name in dataset_var_names(ds):
            if not (name.startswith("point_") or "station" in name.lower() or "obs" in name.lower()):
                continue

            try:
                da = ds[name]
                dims = list(da.dims)
                if not any("time" in dim.lower() for dim in dims):
                    continue

                fig, ax = plt.subplots(figsize=(10, 5))

                # For station-like dimensions, plot first few stations to keep it readable.
                station_dims = [d for d in dims if d.lower() in {"stations", "station", "station_id", "points", "point"}]
                plot_da = da
                if station_dims:
                    station_dim = station_dims[0]
                    n = min(5, int(plot_da.sizes.get(station_dim, 1)))
                    plot_da = plot_da.isel({station_dim: slice(0, n)})

                plot_da.plot.line(ax=ax, x="time" if "time" in plot_da.dims else None)
                ax.set_title(f"Observation/history: {name}")
                ax.grid(True, alpha=0.3)
                fig.tight_layout()

                out_path = out_dir / f"hydrograph_{dataset_label}_{name}.png"
                fig.savefig(out_path, dpi=200, bbox_inches="tight")
                plt.close(fig)
                saved.append(out_path)
                print(f"Saved hydrograph: {out_path}")
            except Exception as exc:
                plt.close("all")
                print(f"WARNING: failed to plot observation variable {name}: {exc}")

    if not saved:
        print("No observation hydrographs were created.")

    return saved


def make_quicklook_plots(bundle: OutputBundle, cfg: dict[str, Any], derived: dict[str, Any]) -> list[Path]:
    if not cfg_get(cfg, "postprocess_make_quicklook_plots", True):
        print("Skipping quicklook plots because postprocess_make_quicklook_plots=False")
        return []

    print_section("MAKE QUICKLOOK PLOTS")
    saved: list[Path] = []

    layout = save_model_layout_plot(bundle, cfg)
    if layout:
        saved.append(layout)

    if cfg_get(cfg, "postprocess_plot_max_water_level", True):
        path = save_dataarray_plot(
            bundle,
            derived.get("max_water_level"),
            cfg,
            filename="max_water_level.png",
            title="SFINCS maximum water level",
            long_name="maximum water level",
        )
        if path:
            saved.append(path)

    if cfg_get(cfg, "postprocess_plot_max_flood_depth", True):
        path = save_dataarray_plot(
            bundle,
            derived.get("max_flood_depth"),
            cfg,
            filename="max_flood_depth.png",
            title="SFINCS maximum flood depth",
            long_name="maximum flood depth",
            vmin=0,
        )
        if path:
            saved.append(path)

    if cfg_get(cfg, "postprocess_plot_final_water_level", True):
        path = save_dataarray_plot(
            bundle,
            derived.get("final_water_level"),
            cfg,
            filename="final_water_level.png",
            title="SFINCS final water level",
            long_name="final water level",
        )
        if path:
            saved.append(path)

    saved.extend(save_observation_hydrographs(bundle, cfg))
    return saved


# ============================================================
# SUMMARY WRITING
# ============================================================

def build_derived_products(bundle: OutputBundle, cfg: dict[str, Any]) -> dict[str, Any]:
    print_section("BUILD DERIVED PRODUCTS")

    derived: dict[str, Any] = {
        "max_water_level": None,
        "max_water_level_meta": {},
        "final_water_level": None,
        "final_water_level_meta": {},
        "max_flood_depth": None,
        "max_flood_depth_meta": {},
    }

    wl_name, wl_da, wl_method = get_max_water_level(bundle, cfg)
    derived["max_water_level"] = wl_da
    derived["max_water_level_meta"] = {
        "source_variable": wl_name,
        "method": wl_method,
        "stats": describe_dataarray(wl_da) if wl_da is not None else None,
    }
    print(f"Max water level: source={wl_name}, method={wl_method}")

    final_name, final_da, final_method = get_final_water_level(bundle, cfg)
    derived["final_water_level"] = final_da
    derived["final_water_level_meta"] = {
        "source_variable": final_name,
        "method": final_method,
        "stats": describe_dataarray(final_da) if final_da is not None else None,
    }
    print(f"Final water level: source={final_name}, method={final_method}")

    depth_name, depth_da, depth_meta = get_max_flood_depth(bundle, cfg)
    derived["max_flood_depth"] = depth_da
    derived["max_flood_depth_meta"] = {
        **depth_meta,
        "source_variable": depth_name,
        "stats": describe_dataarray(depth_da) if depth_da is not None else None,
    }
    print(f"Max flood depth: source={depth_name}, method={depth_meta.get('method')}")
    if depth_meta.get("is_approximate"):
        print("WARNING: max flood depth is approximate/coarse. Proper subgrid downscaling was not available.")

    return derived


def build_summary_dict(
    bundle: OutputBundle,
    cfg: dict[str, Any],
    derived: dict[str, Any],
    plot_paths: list[Path],
) -> dict[str, Any]:
    root = model_root(cfg)

    summary: dict[str, Any] = {
        "status": "success",
        "created_at": now_iso(),
        "run_name": cfg_get(cfg, "run_name"),
        "run_root": run_root(cfg),
        "model_root": root,
        "postprocess_root": postprocess_root(cfg),
        "read_method": bundle.read_method,
        "warnings": bundle.warnings,
        "input_files": {
            "sfincs_inp": root / "sfincs.inp",
            "sfincs_log": root / "sfincs.log",
            "sfincs_map_nc": root / "sfincs_map.nc",
            "sfincs_his_nc": root / "sfincs_his.nc",
        },
        "model_config": {
            "tref": cfg_get(cfg, "tref"),
            "tstart": cfg_get(cfg, "tstart"),
            "tstop": cfg_get(cfg, "tstop"),
            "dtout_s": cfg_get(cfg, "dtout_s"),
            "dthisout_s": cfg_get(cfg, "dthisout_s"),
            "dtmaxout_s": cfg_get(cfg, "dtmaxout_s"),
            "use_subgrid": cfg_get(cfg, "use_subgrid"),
            "use_rainfall": cfg_get(cfg, "use_rainfall"),
            "use_waterlevel_boundary": cfg_get(cfg, "use_waterlevel_boundary"),
            "use_discharge_boundary": cfg_get(cfg, "use_discharge_boundary"),
            "use_infiltration": cfg_get(cfg, "use_infiltration"),
        },
        "map_output": summarize_dataset(bundle.map_data, "map_output"),
        "history_output": summarize_dataset(bundle.his_data, "history_output") if bundle.his_data is not None else None,
        "derived_products": {
            "max_water_level": derived.get("max_water_level_meta"),
            "final_water_level": derived.get("final_water_level_meta"),
            "max_flood_depth": derived.get("max_flood_depth_meta"),
        },
        "plots": [str(p) for p in plot_paths],
    }

    return summary


def write_summary_json(cfg: dict[str, Any], summary: dict[str, Any]) -> None:
    if not cfg_get(cfg, "postprocess_create_summary_json", True):
        return
    write_json(summary_json_path(cfg), summary)
    print(f"Wrote summary JSON: {summary_json_path(cfg)}")


def format_stat_line(label: str, meta: Optional[dict[str, Any]]) -> str:
    if not meta:
        return f"{label}: unavailable"
    stats = meta.get("stats") or {}
    if not stats:
        return f"{label}: unavailable"
    return (
        f"{label}: min={stats.get('min')}, max={stats.get('max')}, "
        f"mean={stats.get('mean')} ({meta.get('method')})"
    )


def write_summary_txt(cfg: dict[str, Any], summary: dict[str, Any]) -> None:
    if not cfg_get(cfg, "postprocess_create_summary_txt", True):
        return

    derived = summary.get("derived_products", {})
    lines: list[str] = []
    lines.append("SFINCS POSTPROCESSING SUMMARY")
    lines.append("=" * 40)
    lines.append(f"Created at:       {summary.get('created_at')}")
    lines.append(f"Run name:         {summary.get('run_name')}")
    lines.append(f"Run root:         {summary.get('run_root')}")
    lines.append(f"Model root:       {summary.get('model_root')}")
    lines.append(f"Postprocess root: {summary.get('postprocess_root')}")
    lines.append(f"Read method:      {summary.get('read_method')}")
    lines.append("")

    lines.append("Model timing / toggles")
    lines.append("-" * 40)
    model_config = summary.get("model_config", {})
    for key, val in model_config.items():
        lines.append(f"{key}: {val}")
    lines.append("")

    lines.append("Derived product stats")
    lines.append("-" * 40)
    lines.append(format_stat_line("Maximum water level", derived.get("max_water_level")))
    lines.append(format_stat_line("Final water level", derived.get("final_water_level")))
    lines.append(format_stat_line("Maximum flood depth", derived.get("max_flood_depth")))
    depth_meta = derived.get("max_flood_depth") or {}
    if depth_meta.get("is_approximate"):
        lines.append("WARNING: maximum flood depth is approximate/coarse, not proper subgrid downscaling.")
    if depth_meta.get("warnings"):
        for warning in depth_meta.get("warnings", []):
            lines.append(f"Depth warning: {warning}")
    lines.append("")

    lines.append("Map output variables")
    lines.append("-" * 40)
    map_vars = (summary.get("map_output") or {}).get("data_vars", {})
    for name in map_vars:
        lines.append(f"- {name}")
    lines.append("")

    lines.append("Plots")
    lines.append("-" * 40)
    plots = summary.get("plots", [])
    if plots:
        for plot in plots:
            lines.append(f"- {plot}")
    else:
        lines.append("No plots created.")
    lines.append("")

    if summary.get("warnings"):
        lines.append("Warnings")
        lines.append("-" * 40)
        for warning in summary.get("warnings", []):
            lines.append(f"- {warning}")
        lines.append("")

    write_text(summary_txt_path(cfg), "\n".join(lines) + "\n")
    print(f"Wrote summary TXT: {summary_txt_path(cfg)}")


# ============================================================
# MAIN POSTPROCESS WORKFLOW
# ============================================================

def postprocess(cfg: dict[str, Any], config_path: Path) -> None:
    print_section("POSTPROCESS CONFIG SUMMARY")
    print(f"Config path:       {config_path}")
    print(f"Run name:          {cfg_get(cfg, 'run_name')}")
    print(f"Run root:          {run_root(cfg)}")
    print(f"Model root:        {model_root(cfg)}")
    print(f"Postprocess root:  {postprocess_root(cfg)}")

    postprocess_root(cfg).mkdir(parents=True, exist_ok=True)
    quicklook_dir(cfg).mkdir(parents=True, exist_ok=True)

    validate_raw_outputs(cfg)
    bundle = read_outputs(cfg)
    write_output_variables(bundle, cfg)
    derived = build_derived_products(bundle, cfg)
    plot_paths = make_quicklook_plots(bundle, cfg, derived)
    summary = build_summary_dict(bundle, cfg, derived, plot_paths)
    write_summary_txt(cfg, summary)
    write_summary_json(cfg, summary)


    print_section("POSTPROCESS COMPLETE")
    print(f"Summary TXT:  {summary_txt_path(cfg)}")
    print(f"Summary JSON: {summary_json_path(cfg)}")
    print(f"Quicklooks:   {quicklook_dir(cfg)}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage:")
        print("  python postprocess_stage.py /path/to/run_config.json")
        return 2

    config_path = Path(argv[1]).resolve()

    print_section("POSTPROCESS STAGE START")
    print(f"Started at: {now_iso()}")
    print(f"Python:     {sys.executable}")
    print(f"Config:     {config_path}")

    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}")
        return 2

    cfg = read_json(config_path)

    try:
        postprocess(cfg, config_path)
    except Exception as exc:
        print_section("POSTPROCESS FAILED")
        print(f"Failed at: {now_iso()}")
        print(f"Error type: {type(exc).__name__}")
        print(f"Error: {exc}")
        print("\nTraceback:")
        traceback.print_exc()

        try:
            write_json(
                postprocess_failure_path(cfg),
                {
                    "status": "failed",
                    "failed_at": now_iso(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "config_path": config_path,
                    "model_root": model_root(cfg),
                    "postprocess_root": postprocess_root(cfg),
                },
            )
            print(f"Wrote failure record: {postprocess_failure_path(cfg)}")
        except Exception as write_exc:
            print(f"WARNING: could not write failure record: {write_exc}")

        return 1

    print_section("POSTPROCESS STAGE END")
    print(f"Finished at: {now_iso()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
