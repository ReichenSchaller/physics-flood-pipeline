#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 11:56:09 2026

@author: epsilon

Manual Mode geometry checker for SFINCS/HydroMT source-build configs.

Purpose
-------
Run a read-only geometry sanity check before preprocessing. This checks whether
the selected DEM, active mask, region geometry, coastal/open-boundary outline,
discharge points, observation points/lines, and structure vectors are spatially
plausible with respect to each other.

This does NOT build the model and does NOT edit any inputs.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def json_safe(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        if not math.isfinite(value):
            return None
        return value
    if isinstance(obj, np.ndarray):
        return [json_safe(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_safe(v) for v in obj]
    return obj


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(json_safe(data), f, indent=2, allow_nan=False)


def cfg_path(cfg: dict[str, Any], key: str) -> Path | None:
    value = cfg.get(key)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return Path(text)


def first_path_from_list(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                return Path(text)
        return None
    text = str(value).strip()
    return Path(text) if text else None


def path_from_hydromt_dem_sources(cfg: dict[str, Any]) -> Path | None:
    items = cfg.get("hydromt_dem_sources") or []
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("elevation")
        if value is None:
            continue
        text = str(value).strip()
        if text.startswith("/"):
            return Path(text)
    return None


def model_crs_from_cfg(cfg: dict[str, Any]) -> str:
    value = str(cfg.get("grid_crs") or "EPSG:32615").strip()
    if not value:
        return "EPSG:32615"
    if value.lower().startswith("epsg:"):
        return value.upper()
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"EPSG:{digits}" if digits else value


def add_check(
    checks: list[dict[str, Any]],
    status: str,
    name: str,
    detail: str = "",
    data: dict[str, Any] | None = None,
) -> None:
    if status not in {"good", "warn", "bad"}:
        raise ValueError(f"Invalid check status: {status}")
    checks.append({
        "status": status,
        "name": name,
        "detail": detail,
        "data": data or {},
    })


def status_rank(status: str) -> int:
    return {"good": 0, "warn": 1, "bad": 2}.get(status, 2)


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(item["status"] == "bad" for item in checks):
        return "bad"
    if any(item["status"] == "warn" for item in checks):
        return "warn"
    return "good"


def import_geo_stack():
    try:
        import geopandas as gpd
        import rasterio
        from rasterio.warp import transform_bounds
        from shapely.geometry import box, Point, LineString
        from shapely.ops import unary_union
        import pandas as pd
    except Exception as exc:
        raise RuntimeError(
            "Geometry check requires geopandas, rasterio, shapely, and pandas "
            "in the selected conda_python environment."
        ) from exc

    return {
        "gpd": gpd,
        "rasterio": rasterio,
        "transform_bounds": transform_bounds,
        "box": box,
        "Point": Point,
        "LineString": LineString,
        "unary_union": unary_union,
        "pd": pd,
    }


def bounds_dict(bounds: tuple[float, float, float, float]) -> dict[str, float]:
    minx, miny, maxx, maxy = bounds
    return {
        "minx": float(minx),
        "miny": float(miny),
        "maxx": float(maxx),
        "maxy": float(maxy),
        "width": float(maxx - minx),
        "height": float(maxy - miny),
        "area_bbox": float(max(0.0, maxx - minx) * max(0.0, maxy - miny)),
        "cx": float((minx + maxx) / 2.0),
        "cy": float((miny + maxy) / 2.0),
    }


def read_raster_meta(path: Path, target_crs: str, stack: dict[str, Any]) -> dict[str, Any]:
    rasterio = stack["rasterio"]
    transform_bounds = stack["transform_bounds"]

    with rasterio.open(path) as src:
        src_crs = str(src.crs) if src.crs else None
        raw_bounds = tuple(float(v) for v in src.bounds)
        if src.crs and target_crs and str(src.crs) != target_crs:
            tb = transform_bounds(src.crs, target_crs, *src.bounds, densify_pts=21)
            target_bounds = tuple(float(v) for v in tb)
        else:
            target_bounds = raw_bounds

        return {
            "path": str(path),
            "exists": path.exists(),
            "kind": "raster",
            "crs": src_crs,
            "target_crs": target_crs,
            "bounds": bounds_dict(target_bounds),
            "raw_bounds": bounds_dict(raw_bounds),
            "width_px": int(src.width),
            "height_px": int(src.height),
            "count": int(src.count),
            "nodata": src.nodata,
            "res": [float(abs(src.transform.a)), float(abs(src.transform.e))],
        }


def read_vector_meta(path: Path, target_crs: str, stack: dict[str, Any]) -> dict[str, Any]:
    gpd = stack["gpd"]

    gdf = gpd.read_file(path)
    src_crs = str(gdf.crs) if gdf.crs else None
    if gdf.empty:
        target_gdf = gdf
        target_bounds = (math.nan, math.nan, math.nan, math.nan)
        geom = None
    else:
        if gdf.crs and target_crs and str(gdf.crs) != target_crs:
            target_gdf = gdf.to_crs(target_crs)
        else:
            target_gdf = gdf
        target_bounds = tuple(float(v) for v in target_gdf.total_bounds)
        geoms = target_gdf.geometry.dropna()
        geom = geoms.union_all() if hasattr(geoms, "union_all") else geoms.unary_union

    geom_types = []
    if not gdf.empty and "geometry" in gdf:
        geom_types = sorted(set(str(v) for v in gdf.geometry.geom_type.dropna().tolist()))

    return {
        "path": str(path),
        "exists": path.exists(),
        "kind": "vector",
        "crs": src_crs,
        "target_crs": target_crs,
        "rows": int(len(gdf)),
        "geometry_types": geom_types,
        "bounds": bounds_dict(target_bounds) if geom is not None else None,
        "_geometry": geom,
    }


def bbox_geometry(meta: dict[str, Any], stack: dict[str, Any]):
    box = stack["box"]
    b = meta.get("bounds")
    if not b:
        return None
    return box(b["minx"], b["miny"], b["maxx"], b["maxy"])


def bbox_overlap_fraction(inner_meta: dict[str, Any], outer_meta: dict[str, Any], stack: dict[str, Any]) -> float:
    inner = bbox_geometry(inner_meta, stack)
    outer = bbox_geometry(outer_meta, stack)
    if inner is None or outer is None:
        return 0.0
    if inner.area <= 0:
        return 0.0
    return float(inner.intersection(outer).area / inner.area)


def distance_between_bboxes(a_meta: dict[str, Any], b_meta: dict[str, Any], stack: dict[str, Any]) -> float:
    a = bbox_geometry(a_meta, stack)
    b = bbox_geometry(b_meta, stack)
    if a is None or b is None:
        return float("nan")
    return float(a.distance(b))


def _infer_csv_xy_columns(columns: list[str], requested_x_col: str, requested_y_col: str) -> tuple[str, str, list[tuple[str, str]]]:
    lower_to_original = {str(col).lower(): str(col) for col in columns}

    requested_x_col = str(requested_x_col or "").strip()
    requested_y_col = str(requested_y_col or "").strip()

    candidate_pairs = []

    if requested_x_col and requested_y_col:
        candidate_pairs.append((requested_x_col, requested_y_col))

    candidate_pairs.extend([
        ("x_utm15n", "y_utm15n"),
        ("coord_x_utm15n", "coord_y_utm15n"),
        ("sfincs_src_x", "sfincs_src_y"),
        ("source_x", "source_y"),
        ("x", "y"),
        ("coord_x", "coord_y"),
        ("easting", "northing"),
    ])

    tried: list[tuple[str, str]] = []

    for x_candidate, y_candidate in candidate_pairs:
        x_key = str(x_candidate).lower()
        y_key = str(y_candidate).lower()
        tried.append((x_candidate, y_candidate))

        if x_key in lower_to_original and y_key in lower_to_original:
            return lower_to_original[x_key], lower_to_original[y_key], tried

    raise RuntimeError(
        "Could not infer CSV x/y columns. "
        f"Tried {tried}. Available columns: {columns}"
    )


def make_point_gdf_from_xy_csv(path: Path, x_col: str, y_col: str, target_crs: str, stack: dict[str, Any]):
    pd = stack["pd"]
    gpd = stack["gpd"]
    Point = stack["Point"]

    df = pd.read_csv(path)
    x_used, y_used, tried = _infer_csv_xy_columns(list(df.columns), x_col, y_col)

    clean = df[[x_used, y_used]].dropna()
    geoms = [Point(float(x), float(y)) for x, y in zip(clean[x_used], clean[y_used])]

    gdf = gpd.GeoDataFrame(clean.copy(), geometry=geoms, crs=target_crs)
    gdf.attrs["x_col"] = x_used
    gdf.attrs["y_col"] = y_used
    gdf.attrs["requested_x_col"] = x_col
    gdf.attrs["requested_y_col"] = y_col
    gdf.attrs["tried_xy_columns"] = tried
    return gdf


def make_point_gdf_from_xy_file(path: Path, target_crs: str, stack: dict[str, Any]):
    gpd = stack["gpd"]
    Point = stack["Point"]

    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            vals = []
            for tok in line.replace(",", " ").split():
                try:
                    vals.append(float(tok))
                except Exception:
                    pass
            if len(vals) >= 2:
                rows.append((vals[0], vals[1]))

    geoms = [Point(x, y) for x, y in rows]
    return gpd.GeoDataFrame({"x": [r[0] for r in rows], "y": [r[1] for r in rows]}, geometry=geoms, crs=target_crs)


def _looks_like_projected_xy(x: float, y: float) -> bool:
    # Good generic guard for projected meter coordinates in this pipeline.
    # Prevents line IDs/counts like 1, 2, 34 from becoming fake points near (0, 0).
    return abs(float(x)) > 10_000 and abs(float(y)) > 10_000


def _choose_xyxy_from_numbers(vals: list[float]) -> tuple[float, float, float, float] | None:
    if len(vals) < 4:
        return None

    # Prefer the last valid coordinate quartet because many simple control files
    # are formatted as: id/group x1 y1 x2 y2.
    candidates = []

    for i in range(0, len(vals) - 3):
        x1, y1, x2, y2 = vals[i:i + 4]
        if _looks_like_projected_xy(x1, y1) and _looks_like_projected_xy(x2, y2):
            candidates.append((x1, y1, x2, y2))

    return candidates[-1] if candidates else None


def make_line_endpoint_gdf_from_crs_file(path: Path, target_crs: str, stack: dict[str, Any]):
    gpd = stack["gpd"]
    Point = stack["Point"]

    points = []
    skipped = 0

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            vals = []
            for tok in line.replace(",", " ").split():
                try:
                    vals.append(float(tok))
                except Exception:
                    pass

            quad = _choose_xyxy_from_numbers(vals)

            if quad is None:
                skipped += 1
                continue

            x1, y1, x2, y2 = quad
            points.append((x1, y1))
            points.append((x2, y2))

    geoms = [Point(x, y) for x, y in points]
    gdf = gpd.GeoDataFrame(
        {"x": [p[0] for p in points], "y": [p[1] for p in points]},
        geometry=geoms,
        crs=target_crs,
    )
    gdf.attrs["skipped_lines"] = skipped
    return gdf

def point_gdf_meta(label: str, gdf, target_crs: str) -> dict[str, Any]:
    if gdf.empty:
        return {
            "label": label,
            "kind": "points",
            "target_crs": target_crs,
            "rows": 0,
            "bounds": None,
            "_geometry": None,
        }

    geoms = gdf.geometry.dropna()
    geom = geoms.union_all() if hasattr(geoms, "union_all") else geoms.unary_union
    return {
        "label": label,
        "kind": "points",
        "target_crs": target_crs,
        "rows": int(len(gdf)),
        "bounds": bounds_dict(tuple(float(v) for v in gdf.total_bounds)),
        "_geometry": geom,
    }


def check_meta_against_reference(
    *,
    checks: list[dict[str, Any]],
    subject_label: str,
    subject_meta: dict[str, Any],
    reference_label: str,
    reference_meta: dict[str, Any],
    stack: dict[str, Any],
    fail_if_no_overlap: bool = True,
    warn_small_overlap: float = 0.98,
) -> None:
    frac = bbox_overlap_fraction(subject_meta, reference_meta, stack)
    dist = distance_between_bboxes(subject_meta, reference_meta, stack)

    detail = (
        f"{subject_label} bbox overlap within {reference_label}: {frac:.3f}; "
        f"bbox distance: {dist:.2f} m"
    )

    if frac <= 0.0 and fail_if_no_overlap:
        add_check(
            checks,
            "bad",
            f"{subject_label} does not overlap {reference_label} bounds.",
            detail,
            {"overlap_fraction": frac, "distance_m": dist},
        )
    elif frac < warn_small_overlap:
        add_check(
            checks,
            "warn",
            f"{subject_label} only partially overlaps {reference_label} bounds.",
            detail,
            {"overlap_fraction": frac, "distance_m": dist},
        )
    else:
        add_check(
            checks,
            "good",
            f"{subject_label} overlaps {reference_label} bounds.",
            detail,
            {"overlap_fraction": frac, "distance_m": dist},
        )


def geometry_distance_check(
    *,
    checks: list[dict[str, Any]],
    subject_label: str,
    subject_geom,
    reference_label: str,
    reference_geom,
    warn_distance_m: float,
    bad_distance_m: float,
) -> None:
    if subject_geom is None or reference_geom is None:
        return

    dist = float(subject_geom.distance(reference_geom))

    if dist > bad_distance_m:
        add_check(
            checks,
            "bad",
            f"{subject_label} is far from {reference_label}.",
            f"distance={dist:.2f} m; bad threshold={bad_distance_m:.2f} m",
            {"distance_m": dist},
        )
    elif dist > warn_distance_m:
        add_check(
            checks,
            "warn",
            f"{subject_label} is not especially close to {reference_label}.",
            f"distance={dist:.2f} m; warning threshold={warn_distance_m:.2f} m",
            {"distance_m": dist},
        )
    else:
        add_check(
            checks,
            "good",
            f"{subject_label} is close to {reference_label}.",
            f"distance={dist:.2f} m",
            {"distance_m": dist},
        )


def run_geometry_check(cfg: dict[str, Any]) -> dict[str, Any]:
    stack = import_geo_stack()
    checks: list[dict[str, Any]] = []

    target_crs = model_crs_from_cfg(cfg)
    dx = float(cfg.get("grid_dx_m") or cfg.get("grid_resolution_m") or 100.0)
    dy = float(cfg.get("grid_dy_m") or cfg.get("grid_resolution_m") or 100.0)
    buffer_m = float(cfg.get("open_boundary_outline_buffer_m") or 150.0)
    edge_warn_m = max(3.0 * max(dx, dy), 2.0 * buffer_m, 300.0)
    edge_bad_m = max(10.0 * max(dx, dy), 5.0 * buffer_m, 1000.0)

    report: dict[str, Any] = {
        "created_at": now_iso(),
        "target_crs": target_crs,
        "settings": {
            "grid_dx_m": dx,
            "grid_dy_m": dy,
            "open_boundary_outline_buffer_m": buffer_m,
            "edge_warn_m": edge_warn_m,
            "edge_bad_m": edge_bad_m,
        },
        "inputs": {},
        "checks": checks,
    }

    dem_path = first_path_from_list(cfg.get("dem_paths")) or path_from_hydromt_dem_sources(cfg)
    active_mask_path = cfg_path(cfg, "active_mask_path")
    region_path = cfg_path(cfg, "region_path")
    outline_path = cfg_path(cfg, "open_boundary_outline_path")
    thin_dam_path = cfg_path(cfg, "thin_dam_path")
    discharge_points_path = cfg_path(cfg, "discharge_points_csv_path")
    obs_points_path = cfg_path(cfg, "obs_points_path")
    obs_lines_path = cfg_path(cfg, "obs_lines_path")

    metas: dict[str, dict[str, Any]] = {}

    def require_file(label: str, path: Path | None, required: bool = True) -> bool:
        if path is None:
            add_check(
                checks,
                "bad" if required else "warn",
                f"{label} path is blank.",
                "Set the path or disable the related feature.",
            )
            return False
        if not path.exists():
            add_check(checks, "bad", f"{label} file does not exist.", str(path))
            return False
        add_check(checks, "good", f"{label} file exists.", str(path))
        return True

    if require_file("DEM", dem_path, required=True):
        metas["dem"] = read_raster_meta(dem_path, target_crs, stack)
        report["inputs"]["dem"] = {k: v for k, v in metas["dem"].items() if not k.startswith("_")}
        add_check(
            checks,
            "good",
            "DEM metadata read successfully.",
            f"CRS={metas['dem']['crs']}; size={metas['dem']['width_px']}x{metas['dem']['height_px']}; res={metas['dem']['res']}",
        )

    if active_mask_path is not None:
        if require_file("active_mask_path", active_mask_path, required=False):
            metas["active_mask"] = read_raster_meta(active_mask_path, target_crs, stack)
            report["inputs"]["active_mask"] = {k: v for k, v in metas["active_mask"].items() if not k.startswith("_")}
            add_check(
                checks,
                "good",
                "Active mask raster metadata read successfully.",
                f"CRS={metas['active_mask']['crs']}; size={metas['active_mask']['width_px']}x{metas['active_mask']['height_px']}; res={metas['active_mask']['res']}",
            )

    if region_path is not None:
        if require_file("region_path", region_path, required=False):
            metas["region"] = read_vector_meta(region_path, target_crs, stack)
            report["inputs"]["region"] = {k: v for k, v in metas["region"].items() if not k.startswith("_")}
            if metas["region"]["rows"] <= 0:
                add_check(checks, "bad", "Region geometry is empty.", str(region_path))
            else:
                add_check(
                    checks,
                    "good",
                    "Region geometry read successfully.",
                    f"CRS={metas['region']['crs']}; rows={metas['region']['rows']}; types={metas['region']['geometry_types']}",
                )

    if str(cfg.get("open_boundary_mask_mode") or "").strip() == "coastal_outline":
        if require_file("open_boundary_outline_path", outline_path, required=True):
            metas["outline"] = read_vector_meta(outline_path, target_crs, stack)
            report["inputs"]["open_boundary_outline"] = {k: v for k, v in metas["outline"].items() if not k.startswith("_")}
            if metas["outline"]["rows"] <= 0:
                add_check(checks, "bad", "Coastal outline is empty.", str(outline_path))
            else:
                allowed_types = {"LineString", "MultiLineString", "Polygon", "MultiPolygon"}
                found_types = set(metas["outline"]["geometry_types"])
                if found_types and found_types.issubset(allowed_types):
                    add_check(
                        checks,
                        "good",
                        "Coastal outline geometry type is supported.",
                        f"types={sorted(found_types)}; rows={metas['outline']['rows']}",
                    )
                else:
                    add_check(
                        checks,
                        "warn",
                        "Coastal outline geometry type is unusual.",
                        f"types={sorted(found_types)}; expected line or polygon geometry.",
                    )

                if metas["outline"]["crs"] is None:
                    add_check(checks, "bad", "Coastal outline CRS is missing.", "Save the file with CRS, preferably EPSG:32615.")
                else:
                    add_check(checks, "good", "Coastal outline CRS is present.", metas["outline"]["crs"])

    # Bounds consistency.
    if "dem" in metas and "active_mask" in metas:
        check_meta_against_reference(
            checks=checks,
            subject_label="active_mask_path",
            subject_meta=metas["active_mask"],
            reference_label="DEM",
            reference_meta=metas["dem"],
            stack=stack,
            fail_if_no_overlap=True,
            warn_small_overlap=0.95,
        )

    if "dem" in metas and "region" in metas:
        check_meta_against_reference(
            checks=checks,
            subject_label="region_path",
            subject_meta=metas["region"],
            reference_label="DEM",
            reference_meta=metas["dem"],
            stack=stack,
            fail_if_no_overlap=True,
            warn_small_overlap=0.50,
        )

    if "dem" in metas and "outline" in metas:
        check_meta_against_reference(
            checks=checks,
            subject_label="open_boundary_outline_path",
            subject_meta=metas["outline"],
            reference_label="DEM",
            reference_meta=metas["dem"],
            stack=stack,
            fail_if_no_overlap=True,
            warn_small_overlap=0.90,
        )

    if "active_mask" in metas and "outline" in metas:
        check_meta_against_reference(
            checks=checks,
            subject_label="open_boundary_outline_path",
            subject_meta=metas["outline"],
            reference_label="active_mask_path",
            reference_meta=metas["active_mask"],
            stack=stack,
            fail_if_no_overlap=True,
            warn_small_overlap=0.80,
        )

    if "region" in metas and "outline" in metas:
        check_meta_against_reference(
            checks=checks,
            subject_label="open_boundary_outline_path",
            subject_meta=metas["outline"],
            reference_label="region_path",
            reference_meta=metas["region"],
            stack=stack,
            fail_if_no_overlap=True,
            warn_small_overlap=0.80,
        )

        region_boundary = metas["region"]["_geometry"].boundary if metas["region"].get("_geometry") else None
        outline_geom = metas["outline"].get("_geometry")
        geometry_distance_check(
            checks=checks,
            subject_label="Coastal outline",
            subject_geom=outline_geom,
            reference_label="region boundary",
            reference_geom=region_boundary,
            warn_distance_m=edge_warn_m,
            bad_distance_m=edge_bad_m,
        )

    # Optional point/vector datasets.
    if thin_dam_path is not None and thin_dam_path.exists():
        try:
            metas["thin_dam"] = read_vector_meta(thin_dam_path, target_crs, stack)
            report["inputs"]["thin_dam"] = {k: v for k, v in metas["thin_dam"].items() if not k.startswith("_")}
            if "dem" in metas:
                check_meta_against_reference(
                    checks=checks,
                    subject_label="thin_dam_path",
                    subject_meta=metas["thin_dam"],
                    reference_label="DEM",
                    reference_meta=metas["dem"],
                    stack=stack,
                    fail_if_no_overlap=False,
                    warn_small_overlap=0.20,
                )
        except Exception as exc:
            add_check(checks, "warn", "Thin-dam vector geometry check failed.", f"{type(exc).__name__}: {exc}")

    if discharge_points_path is not None and discharge_points_path.exists():
        try:
            x_col = str(cfg.get("discharge_points_x_column") or "x")
            y_col = str(cfg.get("discharge_points_y_column") or "y")
            gdf = make_point_gdf_from_xy_csv(discharge_points_path, x_col, y_col, target_crs, stack)
            metas["discharge_points"] = point_gdf_meta("discharge_points", gdf, target_crs)
            report["inputs"]["discharge_points"] = {k: v for k, v in metas["discharge_points"].items() if not k.startswith("_")}
            x_used = gdf.attrs.get("x_col", x_col)
            y_used = gdf.attrs.get("y_col", y_col)
            
            if x_used != x_col or y_used != y_col:
                add_check(
                    checks,
                    "warn",
                    "Discharge source point x/y columns were inferred.",
                    f"Requested x/y={x_col}/{y_col}; using {x_used}/{y_used}.",
                )
            
            add_check(
                checks,
                "good",
                "Discharge source points read successfully.",
                f"points={len(gdf)}; x_col={x_used}; y_col={y_used}",
            )
            if "dem" in metas:
                check_meta_against_reference(
                    checks=checks,
                    subject_label="discharge_points_csv_path",
                    subject_meta=metas["discharge_points"],
                    reference_label="DEM",
                    reference_meta=metas["dem"],
                    stack=stack,
                    fail_if_no_overlap=True,
                    warn_small_overlap=0.80,
                )
        except Exception as exc:
            add_check(checks, "bad", "Discharge source point geometry check failed.", f"{type(exc).__name__}: {exc}")

    if obs_points_path is not None and obs_points_path.exists():
        try:
            gdf = make_point_gdf_from_xy_file(obs_points_path, target_crs, stack)
            metas["obs_points"] = point_gdf_meta("obs_points", gdf, target_crs)
            report["inputs"]["obs_points"] = {k: v for k, v in metas["obs_points"].items() if not k.startswith("_")}
            add_check(checks, "good", "Observation points read successfully.", f"points={len(gdf)}")
            if "dem" in metas:
                check_meta_against_reference(
                    checks=checks,
                    subject_label="obs_points_path",
                    subject_meta=metas["obs_points"],
                    reference_label="DEM",
                    reference_meta=metas["dem"],
                    stack=stack,
                    fail_if_no_overlap=False,
                    warn_small_overlap=0.80,
                )
        except Exception as exc:
            add_check(checks, "warn", "Observation point geometry check failed.", f"{type(exc).__name__}: {exc}")

    if obs_lines_path is not None and obs_lines_path.exists():
        try:
            gdf = make_line_endpoint_gdf_from_crs_file(obs_lines_path, target_crs, stack)
            metas["obs_line_endpoints"] = point_gdf_meta("obs_line_endpoints", gdf, target_crs)
            report["inputs"]["obs_line_endpoints"] = {k: v for k, v in metas["obs_line_endpoints"].items() if not k.startswith("_")}
            add_check(checks, "good", "Observation line endpoints read successfully.", f"endpoints={len(gdf)}")
            if "dem" in metas:
                check_meta_against_reference(
                    checks=checks,
                    subject_label="obs_lines_path endpoints",
                    subject_meta=metas["obs_line_endpoints"],
                    reference_label="DEM",
                    reference_meta=metas["dem"],
                    stack=stack,
                    fail_if_no_overlap=False,
                    warn_small_overlap=0.80,
                )
        except Exception as exc:
            add_check(checks, "warn", "Observation line endpoint geometry check failed.", f"{type(exc).__name__}: {exc}")

    status = overall_status(checks)
    report["status"] = status
    report["ok"] = status != "bad"
    report["summary"] = {
        "good": sum(1 for item in checks if item["status"] == "good"),
        "warn": sum(1 for item in checks if item["status"] == "warn"),
        "bad": sum(1 for item in checks if item["status"] == "bad"),
        "total": len(checks),
    }

    return report


def format_text_report(report: dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 100)
    lines.append("MANUAL GEOMETRY CHECK")
    lines.append("=" * 100)
    lines.append(f"created_at: {report.get('created_at')}")
    lines.append(f"target_crs: {report.get('target_crs')}")
    lines.append(f"status: {report.get('status')}")
    lines.append(f"summary: {report.get('summary')}")
    lines.append("")

    for item in report.get("checks", []):
        label = item.get("status", "").upper()
        name = item.get("name", "")
        detail = item.get("detail", "")
        lines.append(f"[{label}] {name}")
        if detail:
            lines.append(f"       {detail}")

    lines.append("")
    lines.append("=" * 100)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to Manual run_config.json")
    parser.add_argument("--json-out", default="", help="Optional output JSON path")
    args = parser.parse_args()

    config_path = Path(args.config)
    json_out = Path(args.json_out) if args.json_out else None

    try:
        cfg = read_json(config_path)
        report = run_geometry_check(cfg)
        report["config_path"] = str(config_path)

        if json_out is not None:
            write_json(json_out, report)

        print(format_text_report(report), flush=True)
        return 0 if report.get("ok") else 2

    except Exception as exc:
        failure = {
            "created_at": now_iso(),
            "ok": False,
            "status": "bad",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
            "config_path": str(config_path),
        }

        if json_out is not None:
            write_json(json_out, failure)

        print("MANUAL GEOMETRY CHECK FAILED", file=sys.stderr)
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())