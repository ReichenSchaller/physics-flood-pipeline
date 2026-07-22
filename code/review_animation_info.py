#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 18 14:19:37 2026

@author: epsilon
"""

from pathlib import Path
import argparse
import json
import math
import numpy as np
import xarray as xr


def read_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def find_model_map_nc(run_root):
    run_root = Path(run_root)
    for p in [run_root / "model" / "sfincs_map.nc", run_root / "sfincs_map.nc"]:
        if p.exists():
            return p
    raise FileNotFoundError(f"Could not find sfincs_map.nc under {run_root}")


def find_time_dim(da):
    for dim in da.dims:
        low = dim.lower()
        if "time" in low or low in {"t", "nt"}:
            return dim
    return None


def time_to_hours_and_labels(ds, time_dim):
    vals = np.asarray(ds[time_dim].values)

    if np.issubdtype(vals.dtype, np.datetime64):
        base_s = vals[0].astype("datetime64[s]").astype("int64")
        sec = vals.astype("datetime64[s]").astype("int64") - base_s
        hours = sec.astype("float64") / 3600.0
        labels = [np.datetime_as_string(v, unit="h").replace("T", " ") for v in vals]
        return hours, labels, "datetime64"

    numeric = vals.astype("float64")
    units = str(ds[time_dim].attrs.get("units", "")).lower()

    if "hour" in units:
        hours = numeric - numeric[0]
    elif "day" in units:
        hours = (numeric - numeric[0]) * 24.0
    else:
        hours = (numeric - numeric[0]) / 3600.0

    labels = [f"+{h:.1f} hr" for h in hours]
    return hours, labels, f"numeric:{units or 'seconds_fallback'}"


def select_frame_indices(hours, hours_per_frame):
    hpf = float(hours_per_frame)
    if hpf <= 0:
        raise ValueError("hours_per_frame must be > 0")

    hours = np.asarray(hours, dtype="float64")
    targets = np.arange(float(hours[0]), float(hours[-1]) + 0.5 * hpf, hpf)
    idx = np.searchsorted(hours, targets, side="left")
    idx = np.clip(idx, 0, len(hours) - 1)
    idx = np.unique(idx)
    return idx.astype(int)


def list_existing_animations(run_root):
    anim_dir = Path(run_root) / "review" / "animations"
    if not anim_dir.exists():
        return []

    out = []
    for meta_path in sorted(anim_dir.glob("animation_depth_*.json")):
        try:
            meta = read_json(meta_path)
        except Exception:
            continue

        rel = meta.get("output_relpath")
        if not rel:
            continue

        video_path = Path(run_root) / rel
        if not video_path.exists():
            continue

        out.append({
            "metadata_relpath": str(meta_path.resolve().relative_to(Path(run_root).resolve())),
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

    out.sort(key=lambda x: str(x.get("created_at") or ""))
    return out


def build_info(run_root, hours_per_frame, fps):
    run_root = Path(run_root).resolve()
    hpf = float(hours_per_frame)
    fps = float(fps)

    if hpf <= 0:
        raise ValueError("hours_per_frame must be > 0")
    if fps <= 0:
        raise ValueError("fps must be > 0")

    map_nc = find_model_map_nc(run_root)
    status_path = run_root / "review" / "animations" / "animation_status.json"

    ds = xr.open_dataset(map_nc)
    try:
        if "zs" not in ds.variables:
            raise RuntimeError("sfincs_map.nc does not contain zs(time,n,m).")
        if "zb" not in ds.variables:
            raise RuntimeError("sfincs_map.nc does not contain zb(n,m).")

        time_dim = find_time_dim(ds["zs"])
        if time_dim is None:
            raise RuntimeError("Could not identify time dimension on zs.")

        hours, labels, time_kind = time_to_hours_and_labels(ds, time_dim)
        frame_indices = select_frame_indices(hours, hpf)

        diffs = np.diff(hours)
        good_diffs = diffs[np.isfinite(diffs)]

        native_spacing = None
        if good_diffs.size:
            native_spacing = {
                "min": float(np.nanmin(good_diffs)),
                "p50": float(np.nanpercentile(good_diffs, 50)),
                "max": float(np.nanmax(good_diffs)),
                "mean": float(np.nanmean(good_diffs)),
            }

        frame_count = int(len(frame_indices))
        latest = None
        existing = list_existing_animations(run_root)
        if existing:
            latest = existing[-1]

        return {
            "ok": True,
            "kind": "review_animation_info_v1",
            "run": run_root.name,
            "run_root": str(run_root),
            "source_netcdf": str(map_nc.resolve().relative_to(run_root)),
            "status": read_json(status_path),
            "has_status": status_path.exists(),
            "animated_field": "depth(t) = max(zs(t) - zb, 0)",
            "source_time_count": int(ds.sizes[time_dim]),
            "time_dim": time_dim,
            "time_kind": time_kind,
            "first_time_label": labels[0],
            "last_time_label": labels[-1],
            "total_span_hours": float(hours[-1] - hours[0]),
            "native_spacing_hours": native_spacing,
            "hours_per_frame": hpf,
            "fps": fps,
            "frame_count": frame_count,
            "video_seconds": round(frame_count / fps, 3),
            "first_selected_index": int(frame_indices[0]),
            "last_selected_index": int(frame_indices[-1]),
            "first_selected_label": labels[int(frame_indices[0])],
            "last_selected_label": labels[int(frame_indices[-1])],
            "existing_animations": existing,
            "latest_animation": latest,
            "output_dir": "review/animations",
            "notes": [
                "V1 animation uses derived depth from zs(t)-zb.",
                "Rainfall heatmap overlay is a planned V2."
            ],
        }

    finally:
        ds.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    parser.add_argument("--hours-per-frame", type=float, default=6.0)
    parser.add_argument("--fps", type=float, default=10.0)
    args = parser.parse_args()

    info = build_info(args.run_root, args.hours_per_frame, args.fps)
    print(json.dumps(info, indent=2, default=str))


if __name__ == "__main__":
    main()
