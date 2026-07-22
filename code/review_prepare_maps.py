#!/usr/bin/env python3
# -*- coding: utf-8 -*----
"""
Created on Wed Jun 17 16:14:28 2026

@author: epsilon
"""

from pathlib import Path
import argparse
import datetime as dt
import json
import traceback

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm, colors

import xarray as xr

try:
    from pyproj import Transformer
except Exception:
    Transformer = None


DEFAULT_RUN = Path("/proj/zefflab/projects/Flooding/sfincs_runs/harvey_2017_mrms_manual_020")


LAYER_SPECS = [
    {
        "layer_id": "max_depth",
        "title": "Max flood depth",
        "candidates": ["hmax", "max_h", "flood_depth_max", "depth_max", "h"],
        "units_fallback": "m",
        "cmap": "turbo",
        "mask_min": 0.05,
        "description": "Maximum modeled water depth above local ground/bed.",
        "cmap": "turbo",
        "alpha": 1.00,
        "mask_min": 0.05,
        "saturation": 1.55,
        "brightness": 1.22,
        "gamma": 0.58,
    },
    {
        "layer_id": "max_water_level",
        "title": "Max water level",
        "candidates": ["zsmax", "max_zs", "waterlevel_max", "water_level_max", "zs"],
        "units_fallback": "m",
        "cmap": "turbo",
        "mask_min": 0.05,
        "description": "Maximum modeled water-surface elevation relative to the model vertical datum.",
        "cmap": "turbo",
        "alpha": 1.00,
        "mask_min": 0.05,
        "saturation": 1.45,
        "brightness": 1.18,
        "gamma": 0.65,
    },
]

MAP_PAD_FRAC = 0.04
MAP_DPI = 160
MAP_FRAME_MAX_IN = 9.4


def build_map_frame(xg, yg, pad_frac=MAP_PAD_FRAC):
    x = np.asarray(xg, dtype="float64")
    y = np.asarray(yg, dtype="float64")

    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]

    if x.size == 0 or y.size == 0:
        return None

    data_xmin = float(np.nanmin(x))
    data_xmax = float(np.nanmax(x))
    data_ymin = float(np.nanmin(y))
    data_ymax = float(np.nanmax(y))

    dx = data_xmax - data_xmin
    dy = data_ymax - data_ymin

    if dx <= 0 or dy <= 0:
        return None

    pad_x = dx * float(pad_frac)
    pad_y = dy * float(pad_frac)

    xmin = data_xmin - pad_x
    xmax = data_xmax + pad_x
    ymin = data_ymin - pad_y
    ymax = data_ymax + pad_y

    frame_dx = xmax - xmin
    frame_dy = ymax - ymin
    aspect = frame_dx / frame_dy

    if aspect >= 1:
        fig_w = MAP_FRAME_MAX_IN
        fig_h = MAP_FRAME_MAX_IN / aspect
    else:
        fig_h = MAP_FRAME_MAX_IN
        fig_w = MAP_FRAME_MAX_IN * aspect

    width_px = int(round(fig_w * MAP_DPI))
    height_px = int(round(fig_h * MAP_DPI))

    return {
        "xmin": float(xmin),
        "xmax": float(xmax),
        "ymin": float(ymin),
        "ymax": float(ymax),
        "data_extent": {
            "xmin": float(data_xmin),
            "xmax": float(data_xmax),
            "ymin": float(data_ymin),
            "ymax": float(data_ymax),
        },
        "pad_frac": float(pad_frac),
        "aspect": float(aspect),
        "figsize_in": [float(fig_w), float(fig_h)],
        "dpi": int(MAP_DPI),
        "image": {
            "width_px": int(width_px),
            "height_px": int(height_px),
        },
        "source": "review_prepare_maps shared padded render frame",
    }


def make_map_frame_figure(map_frame, transparent=False):
    fig_w, fig_h = map_frame["figsize_in"]

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=int(map_frame.get("dpi", MAP_DPI)))

    if transparent:
        fig.patch.set_alpha(0.0)

    ax.set_xlim(float(map_frame["xmin"]), float(map_frame["xmax"]))
    ax.set_ylim(float(map_frame["ymin"]), float(map_frame["ymax"]))
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_position([0, 0, 1, 1])

    for spine in ax.spines.values():
        spine.set_visible(False)

    return fig, ax

def postprocess_satellite_png(path, saturation=0.42, brightness=0.96, contrast=0.82, haze=0.18):
    try:
        img = plt.imread(path).astype("float32")
    except Exception:
        return False

    if img.max() > 1.0:
        img = img / 255.0

    if img.ndim != 3 or img.shape[2] < 3:
        return False

    rgb = img[..., :3]
    alpha = img[..., 3:4] if img.shape[2] >= 4 else np.ones((*rgb.shape[:2], 1), dtype="float32")

    lum = (
        0.2126 * rgb[..., 0:1] +
        0.7152 * rgb[..., 1:2] +
        0.0722 * rgb[..., 2:3]
    )

    # Muted, not spooky: reduce saturation, soften contrast, keep it bright.
    rgb = lum + (rgb - lum) * float(saturation)
    rgb = (rgb - 0.5) * float(contrast) + 0.5
    rgb = rgb * float(brightness)

    # Add a light white haze so the satellite becomes a pale basemap.
    rgb = rgb * (1.0 - float(haze)) + float(haze)

    out = np.concatenate([np.clip(rgb, 0, 1), alpha], axis=2)
    plt.imsave(path, out)
    return True
def now_iso():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def read_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def clean_rel(path, run_root):
    return str(Path(path).resolve().relative_to(run_root.resolve()))


def status_path(run_root):
    return run_root / "review" / "maps" / "map_status.json"


def set_status(run_root, state, **extra):
    payload = {
        "state": state,
        "updated_at": now_iso(),
        **extra,
    }
    write_json(status_path(run_root), payload)


def find_model_map_nc(run_root):
    candidates = [
        run_root / "model" / "sfincs_map.nc",
        run_root / "sfincs_map.nc",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Could not find sfincs_map.nc under {run_root}")


def get_epsg_from_config(run_root):
    cfg = read_json(run_root / "run_config.json")

    raw = cfg.get("grid_crs") or cfg.get("crs")
    if isinstance(raw, str):
        text = raw.upper().replace("EPSG:", "").strip()
        if text.isdigit():
            return int(text)

    adv = cfg.get("advanced_config")
    if isinstance(adv, dict):
        epsg = adv.get("epsg")
        if epsg:
            return int(epsg)

    epsg = cfg.get("epsg")
    if epsg:
        return int(epsg)

    return None


def find_variable(ds, candidates):
    lower_lookup = {name.lower(): name for name in ds.data_vars}
    for cand in candidates:
        if cand.lower() in lower_lookup:
            return lower_lookup[cand.lower()]
    return None


def reduce_to_2d(da, prefer_max=True):
    work = da

    # Reduce time-like dimensions by max for review map products.
    for dim in list(work.dims):
        low = dim.lower()
        if "time" in low or low in {"t", "nt"}:
            if prefer_max:
                work = work.max(dim=dim, skipna=True)
            else:
                work = work.isel({dim: -1})

    work = work.squeeze(drop=True)

    # If any extra singleton/nonspatial dimensions remain, take first index.
    while work.ndim > 2:
        dim = work.dims[0]
        work = work.isel({dim: 0}).squeeze(drop=True)

    arr = np.asarray(work.values, dtype="float64")

    if arr.ndim != 2:
        raise ValueError(
            f"Variable {da.name!r} reduced to shape {arr.shape}, not a 2D grid. "
            "This V1 map builder expects regular 2D SFINCS map output."
        )

    return arr, work


def get_xy_grid(ds, da2d, arr):
    rows, cols = arr.shape

    x_names = ["x", "xc", "xcor", "mesh2d_face_x"]
    y_names = ["y", "yc", "ycor", "mesh2d_face_y"]

    for x_name in x_names:
        for y_name in y_names:
            if x_name not in ds.variables or y_name not in ds.variables:
                continue

            x = np.asarray(ds[x_name].values, dtype="float64")
            y = np.asarray(ds[y_name].values, dtype="float64")

            if x.shape == arr.shape and y.shape == arr.shape:
                return x, y, x_name, y_name

            if x.ndim == 1 and y.ndim == 1:
                if len(x) == cols and len(y) == rows:
                    xx, yy = np.meshgrid(x, y)
                    return xx, yy, x_name, y_name

                if len(x) == rows and len(y) == cols:
                    yy, xx = np.meshgrid(y, x)
                    if xx.shape == arr.shape and yy.shape == arr.shape:
                        return xx, yy, x_name, y_name

    # Try coordinates attached to the DataArray.
    for x_name in x_names:
        for y_name in y_names:
            if x_name not in da2d.coords or y_name not in da2d.coords:
                continue

            x = np.asarray(da2d.coords[x_name].values, dtype="float64")
            y = np.asarray(da2d.coords[y_name].values, dtype="float64")

            if x.shape == arr.shape and y.shape == arr.shape:
                return x, y, x_name, y_name

            if x.ndim == 1 and y.ndim == 1 and len(x) == cols and len(y) == rows:
                xx, yy = np.meshgrid(x, y)
                return xx, yy, x_name, y_name

    raise ValueError(
        "Could not find usable x/y coordinates in sfincs_map.nc. "
        "Need x/y or xc/yc as 1D or 2D variables."
    )


def latlon_bounds(xg, yg, epsg):
    xmin = float(np.nanmin(xg))
    xmax = float(np.nanmax(xg))
    ymin = float(np.nanmin(yg))
    ymax = float(np.nanmax(yg))

    raw_bounds = {
        "xmin": xmin,
        "xmax": xmax,
        "ymin": ymin,
        "ymax": ymax,
        "epsg": epsg,
    }

    if epsg is None or Transformer is None:
        return None, raw_bounds

    transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    corners = [
        transformer.transform(xmin, ymin),
        transformer.transform(xmin, ymax),
        transformer.transform(xmax, ymin),
        transformer.transform(xmax, ymax),
    ]
    lons = [c[0] for c in corners]
    lats = [c[1] for c in corners]

    # Leaflet-style image bounds: [[south, west], [north, east]]
    return [[min(lats), min(lons)], [max(lats), max(lons)]], raw_bounds


def orient_array_for_web(arr, xg, yg):
    out = np.array(arr, copy=True)

    # Image top row should be north. If row index increases northward, flip vertically.
    first_row_y = float(np.nanmean(yg[0, :]))
    last_row_y = float(np.nanmean(yg[-1, :]))
    if last_row_y > first_row_y:
        out = np.flipud(out)

    # Image left column should be west. If column index decreases eastward, flip horizontally.
    first_col_x = float(np.nanmean(xg[:, 0]))
    last_col_x = float(np.nanmean(xg[:, -1]))
    if last_col_x < first_col_x:
        out = np.fliplr(out)

    return out


def robust_limits(arr, mask):
    vals = arr[np.isfinite(arr) & mask]
    if vals.size == 0:
        raise ValueError("No valid values available for layer.")

    vmin = float(np.nanpercentile(vals, 2))
    vmax = float(np.nanpercentile(vals, 98))

    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin = float(np.nanmin(vals))
        vmax = float(np.nanmax(vals))

    if vmin == vmax:
        vmax = vmin + 1.0

    return vmin, vmax, float(np.nanmin(vals)), float(np.nanmax(vals)), float(np.nanmean(vals))


def boost_rgb(rgb, saturation=1.0, brightness=1.0):
    rgb = np.clip(rgb, 0, 1).astype("float32")

    # Perceptual-ish luminance.
    lum = (
        0.2126 * rgb[..., 0:1] +
        0.7152 * rgb[..., 1:2] +
        0.0722 * rgb[..., 2:3]
    )

    out = lum + (rgb - lum) * float(saturation)
    out = out * float(brightness)
    return np.clip(out, 0, 1)



def save_overlay_png(arr, xg, yg, out_path, cmap_name, alpha, vmin, vmax, mask,
                     saturation=1.0, brightness=1.0, gamma=1.0):
    image_arr = orient_array_for_web(arr, xg, yg)
    image_mask = orient_array_for_web(mask.astype(float), xg, yg) > 0.5

    scaled = (image_arr - vmin) / max((vmax - vmin), 1e-12)
    scaled = np.clip(scaled, 0, 1)

    # gamma < 1 makes low/mid flood values visually punchier.
    scaled = scaled ** float(gamma)

    cmap = cm.get_cmap(cmap_name)
    rgba = cmap(scaled)

    rgba[..., :3] = boost_rgb(
        rgba[..., :3],
        saturation=saturation,
        brightness=brightness,
    )

    rgba[..., 3] = np.where(np.isfinite(image_arr) & image_mask, alpha, 0.0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(out_path, rgba)


def dilate_bool(mask, iterations=1):
    out = np.asarray(mask, dtype=bool)

    for _ in range(int(iterations)):
        p = np.pad(out, 1, mode="constant", constant_values=False)
        out = (
            p[1:-1, 1:-1] |
            p[:-2, 1:-1] |
            p[2:, 1:-1] |
            p[1:-1, :-2] |
            p[1:-1, 2:] |
            p[:-2, :-2] |
            p[:-2, 2:] |
            p[2:, :-2] |
            p[2:, 2:]
        )

    return out


def erode_bool(mask, iterations=1):
    out = np.asarray(mask, dtype=bool)

    for _ in range(int(iterations)):
        p = np.pad(out, 1, mode="constant", constant_values=False)
        out = (
            p[1:-1, 1:-1] &
            p[:-2, 1:-1] &
            p[2:, 1:-1] &
            p[1:-1, :-2] &
            p[1:-1, 2:] &
            p[:-2, :-2] &
            p[:-2, 2:] &
            p[2:, :-2] &
            p[2:, 2:]
        )

    return out


def save_flood_halo_png(mask, xg, yg, out_path):
    wet = np.asarray(mask, dtype=bool)

    if not np.any(wet):
        return False

    # Wide black outer halo + thinner white/yellow edge.
    outer = dilate_bool(wet, iterations=4) & ~wet
    edge = wet & ~erode_bool(wet, iterations=2)
    near_edge = dilate_bool(edge, iterations=1)

    rows, cols = wet.shape
    rgba = np.zeros((rows, cols, 4), dtype="float32")

    # Black outside glow.
    rgba[..., 0] = np.where(outer, 0.02, rgba[..., 0])
    rgba[..., 1] = np.where(outer, 0.02, rgba[..., 1])
    rgba[..., 2] = np.where(outer, 0.02, rgba[..., 2])
    rgba[..., 3] = np.where(outer, 0.82, rgba[..., 3])

    # Bright inner edge.
    rgba[..., 0] = np.where(near_edge, 1.00, rgba[..., 0])
    rgba[..., 1] = np.where(near_edge, 0.95, rgba[..., 1])
    rgba[..., 2] = np.where(near_edge, 0.18, rgba[..., 2])
    rgba[..., 3] = np.where(near_edge, 0.95, rgba[..., 3])

    image_rgba = np.zeros_like(rgba)
    for band in range(4):
        image_rgba[..., band] = orient_array_for_web(rgba[..., band], xg, yg)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(out_path, np.clip(image_rgba, 0, 1))
    return True




def save_legend_png(out_path, cmap_name, vmin, vmax, units, title):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(1.2, 5.2))
    fig.subplots_adjust(left=0.45, right=0.8, top=0.98, bottom=0.02)

    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    sm = cm.ScalarMappable(norm=norm, cmap=plt.get_cmap(cmap_name))
    sm.set_array([])

    cbar = fig.colorbar(sm, cax=ax, orientation="vertical")
    label = title if not units else f"{title} ({units})"
    cbar.set_label(label, rotation=90, labelpad=10)

    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def save_preview_png(arr, xg, yg, out_path, cmap_name, vmin, vmax, units, title, mask):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plot_arr = np.where(mask, arr, np.nan)

    fig, ax = plt.subplots(figsize=(8.8, 7.0))
    ax.pcolormesh(xg, yg, plot_arr, shading="auto", cmap=cmap_name, vmin=vmin, vmax=vmax)

    ax.set_title(title, pad=6)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.01)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def active_crop_slices(ds, pad=20):
    if "msk" not in ds.variables:
        return None

    msk = np.asarray(ds["msk"].values)
    if msk.ndim != 2:
        return None

    active = np.isfinite(msk) & (msk > 0)
    if not np.any(active):
        return None

    rr, cc = np.where(active)
    r0 = max(0, int(rr.min()) - pad)
    r1 = min(msk.shape[0], int(rr.max()) + pad + 1)
    c0 = max(0, int(cc.min()) - pad)
    c1 = min(msk.shape[1], int(cc.max()) + pad + 1)

    return slice(r0, r1), slice(c0, c1)


def apply_crop(arr, crop_slices):
    if crop_slices is None:
        return arr
    rs, cs = crop_slices
    return arr[rs, cs]


def build_layer(ds, run_root, maps_dir, spec, epsg, crop_slices=None):
    var_name = find_variable(ds, spec["candidates"])
    derived_from = None

    if var_name:
        arr, da2d = reduce_to_2d(ds[var_name], prefer_max=True)
        source_variable = var_name
        units = ds[var_name].attrs.get("units") or spec["units_fallback"]

    elif spec["layer_id"] == "max_depth":
        wl_name = find_variable(ds, ["zsmax", "max_zs", "waterlevel_max", "water_level_max", "zs"])
        bed_name = find_variable(ds, ["zb", "bed", "bed_level", "zbed", "dep", "elevation", "terrain"])

        if not wl_name or not bed_name:
            return None

        wl_arr, wl_da2d = reduce_to_2d(ds[wl_name], prefer_max=True)
        bed_arr, _ = reduce_to_2d(ds[bed_name], prefer_max=False)

        if wl_arr.shape != bed_arr.shape:
            raise ValueError(
                f"Cannot derive max depth because {wl_name} shape {wl_arr.shape} "
                f"does not match {bed_name} shape {bed_arr.shape}."
            )

        arr = np.maximum(wl_arr - bed_arr, 0.0)
        da2d = wl_da2d
        source_variable = f"derived:{wl_name}-{bed_name}"
        derived_from = {
            "water_level_variable": wl_name,
            "bed_variable": bed_name,
            "formula": "max(water_level - bed, 0)",
        }
        units = ds[wl_name].attrs.get("units") or spec["units_fallback"]

    else:
        return None

    xg, yg, x_name, y_name = get_xy_grid(ds, da2d, arr)
    arr = apply_crop(arr, crop_slices)
    xg = apply_crop(xg, crop_slices)
    yg = apply_crop(yg, crop_slices)

    base_mask = np.isfinite(arr)
    if spec["mask_min"] is not None:
        base_mask = base_mask & (arr > float(spec["mask_min"]))

    vmin, vmax, raw_min, raw_max, mean_val = robust_limits(arr, base_mask)

    overlay_path = maps_dir / f"{spec['layer_id']}_overlay.png"
    legend_path = maps_dir / f"{spec['layer_id']}_legend.png"
    preview_path = maps_dir / f"{spec['layer_id']}_preview.png"
    halo_path = maps_dir / f"{spec['layer_id']}_halo.png"
    halo_relpath = None

    save_overlay_png(
        arr=arr,
        xg=xg,
        yg=yg,
        out_path=overlay_path,
        cmap_name=spec["cmap"],
        alpha=spec["alpha"],
        vmin=vmin,
        vmax=vmax,
        mask=base_mask,
        saturation=spec.get("saturation", 1.0),
        brightness=spec.get("brightness", 1.0),
        gamma=spec.get("gamma", 1.0),
    )
    
    
    halo_mask = None

    if spec["layer_id"] == "max_depth":
        halo_mask = np.isfinite(arr) & (arr > max(float(spec["mask_min"] or 0.01), 0.03))

    elif spec["layer_id"] == "max_water_level":
        bed_name = find_variable(ds, ["zb", "bed", "bed_level", "zbed", "dep", "elevation", "terrain"])
        if bed_name:
            bed_arr, _ = reduce_to_2d(ds[bed_name], prefer_max=False)
            bed_arr = apply_crop(bed_arr, crop_slices)

            if bed_arr.shape == arr.shape:
                depth_like = np.maximum(arr - bed_arr, 0.0)
                halo_mask = np.isfinite(depth_like) & (depth_like > 0.03)

    if halo_mask is not None and save_flood_halo_png(halo_mask, xg, yg, halo_path):
        halo_relpath = clean_rel(halo_path, run_root)

    save_legend_png(
        out_path=legend_path,
        cmap_name=spec["cmap"],
        vmin=vmin,
        vmax=vmax,
        units=units,
        title=spec["title"],
    )

    save_preview_png(
        arr=arr,
        xg=xg,
        yg=yg,
        out_path=preview_path,
        cmap_name=spec["cmap"],
        vmin=vmin,
        vmax=vmax,
        units=units,
        title=spec["title"],
        mask=base_mask,
    )

    bounds_ll, raw_bounds = latlon_bounds(xg, yg, epsg)

    layer_meta = {
        "layer_id": spec["layer_id"],
        "title": spec["title"],
        "description": spec["description"],
        "source_variable": source_variable,
        "units": units,
        "overlay_relpath": clean_rel(overlay_path, run_root),
        "legend_relpath": clean_rel(legend_path, run_root),
        "preview_relpath": clean_rel(preview_path, run_root),
        "halo_relpath": halo_relpath,
        "bounds_latlon": bounds_ll,
        "raw_bounds": raw_bounds,
        "value_min": raw_min,
        "value_max": raw_max,
        "value_mean": mean_val,
        "render_vmin": vmin,
        "render_vmax": vmax,
        "x_coord": x_name,
        "y_coord": y_name,
        "shape": list(arr.shape),
    }

    if derived_from:
        layer_meta["derived_from"] = derived_from

    return layer_meta, arr, xg, yg




def make_empty_rgba_like(arr):
    rows, cols = arr.shape
    return np.zeros((rows, cols, 4), dtype="float32")


def save_rgba_array_png(rgba, xg, yg, out_path):
    out = orient_array_for_web(rgba, xg, yg) if rgba.ndim == 2 else rgba

    # For RGBA, apply the same orientation rules manually.
    if rgba.ndim == 3:
        out = np.array(rgba, copy=True)

        first_row_y = float(np.nanmean(yg[0, :]))
        last_row_y = float(np.nanmean(yg[-1, :]))
        if last_row_y > first_row_y:
            out = np.flipud(out)

        first_col_x = float(np.nanmean(xg[:, 0]))
        last_col_x = float(np.nanmean(xg[:, -1]))
        if last_col_x < first_col_x:
            out = np.fliplr(out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(out_path, np.clip(out, 0, 1))


def draw_square_marker(rgba, row, col, radius, color):
    rows, cols, _ = rgba.shape
    r0 = max(0, row - radius)
    r1 = min(rows, row + radius + 1)
    c0 = max(0, col - radius)
    c1 = min(cols, col + radius + 1)
    rgba[r0:r1, c0:c1, :] = color


def nearest_grid_index(xg, yg, x, y):
    dist2 = (xg - x) ** 2 + (yg - y) ** 2
    idx = int(np.nanargmin(dist2))
    row, col = np.unravel_index(idx, xg.shape)
    return row, col


def read_xy_points(path):
    points = []
    if not path or not Path(path).exists():
        return points

    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue

        parts = raw.replace(",", " ").split()
        nums = []
        for part in parts:
            try:
                nums.append(float(part))
            except ValueError:
                pass

        if len(nums) >= 2:
            points.append((nums[0], nums[1]))

    return points

def read_xy_or_xyxy_centers(path):
    points = []

    if not path or not Path(path).exists():
        return points

    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()

        if not raw or raw.startswith("#"):
            continue

        parts = raw.replace(",", " ").split()
        nums = []

        for part in parts:
            try:
                nums.append(float(part))
            except ValueError:
                pass

        if len(nums) >= 4:
            points.append(((nums[0] + nums[2]) / 2.0, (nums[1] + nums[3]) / 2.0))
        elif len(nums) >= 2:
            points.append((nums[0], nums[1]))

    return points


def find_existing_model_file(run_root, names):
    for name in names:
        path = run_root / "model" / name
        if path.exists():
            return path
    return None


def build_model_active_area_overlay(ds, run_root, maps_dir, xg, yg, crop_slices=None, map_frame=None):
    if "msk" not in ds.variables:
        return None

    msk = np.asarray(ds["msk"].values)
    if msk.ndim != 2:
        return None

    msk = apply_crop(msk, crop_slices)
    active = np.isfinite(msk) & (msk > 0)

    if not np.any(active):
        return None

    if map_frame is None:
        map_frame = build_map_frame(xg, yg, pad_frac=MAP_PAD_FRAC)

    if map_frame is None:
        return None

    out_path = maps_dir / "model_active_area_overlay.png"

    fig, ax = make_map_frame_figure(map_frame, transparent=True)

    active_float = np.where(active, 1.0, 0.0)

    ax.contour(
        xg,
        yg,
        active_float,
        levels=[0.5],
        colors=["#000000"],
        linewidths=4.0,
        linestyles="dotted",
        alpha=0.95,
    )

    ax.contour(
        xg,
        yg,
        active_float,
        levels=[0.5],
        colors=["#ffffff"],
        linewidths=2.4,
        linestyles="dotted",
        alpha=0.95,
    )

    ax.contour(
        xg,
        yg,
        active_float,
        levels=[0.5],
        colors=["#00e5ff"],
        linewidths=1.4,
        linestyles="dotted",
        alpha=1.0,
    )

    fig.savefig(out_path, dpi=int(map_frame.get("dpi", MAP_DPI)), transparent=True, bbox_inches=None, pad_inches=0)
    plt.close(fig)

    return {
        "label": "Model active boundary",
        "relpath": clean_rel(out_path, run_root),
        "source": "sfincs_map.nc:msk boundary contour",
        "available": True,
    }

def build_obs_points_overlay(run_root, maps_dir, xg, yg):
    obs_path = find_existing_model_file(run_root, [
        "sfincs.obs",
        "sfincs_obs.xy",
        "obs.xy",
        "obspoints.xy",
    ])

    points = read_xy_points(obs_path) if obs_path else []
    if not points:
        return None

    rgba = make_empty_rgba_like(xg)

    # Magenta-ish points with dark outline block.
    for x, y in points:
        row, col = nearest_grid_index(xg, yg, x, y)
        draw_square_marker(rgba, row, col, 4, [0.05, 0.02, 0.08, 0.90])
        draw_square_marker(rgba, row, col, 2, [1.00, 0.10, 0.80, 1.00])

    out_path = maps_dir / "obs_points_overlay.png"
    save_rgba_array_png(rgba, xg, yg, out_path)

    return {
        "label": "Observation points",
        "relpath": clean_rel(out_path, run_root),
        "source": clean_rel(obs_path, run_root),
        "count": len(points),
        "available": True,
    }


def build_obs_lines_overlay(run_root, maps_dir, xg, yg):
    # V1: try to draw point-pairs from simple numeric line files if present.
    line_path = find_existing_model_file(run_root, [
        "sfincs.crs",
        "sfincs_obs_lines.xy",
        "obs_lines.xy",
        "cross_sections.xy",
    ])

    points = read_xy_points(line_path) if line_path else []
    if len(points) < 2:
        return None

    rgba = make_empty_rgba_like(xg)

    # Simple V1: mark line vertices. We can draw true connecting lines in the next pass.
    for x, y in points:
        row, col = nearest_grid_index(xg, yg, x, y)
        draw_square_marker(rgba, row, col, 3, [0.00, 0.00, 0.00, 0.90])
        draw_square_marker(rgba, row, col, 1, [1.00, 0.85, 0.05, 1.00])

    out_path = maps_dir / "obs_lines_overlay.png"
    save_rgba_array_png(rgba, xg, yg, out_path)

    return {
        "label": "Observation lines / gauges",
        "relpath": clean_rel(out_path, run_root),
        "source": clean_rel(line_path, run_root),
        "count": len(points),
        "available": True,
    }

def _as_finite_float(value):
    try:
        out = float(value)
    except Exception:
        return None

    if not np.isfinite(out):
        return None

    return out


def _read_obs_gauge_metrics(run_root):
    path = run_root / "review" / "obs_gauges" / "obs_gauges_metrics.json"

    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _error_rgb(norm):
    norm = np.clip(norm, 0.0, 1.0).astype("float32")

    green = np.array([0.10, 0.55, 0.24], dtype="float32")
    yellow = np.array([0.98, 0.78, 0.20], dtype="float32")
    red = np.array([0.78, 0.12, 0.12], dtype="float32")

    rgb = np.zeros((*norm.shape, 3), dtype="float32")

    low = norm <= 0.5
    high = ~low

    if np.any(low):
        t = (norm[low] / 0.5)[:, None]
        rgb[low] = green * (1.0 - t) + yellow * t

    if np.any(high):
        t = ((norm[high] - 0.5) / 0.5)[:, None]
        rgb[high] = yellow * (1.0 - t) + red * t

    return rgb

def _nearest_indices(sorted_vals, query_vals):
    idx = np.searchsorted(sorted_vals, query_vals)
    idx = np.clip(idx, 1, len(sorted_vals) - 1)

    left = sorted_vals[idx - 1]
    right = sorted_vals[idx]

    use_left = np.abs(query_vals - left) <= np.abs(query_vals - right)

    out = idx.copy()
    out[use_left] = idx[use_left] - 1

    return out


def _active_mask_to_frame_pixels(active, xg, yg, map_frame, width_px, height_px):
    active = np.asarray(active, dtype=bool)

    if active.ndim != 2 or active.shape != xg.shape or active.shape != yg.shape:
        return np.ones((height_px, width_px), dtype=bool)

    x_line = np.asarray(np.nanmean(xg, axis=0), dtype="float64")
    y_line = np.asarray(np.nanmean(yg, axis=1), dtype="float64")

    good_x = np.isfinite(x_line)
    good_y = np.isfinite(y_line)

    if good_x.sum() < 2 or good_y.sum() < 2:
        return np.ones((height_px, width_px), dtype=bool)

    x_order = np.argsort(x_line)
    y_order = np.argsort(y_line)

    x_sorted = x_line[x_order]
    y_sorted = y_line[y_order]
    active_sorted = active[y_order, :][:, x_order]

    x_pixels = np.linspace(float(map_frame["xmin"]), float(map_frame["xmax"]), width_px)
    y_pixels = np.linspace(float(map_frame["ymax"]), float(map_frame["ymin"]), height_px)

    valid_x = (x_pixels >= x_sorted[0]) & (x_pixels <= x_sorted[-1])
    valid_y = (y_pixels >= y_sorted[0]) & (y_pixels <= y_sorted[-1])

    col_idx = _nearest_indices(x_sorted, np.clip(x_pixels, x_sorted[0], x_sorted[-1]))
    row_idx = _nearest_indices(y_sorted, np.clip(y_pixels, y_sorted[0], y_sorted[-1]))

    mask = active_sorted[row_idx[:, None], col_idx[None, :]]
    mask = mask & valid_y[:, None] & valid_x[None, :]

    return mask


def _collect_error_points(metrics, kind):
    gauges = metrics.get("gauges", []) if isinstance(metrics, dict) else []
    points = []

    for row in gauges:
        row_kind = str(row.get("kind", "")).lower()

        if kind == "flow":
            if row_kind != "line":
                continue

            peak_pct = _as_finite_float(row.get("flow_peak_error_pct"))

            if peak_pct is None:
                peak_err = _as_finite_float(row.get("flow_peak_error_cms"))
                obs_peak = _as_finite_float(row.get("obs_flow_peak_cms"))

                if peak_err is not None and obs_peak is not None and abs(obs_peak) > 1e-12:
                    peak_pct = 100.0 * abs(peak_err) / abs(obs_peak)

            if peak_pct is not None:
                vals = [peak_pct]
            else:
                vals = [
                    _as_finite_float(row.get("flow_mean_error_cms")),
                    _as_finite_float(row.get("flow_peak_error_cms")),
                ]
        elif kind == "waterlevel":
            if row_kind == "line":
                continue

            vals = [
                _as_finite_float(row.get("wl_mean_error_m")),
                _as_finite_float(row.get("wl_peak_error_m")),
                _as_finite_float(row.get("wl_error_m")),
                _as_finite_float(row.get("wl_rmse_m")),
            ]

        else:
            continue

        vals = [abs(v) for v in vals if v is not None]

        if not vals:
            continue

        x = _as_finite_float(row.get("x"))
        y = _as_finite_float(row.get("y"))

        if x is None or y is None:
            x1 = _as_finite_float(row.get("x1"))
            y1 = _as_finite_float(row.get("y1"))
            x2 = _as_finite_float(row.get("x2"))
            y2 = _as_finite_float(row.get("y2"))

            if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                x = (x1 + x2) / 2.0
                y = (y1 + y2) / 2.0

        if x is None or y is None:
            continue

        points.append({
            "x": float(x),
            "y": float(y),
            "score": float(max(vals)),
        })

    return points


def _write_error_surface_png(points, out_path, map_frame, active_pixel_mask):
    if not points:
        return False

    width_px = int(active_pixel_mask.shape[1])
    height_px = int(active_pixel_mask.shape[0])

    xmin = float(map_frame["xmin"])
    xmax = float(map_frame["xmax"])
    ymin = float(map_frame["ymin"])
    ymax = float(map_frame["ymax"])

    xs = np.linspace(xmin, xmax, width_px, dtype="float32")
    ys = np.linspace(ymax, ymin, height_px, dtype="float32")
    xx, yy = np.meshgrid(xs, ys)

    scores = np.asarray([p["score"] for p in points], dtype="float32")
    robust_max = float(np.nanpercentile(scores, 95)) if scores.size else 1.0

    if not np.isfinite(robust_max) or robust_max <= 0:
        robust_max = float(np.nanmax(scores)) if scores.size else 1.0

    if not np.isfinite(robust_max) or robust_max <= 0:
        robust_max = 1.0

    frame_span = max(xmax - xmin, ymax - ymin)
    sigma = max(frame_span * 0.075, 1000.0)

    weighted = np.zeros((height_px, width_px), dtype="float32")
    weights = np.zeros((height_px, width_px), dtype="float32")

    for point in points:
        px = float(point["x"])
        py = float(point["y"])
        value = min(float(point["score"]) / robust_max, 1.0)

        dist2 = (xx - px) ** 2 + (yy - py) ** 2
        w = np.exp(-dist2 / (2.0 * sigma * sigma)).astype("float32")

        weighted += w * value
        weights += w

    norm = weighted / np.maximum(weights, 1e-12)

    finite_weights = weights[weights > 0]
    if finite_weights.size:
        weight_scale = float(np.nanpercentile(finite_weights, 80))
    else:
        weight_scale = 1.0

    if not np.isfinite(weight_scale) or weight_scale <= 0:
        weight_scale = 1.0

    alpha = 0.68 * np.clip(weights / weight_scale, 0.0, 1.0) # flow error map alpha
    alpha = np.where(active_pixel_mask, alpha, 0.0)

    rgb = _error_rgb(norm)

    rgba = np.zeros((height_px, width_px, 4), dtype="float32")
    rgba[..., :3] = rgb
    rgba[..., 3] = alpha.astype("float32")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(out_path, np.clip(rgba, 0.0, 1.0))

    return True


def build_obs_error_surface_overlays(ds, run_root, maps_dir, xg, yg, crop_slices=None, map_frame=None):
    metrics = _read_obs_gauge_metrics(run_root)

    if not metrics or map_frame is None:
        return {}

    context_path = maps_dir / "obs_gauge_context_map.png"

    if context_path.exists():
        try:
            img = plt.imread(context_path)
            height_px = int(img.shape[0])
            width_px = int(img.shape[1])
        except Exception:
            width_px = int(map_frame.get("image", {}).get("width_px") or 1481)
            height_px = int(map_frame.get("image", {}).get("height_px") or 1504)
    else:
        width_px = int(map_frame.get("image", {}).get("width_px") or 1481)
        height_px = int(map_frame.get("image", {}).get("height_px") or 1504)

    active_pixel_mask = np.ones((height_px, width_px), dtype=bool)

    if "msk" in ds.variables:
        msk = np.asarray(ds["msk"].values)

        if msk.ndim == 2:
            msk = apply_crop(msk, crop_slices)
            active = np.isfinite(msk) & (msk > 0)
            active_pixel_mask = _active_mask_to_frame_pixels(active, xg, yg, map_frame, width_px, height_px)

    overlays = {}

    flow_points = _collect_error_points(metrics, "flow")
    flow_path = maps_dir / "obs_flow_error_surface.png"

    if _write_error_surface_png(flow_points, flow_path, map_frame, active_pixel_mask):
        overlays["obs_flow_error_surface"] = {
            "label": "Flow error surface",
            "relpath": clean_rel(flow_path, run_root),
            "source": "obs_gauges_metrics.json line flow errors",
            "available": True,
            "point_count": len(flow_points),
            "color_scale": "green low relative error, red high relative error",
        }

    wl_points = _collect_error_points(metrics, "waterlevel")
    wl_path = maps_dir / "obs_wl_error_surface.png"

    if _write_error_surface_png(wl_points, wl_path, map_frame, active_pixel_mask):
        overlays["obs_wl_error_surface"] = {
            "label": "Water-level error surface",
            "relpath": clean_rel(wl_path, run_root),
            "source": "obs_gauges_metrics.json point water-level errors",
            "available": True,
            "point_count": len(wl_points),
            "color_scale": "green low relative error, red high relative error",
        }

    return overlays

def build_obs_gauge_context_map(ds, run_root, maps_dir, xg, yg, epsg, crop_slices=None, map_frame=None):
    if epsg is None:
        return None

    try:
        import contextily as ctx
    except Exception:
        return None

    if map_frame is None:
        map_frame = build_map_frame(xg, yg, pad_frac=MAP_PAD_FRAC)

    if map_frame is None:
        return None

    if "msk" not in ds.variables:
        return None

    msk = np.asarray(ds["msk"].values)

    if msk.ndim != 2:
        return None

    msk = apply_crop(msk, crop_slices)
    active = np.isfinite(msk) & (msk > 0)

    if not np.any(active):
        return None

    obs_path = find_existing_model_file(run_root, [
        "sfincs.obs",
        "sfincs_obs.xy",
        "obs.xy",
        "obspoints.xy",
    ])

    line_path = find_existing_model_file(run_root, [
        "sfincs.crs",
        "sfincs_obs_lines.xy",
        "obs_lines.xy",
        "cross_sections.xy",
    ])

    point_xy = read_xy_points(obs_path) if obs_path else []
    line_xy = read_xy_or_xyxy_centers(line_path) if line_path else []

    out_path = maps_dir / "obs_gauge_context_map.png"

    fig, ax = make_map_frame_figure(map_frame, transparent=False)

    try:
        ctx.add_basemap(
            ax,
            crs=f"EPSG:{epsg}",
            source=ctx.providers.Esri.WorldImagery,
            zoom="auto",
            attribution=False,
        )
    except Exception:
        plt.close(fig)
        return None

    # Force the axes back to the exact model frame after contextily draws tiles.
    # Everything below is now drawn in the same coordinate system on the same axes.
    ax.set_xlim(float(map_frame["xmin"]), float(map_frame["xmax"]))
    ax.set_ylim(float(map_frame["ymin"]), float(map_frame["ymax"]))
    ax.set_aspect("equal", adjustable="box")
    ax.set_position([0, 0, 1, 1])

    active_float = np.where(active, 1.0, 0.0)

    # High-contrast DEM/model active-area outline.
    ax.contour(
        xg,
        yg,
        active_float,
        levels=[0.5],
        colors=["#000000"],
        linewidths=4.0,
        linestyles="solid",
        alpha=0.85,
        zorder=20,
    )

    ax.contour(
        xg,
        yg,
        active_float,
        levels=[0.5],
        colors=["#ffffff"],
        linewidths=2.2,
        linestyles="solid",
        alpha=0.95,
        zorder=21,
    )

    ax.contour(
        xg,
        yg,
        active_float,
        levels=[0.5],
        colors=["#00e5ff"],
        linewidths=1.2,
        linestyles="solid",
        alpha=0.95,
        zorder=22,
    )

    if point_xy:
        px = [p[0] for p in point_xy]
        py = [p[1] for p in point_xy]

        ax.scatter(
            px,
            py,
            s=36,
            marker="o",
            facecolors="#172033",
            edgecolors="#ffffff",
            linewidths=1.3,
            alpha=0.95,
            zorder=30,
        )

    if line_xy:
        lx = [p[0] for p in line_xy]
        ly = [p[1] for p in line_xy]

        ax.scatter(
            lx,
            ly,
            s=42,
            marker="s",
            facecolors="#b25e09",
            edgecolors="#ffffff",
            linewidths=1.3,
            alpha=0.95,
            zorder=31,
        )

    fig.savefig(
        out_path,
        dpi=int(map_frame.get("dpi", MAP_DPI)),
        bbox_inches=None,
        pad_inches=0,
    )
    plt.close(fig)

    postprocess_satellite_png(
        out_path,
        saturation=0.58,
        brightness=1.00,
        contrast=0.92,
        haze=0.08,
    )

    return {
        "label": "Obs/gauge context map",
        "relpath": clean_rel(out_path, run_root),
        "source": "sfincs_map.nc msk + model obs/crs + contextily:Esri.WorldImagery",
        "available": True,
        "point_count": len(point_xy),
        "line_count": len(line_xy),
    }


def build_satellite_background(run_root, maps_dir, xg, yg, epsg, map_frame=None):
    if epsg is None:
        return None

    try:
        import contextily as ctx
    except Exception:
        return None

    if map_frame is None:
        map_frame = build_map_frame(xg, yg, pad_frac=MAP_PAD_FRAC)

    if map_frame is None:
        return None

    out_path = maps_dir / "satellite_background.png"

    fig, ax = make_map_frame_figure(map_frame, transparent=False)

    try:
        ctx.add_basemap(
            ax,
            crs=f"EPSG:{epsg}",
            source=ctx.providers.Esri.WorldImagery,
            zoom="auto",
            attribution=False,
        )

        ax.set_xlim(float(map_frame["xmin"]), float(map_frame["xmax"]))
        ax.set_ylim(float(map_frame["ymin"]), float(map_frame["ymax"]))
        ax.set_position([0, 0, 1, 1])

    except Exception:
        plt.close(fig)
        return None

    fig.savefig(out_path, dpi=int(map_frame.get("dpi", MAP_DPI)), bbox_inches=None, pad_inches=0)
    plt.close(fig)

    postprocess_satellite_png(out_path, saturation=0.48, brightness=0.98, contrast=0.88, haze=0.12)

    return {
        "label": "Satellite background",
        "relpath": clean_rel(out_path, run_root),
        "source": "contextily:Esri.WorldImagery",
        "available": True,
    }


def build_optional_overlays(ds, run_root, maps_dir, xg, yg, epsg=None, crop_slices=None, map_frame=None):
    overlays = {}

    if map_frame is None:
        map_frame = build_map_frame(xg, yg, pad_frac=MAP_PAD_FRAC)

    satellite = build_satellite_background(run_root, maps_dir, xg, yg, epsg, map_frame=map_frame)
    if satellite:
        overlays["satellite_background"] = satellite

    active = build_model_active_area_overlay(
        ds,
        run_root,
        maps_dir,
        xg,
        yg,
        crop_slices=crop_slices,
        map_frame=map_frame,
    )
    if active:
        overlays["model_active_area"] = active

    obs_points = build_obs_points_overlay(run_root, maps_dir, xg, yg)
    if obs_points:
        overlays["obs_points"] = obs_points

    obs_lines = build_obs_lines_overlay(run_root, maps_dir, xg, yg)
    if obs_lines:
        overlays["obs_lines"] = obs_lines

    obs_context = build_obs_gauge_context_map(
        ds,
        run_root,
        maps_dir,
        xg,
        yg,
        epsg,
        crop_slices=crop_slices,
        map_frame=map_frame,
    )
    if obs_context:
        overlays["obs_gauge_context_map"] = obs_context

    error_surfaces = build_obs_error_surface_overlays(
        ds,
        run_root,
        maps_dir, 
        xg,
        yg,
        crop_slices=crop_slices,
        map_frame=map_frame,
    )

    overlays.update(error_surfaces)

    return overlays



def build_maps(run_root, force=False, pretty=False):
    run_root = Path(run_root).resolve()
    maps_dir = run_root / "review" / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = maps_dir / "layers_manifest.json"
    cache_npz = maps_dir / "map_cache.npz"

    if manifest_path.exists() and not force:
        existing = read_json(manifest_path)
        set_status(
            run_root,
            "ready",
            message="Map cache already exists. Use --force to rebuild.",
            manifest=str(manifest_path),
            layers=existing.get("layers", []),
        )
        return existing

    set_status(run_root, "running", started_at=now_iso(), message="Building Review map cache.")

    map_nc = find_model_map_nc(run_root)
    epsg = get_epsg_from_config(run_root)

    ds = xr.open_dataset(map_nc)
    
    crop_slices = active_crop_slices(ds, pad=20)
    
    layers = []
    cache_arrays = {}
    cache_x = None
    cache_y = None

    try:
        for spec in LAYER_SPECS:
            built = build_layer(ds, run_root, maps_dir, spec, epsg, crop_slices=crop_slices)
            if built is None:
                continue

            layer_meta, arr, xg, yg = built
            layers.append(layer_meta)
            cache_arrays[spec["layer_id"]] = arr

            if cache_x is None:
                cache_x = xg
                cache_y = yg

        if not layers:
            available = sorted(list(ds.data_vars))
            raise RuntimeError(
                "Could not build any map layers. "
                f"Available variables include: {available[:80]}"
            )

        if cache_x is not None and cache_y is not None:
            np.savez_compressed(
                cache_npz,
                x=cache_x,
                y=cache_y,
                epsg=np.array([epsg if epsg is not None else -1]),
                **cache_arrays,
            )
        map_frame = None
        optional_overlays = {}

        if cache_x is not None and cache_y is not None:
            map_frame = build_map_frame(cache_x, cache_y, pad_frac=MAP_PAD_FRAC)
            optional_overlays = build_optional_overlays(
                ds,
                run_root,
                maps_dir,
                cache_x,
                cache_y,
                epsg=epsg,
                crop_slices=crop_slices,
                map_frame=map_frame,
            )

        manifest = {
            "ok": True,
            "kind": "review_map_layers_v1",
            "created_at": now_iso(),
            "run_name": run_root.name,
            "run_root": str(run_root),
            "source_netcdf": clean_rel(map_nc, run_root),
            "cache_npz_relpath": clean_rel(cache_npz, run_root) if cache_npz.exists() else None,
            "epsg": epsg,
            "layers": layers,
            "optional_overlays": optional_overlays,
            "map_frame": map_frame,
        }

        write_json(manifest_path, manifest)

        set_status(
            run_root,
            "ready",
            finished_at=now_iso(),
            message=f"Built {len(layers)} Review map layer(s).",
            manifest=clean_rel(manifest_path, run_root),
            layer_ids=[x["layer_id"] for x in layers],
        )

        if pretty:
            print(json.dumps(manifest, indent=2))

        return manifest

    finally:
        ds.close()


def main():
    parser = argparse.ArgumentParser(description="Build Review toggleable map layers from SFINCS outputs.")
    parser.add_argument("run_root", nargs="?", default=str(DEFAULT_RUN))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()

    try:
        manifest = build_maps(run_root, force=args.force, pretty=args.pretty)
        if not args.pretty:
            print(f"OK: built/reused {len(manifest.get('layers', []))} map layer(s)")
            print(run_root / "review" / "maps" / "layers_manifest.json")
    except Exception as exc:
        set_status(
            run_root,
            "failed",
            failed_at=now_iso(),
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        raise


if __name__ == "__main__":
    main()