#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 18 14:11:26 2026

@author: epsilon
"""

from pathlib import Path
import argparse
import datetime as dt
import json
import math
import os
import re
import traceback
import subprocess
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
import numpy as np

import matplotlib
matplotlib.use("Agg")

FFMPEG = Path("/proj/zefflab/projects/Flooding/pipeline/envs/sfincs/bin/ffmpeg")
if FFMPEG.exists():
    matplotlib.rcParams["animation.ffmpeg_path"] = str(FFMPEG)
    os.environ["PATH"] = f"{FFMPEG.parent}:{os.environ.get('PATH', '')}"

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import cm

import xarray as xr


DEFAULT_RUN = Path("/proj/zefflab/projects/Flooding/sfincs_runs/pure_test_override_001")

def resize_image_to_shape(img, rows, cols):
    img = np.asarray(img).astype("float32")

    if img.max() > 1.0:
        img = img / 255.0

    if img.ndim == 2:
        img = np.repeat(img[..., None], 3, axis=2)

    if img.shape[2] >= 4:
        rgb = img[..., :3]
    else:
        rgb = img[..., :3]

    if Image is not None:
        pil = Image.fromarray(np.clip(rgb * 255, 0, 255).astype("uint8"))
        pil = pil.resize((cols, rows), resample=Image.Resampling.LANCZOS)
        return np.asarray(pil).astype("float32") / 255.0

    # Fallback nearest-neighbor resize if Pillow is not available.
    src_rows, src_cols = rgb.shape[:2]
    rr = np.linspace(0, src_rows - 1, rows).round().astype(int)
    cc = np.linspace(0, src_cols - 1, cols).round().astype(int)
    return rgb[rr[:, None], cc[None, :], :]


def pad_rgb_to_even(rgb):
    rows, cols, bands = rgb.shape
    out_rows = rows + (rows % 2)
    out_cols = cols + (cols % 2)

    if out_rows == rows and out_cols == cols:
        return rgb

    out = np.zeros((out_rows, out_cols, bands), dtype=rgb.dtype)
    out[:rows, :cols, :] = rgb

    if out_cols > cols:
        out[:rows, cols:, :] = rgb[:, -1:, :]

    if out_rows > rows:
        out[rows:, :, :] = out[rows - 1:rows, :, :]

    return out


def add_frame_label(rgb, line1, line2=None):
    if Image is None or ImageDraw is None:
        return rgb

    img = Image.fromarray(np.clip(rgb * 255, 0, 255).astype("uint8"))
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    except Exception:
        font_big = None
        font_small = None

    x = 14
    y = 14

    # Simple readable label box.
    box_w = min(img.width - 28, 470)
    box_h = 54 if line2 else 34
    draw.rounded_rectangle(
        [x - 6, y - 6, x + box_w, y + box_h],
        radius=8,
        fill=(255, 255, 255, 210),
        outline=(0, 0, 0, 180),
    )

    draw.text((x, y), str(line1), fill=(0, 0, 0, 255), font=font_big)

    if line2:
        draw.text((x, y + 22), str(line2), fill=(0, 0, 0, 230), font=font_small)

    return np.asarray(img).astype("float32") / 255.0


def compose_depth_frame(base_rgb, depth, mask, vmin, vmax, label1, label2):
    depth_oriented = orient_array_for_web(depth, np.zeros_like(depth), np.flipud(np.arange(depth.shape[0])[:, None] + np.zeros_like(depth)))
    mask_oriented = orient_array_for_web(mask.astype(float), np.zeros_like(mask, dtype=float), np.flipud(np.arange(mask.shape[0])[:, None] + np.zeros_like(mask, dtype=float))) > 0.5

    rgba = depth_to_rgba(
        depth_oriented,
        mask_oriented,
        vmin=vmin,
        vmax=vmax,
        alpha=1.0,
        cmap_name="turbo",
        gamma=0.62,
    )

    flood_rgb = rgba[..., :3]
    alpha = rgba[..., 3:4]

    rgb = base_rgb * (1.0 - alpha) + flood_rgb * alpha
    rgb = add_frame_label(rgb, label1, label2)
    rgb = pad_rgb_to_even(rgb)

    return np.clip(rgb * 255, 0, 255).astype("uint8")

def encode_webm_from_mp4(mp4_path):
    if not FFMPEG.exists():
        raise FileNotFoundError(f"ffmpeg not found at {FFMPEG}")

    mp4_path = Path(mp4_path)
    webm_path = mp4_path.with_suffix(".webm")

    stdout_path = webm_path.with_suffix(".ffmpeg.out")
    stderr_path = webm_path.with_suffix(".ffmpeg.err")

    cmd = [
        str(FFMPEG),
        "-y",
        "-loglevel", "error",
        "-i", str(mp4_path),
        "-an",
        "-c:v", "libvpx-vp9",
        "-b:v", "0",
        "-crf", "32",
        "-pix_fmt", "yuv420p",
        str(webm_path),
    ]

    with stdout_path.open("wb") as fout, stderr_path.open("wb") as ferr:
        proc = subprocess.run(cmd, stdout=fout, stderr=ferr, check=False)

    if proc.returncode != 0:
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
        raise RuntimeError(
            "ffmpeg failed while creating WebM preview.\n"
            f"Command: {' '.join(cmd)}\n"
            f"STDERR:\n{stderr}"
        )

    if not webm_path.exists() or webm_path.stat().st_size == 0:
        raise RuntimeError(f"WebM output is missing or empty: {webm_path}")

    return webm_path

def encode_mp4_from_rgb_frames(out_mp4, frames_iter, width, height, fps):
    if not FFMPEG.exists():
        raise FileNotFoundError(f"ffmpeg not found at {FFMPEG}")

    out_mp4 = Path(out_mp4)
    ffmpeg_stdout = out_mp4.with_suffix(".ffmpeg.out")
    ffmpeg_stderr = out_mp4.with_suffix(".ffmpeg.err")

    cmd = [
        str(FFMPEG),
        "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{int(width)}x{int(height)}",
        "-pix_fmt", "rgb24",
        "-r", str(float(fps)),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-profile:v", "baseline",
        "-level:v", "4.1",
        "-movflags", "+faststart",
        str(out_mp4),
    ]

    frame_count = 0

    with ffmpeg_stdout.open("wb") as fout, ffmpeg_stderr.open("wb") as ferr:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=fout,
            stderr=ferr,
        )

        try:
            for frame in frames_iter:
                frame = np.asarray(frame)

                if frame.ndim != 3 or frame.shape[2] != 3:
                    raise ValueError(f"Expected RGB frame with shape (rows, cols, 3), got {frame.shape}")

                if frame.shape[1] != int(width) or frame.shape[0] != int(height):
                    raise ValueError(
                        "Frame shape does not match ffmpeg size: "
                        f"frame={frame.shape}, expected height={height}, width={width}"
                    )

                if frame.dtype != np.uint8:
                    frame = np.clip(frame, 0, 255).astype("uint8")

                proc.stdin.write(frame.tobytes())
                frame_count += 1

            proc.stdin.close()
            returncode = proc.wait()

        except Exception:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except Exception:
                pass
            proc.kill()
            proc.wait()
            raise

    if returncode != 0:
        stdout = ffmpeg_stdout.read_text(encoding="utf-8", errors="replace") if ffmpeg_stdout.exists() else ""
        stderr = ffmpeg_stderr.read_text(encoding="utf-8", errors="replace") if ffmpeg_stderr.exists() else ""

        raise RuntimeError(
            "ffmpeg failed while encoding animation.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Frames written before failure: {frame_count}\n"
            f"STDOUT:\n{stdout}\n"
            f"STDERR:\n{stderr}"
        )

    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
        raise RuntimeError(
            f"ffmpeg returned success but output MP4 is missing or empty: {out_mp4}"
        )

    return {
        "frames_written": frame_count,
        "ffmpeg_stdout": str(ffmpeg_stdout),
        "ffmpeg_stderr": str(ffmpeg_stderr),
    }        
        
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


def animation_status_path(run_root):
    return run_root / "review" / "animations" / "animation_status.json"


def set_status(run_root, state, **extra):
    payload = {
        "state": state,
        "updated_at": now_iso(),
        **extra,
    }
    write_json(animation_status_path(run_root), payload)


def find_model_map_nc(run_root):
    candidates = [
        run_root / "model" / "sfincs_map.nc",
        run_root / "sfincs_map.nc",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Could not find sfincs_map.nc under {run_root}")


def find_existing_satellite(run_root):
    p = run_root / "review" / "maps" / "satellite_background.png"
    return p if p.exists() else None


def orient_array_for_web(arr, xg, yg):
    out = np.array(arr, copy=True)

    first_row_y = float(np.nanmean(yg[0, :]))
    last_row_y = float(np.nanmean(yg[-1, :]))
    if last_row_y > first_row_y:
        out = np.flipud(out)

    first_col_x = float(np.nanmean(xg[:, 0]))
    last_col_x = float(np.nanmean(xg[:, -1]))
    if last_col_x < first_col_x:
        out = np.fliplr(out)

    return out


def get_xy(ds, shape):
    rows, cols = shape

    x = np.asarray(ds["x"].values, dtype="float64")
    y = np.asarray(ds["y"].values, dtype="float64")

    if x.shape == shape and y.shape == shape:
        return x, y

    if x.ndim == 1 and y.ndim == 1 and len(x) == cols and len(y) == rows:
        return np.meshgrid(x, y)

    raise ValueError(f"Could not get x/y grid matching shape {shape}. x={x.shape}, y={y.shape}")


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


def sanitize_float_for_name(value):
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    text = text.replace(".", "p")
    return text


def next_versioned_output(anim_dir, hours_per_frame, fps, ext=".mp4"):
    hpf_txt = sanitize_float_for_name(hours_per_frame)
    fps_txt = sanitize_float_for_name(fps)

    prefix = f"animation_depth_hpf_{hpf_txt}_fps_{fps_txt}_v"
    existing = sorted(anim_dir.glob(prefix + "*" + ext))

    versions = []
    pat = re.compile(re.escape(prefix) + r"(\d{3})" + re.escape(ext) + r"$")
    for p in existing:
        m = pat.search(p.name)
        if m:
            versions.append(int(m.group(1)))

    version = max(versions) + 1 if versions else 1
    out = anim_dir / f"{prefix}{version:03d}{ext}"
    return out, version


def boost_rgb(rgb, saturation=1.45, brightness=1.15):
    rgb = np.clip(rgb, 0, 1).astype("float32")
    lum = (
        0.2126 * rgb[..., 0:1] +
        0.7152 * rgb[..., 1:2] +
        0.0722 * rgb[..., 2:3]
    )
    out = lum + (rgb - lum) * float(saturation)
    out = out * float(brightness)
    return np.clip(out, 0, 1)


def postprocess_satellite_array(img, saturation=0.48, brightness=0.98, contrast=0.88, haze=0.12):
    img = np.asarray(img).astype("float32")
    if img.max() > 1:
        img = img / 255.0

    if img.ndim != 3 or img.shape[2] < 3:
        return img

    rgb = img[..., :3]
    alpha = img[..., 3:4] if img.shape[2] >= 4 else np.ones((*rgb.shape[:2], 1), dtype="float32")

    lum = (
        0.2126 * rgb[..., 0:1] +
        0.7152 * rgb[..., 1:2] +
        0.0722 * rgb[..., 2:3]
    )

    rgb = lum + (rgb - lum) * float(saturation)
    rgb = (rgb - 0.5) * float(contrast) + 0.5
    rgb = rgb * float(brightness)
    rgb = rgb * (1.0 - float(haze)) + float(haze)

    return np.concatenate([np.clip(rgb, 0, 1), alpha], axis=2)


def depth_to_rgba(depth, mask, vmin, vmax, alpha=1.0, cmap_name="turbo", gamma=0.62):
    scaled = (depth - vmin) / max((vmax - vmin), 1e-12)
    scaled = np.clip(scaled, 0, 1)
    scaled = scaled ** float(gamma)

    cmap = cm.get_cmap(cmap_name)
    rgba = cmap(scaled).astype("float32")
    rgba[..., :3] = boost_rgb(rgba[..., :3], saturation=1.45, brightness=1.15)
    rgba[..., 3] = np.where(np.isfinite(depth) & mask, float(alpha), 0.0)
    return np.clip(rgba, 0, 1)


def sample_depth_limits(ds, zs_name, zb, time_dim, frame_indices, crop_slices, threshold):
    vals_collected = []

    for i in frame_indices:
        zs = np.asarray(ds[zs_name].isel({time_dim: int(i)}).values, dtype="float64")
        zs = apply_crop(zs, crop_slices)
        depth = np.maximum(zs - zb, 0.0)
        mask = np.isfinite(depth) & (depth > threshold)
        vals = depth[mask]

        if vals.size:
            step = max(1, vals.size // 5000)
            vals_collected.append(vals[::step])

    if not vals_collected:
        return 0.0, 1.0, 0.0, 0.0

    vals = np.concatenate(vals_collected)
    vmin = float(np.nanpercentile(vals, 2))
    vmax = float(np.nanpercentile(vals, 98))

    raw_min = float(np.nanmin(vals))
    raw_max = float(np.nanmax(vals))

    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin = raw_min
        vmax = raw_max

    if vmin == vmax:
        vmax = vmin + 1.0

    return vmin, vmax, raw_min, raw_max


def build_animation(run_root, hours_per_frame=3.0, fps=10.0, force=False, pretty=False):
    run_root = Path(run_root).resolve()
    anim_dir = run_root / "review" / "animations"
    anim_dir.mkdir(parents=True, exist_ok=True)

    hpf = float(hours_per_frame)
    fps = float(fps)

    if hpf <= 0:
        raise ValueError("hours_per_frame must be > 0")
    if fps <= 0:
        raise ValueError("fps must be > 0")

    out_mp4, version = next_versioned_output(anim_dir, hpf, fps, ".mp4")
    meta_path = out_mp4.with_suffix(".json")

    set_status(
        run_root,
        "running",
        started_at=now_iso(),
        message="Building Review flood animation.",
        hours_per_frame=hpf,
        fps=fps,
        output_relpath=clean_rel(out_mp4, run_root),
    )

    map_nc = find_model_map_nc(run_root)

    ds = xr.open_dataset(map_nc)
    try:
        if "zs" not in ds.variables:
            raise RuntimeError("sfincs_map.nc does not contain zs(time,n,m), so animation cannot be built.")
        if "zb" not in ds.variables:
            raise RuntimeError("sfincs_map.nc does not contain zb(n,m), so depth animation cannot be derived.")

        zs_name = "zs"
        time_dim = find_time_dim(ds[zs_name])
        if time_dim is None:
            raise RuntimeError("Could not identify a time dimension on zs.")

        hours, labels, time_kind = time_to_hours_and_labels(ds, time_dim)
        frame_indices = select_frame_indices(hours, hpf)

        zb = np.asarray(ds["zb"].values, dtype="float64")
        crop_slices = active_crop_slices(ds, pad=20)
        zb = apply_crop(zb, crop_slices)

        raw_first_zs = np.asarray(ds[zs_name].isel({time_dim: int(frame_indices[0])}).values, dtype="float64")
        xg_full, yg_full = get_xy(ds, raw_first_zs.shape)

        first_zs = apply_crop(raw_first_zs, crop_slices)
        xg = apply_crop(xg_full, crop_slices)
        yg = apply_crop(yg_full, crop_slices)

        if first_zs.shape != zb.shape or xg.shape != zb.shape or yg.shape != zb.shape:
            raise ValueError(
                "Animation crop/grid shape mismatch: "
                f"first_zs={first_zs.shape}, zb={zb.shape}, xg={xg.shape}, yg={yg.shape}"
            )

        threshold = 0.05
        vmin, vmax, raw_min, raw_max = sample_depth_limits(
            ds=ds,
            zs_name=zs_name,
            zb=zb,
            time_dim=time_dim,
            frame_indices=frame_indices,
            crop_slices=crop_slices,
            threshold=threshold,
        )

        xmin = float(np.nanmin(xg))
        xmax = float(np.nanmax(xg))
        ymin = float(np.nanmin(yg))
        ymax = float(np.nanmax(yg))
        extent = (xmin, xmax, ymin, ymax)

        sat_path = find_existing_satellite(run_root)
        satellite = None
        if sat_path:
            try:
                satellite = plt.imread(sat_path)
                satellite = postprocess_satellite_array(satellite)
            except Exception:
                satellite = None

        rows, cols = zb.shape
        out_rows = rows + (rows % 2)
        out_cols = cols + (cols % 2)

        sat_path = find_existing_satellite(run_root)
        if sat_path:
            try:
                satellite = plt.imread(sat_path)
                satellite = postprocess_satellite_array(satellite)
                base_rgb = resize_image_to_shape(satellite, rows, cols)
            except Exception:
                base_rgb = np.ones((rows, cols, 3), dtype="float32") * 0.92
        else:
            base_rgb = np.ones((rows, cols, 3), dtype="float32") * 0.92

        def frame_iter():
            for frame_no, idx_raw in enumerate(frame_indices):
                idx = int(idx_raw)

                zs = np.asarray(ds[zs_name].isel({time_dim: idx}).values, dtype="float64")
                zs = apply_crop(zs, crop_slices)
                depth = np.maximum(zs - zb, 0.0)

                # Orient the frame so video top is north and left is west, matching the Review PNGs.
                depth_web = orient_array_for_web(depth, xg, yg)
                mask_web = orient_array_for_web((np.isfinite(depth) & (depth > threshold)).astype(float), xg, yg) > 0.5

                label = labels[idx] if idx < len(labels) else f"frame {idx}"
                line1 = f"Flood depth — {label}"
                line2 = f"Frame {frame_no + 1}/{len(frame_indices)} | +{hours[idx]:.1f} hr | > {threshold:g} m"

                rgba = depth_to_rgba(
                    depth_web,
                    mask_web,
                    vmin=vmin,
                    vmax=vmax,
                    alpha=1.0,
                    cmap_name="turbo",
                    gamma=0.62,
                )

                base_web = orient_array_for_web(base_rgb, xg, yg)

                flood_rgb = rgba[..., :3]
                alpha_arr = rgba[..., 3:4]

                rgb = base_web * (1.0 - alpha_arr) + flood_rgb * alpha_arr
                rgb = add_frame_label(rgb, line1, line2)
                rgb = pad_rgb_to_even(rgb)

                yield np.clip(rgb * 255, 0, 255).astype("uint8")

        encode_mp4_from_rgb_frames(
            out_mp4=out_mp4,
            frames_iter=frame_iter(),
            width=out_cols,
            height=out_rows,
            fps=fps,
        )
        
        out_webm = encode_webm_from_mp4(out_mp4)
        
        metadata = {
            "ok": True,
            "webm_relpath": str(out_webm.resolve().relative_to(run_root.resolve())),
            "browser_relpath": str(out_webm.resolve().relative_to(run_root.resolve())),
            "webm_size_bytes": int(out_webm.stat().st_size),
            "video_width_px": int(out_cols),
            "video_height_px": int(out_rows),
            "model_rows": int(rows),
            "model_cols": int(cols),
            "video_shape_note": "Video is one pixel per SFINCS model cell, padded to even dimensions for H.264/yuv420p.",
            "kind": "review_animation_v1",
            "created_at": now_iso(),
            "run_name": run_root.name,
            "run_root": str(run_root),
            "source_netcdf": clean_rel(map_nc, run_root),
            "output_relpath": clean_rel(out_mp4, run_root),
            "metadata_relpath": clean_rel(meta_path, run_root),
            "version": version,
            "hours_per_frame": hpf,
            "fps": fps,
            "video_seconds": round(len(frame_indices) / fps, 3),
            "frame_count": int(len(frame_indices)),
            "source_time_count": int(ds.sizes[time_dim]),
            "time_dim": time_dim,
            "time_kind": time_kind,
            "first_frame_index": int(frame_indices[0]),
            "last_frame_index": int(frame_indices[-1]),
            "first_time_label": labels[int(frame_indices[0])],
            "last_time_label": labels[int(frame_indices[-1])],
            "threshold_m": threshold,
            "animated_field": "depth(t) = max(zs(t) - zb, 0)",
            "render_vmin": vmin,
            "render_vmax": vmax,
            "sampled_raw_min": raw_min,
            "sampled_raw_max": raw_max,
            "satellite_relpath": clean_rel(sat_path, run_root) if sat_path else None,
            "notes": [
                "V1 animation uses water depth derived from zs(t)-zb.",
                "Rainfall overlay is intentionally not included yet.",
            ],
        }

        write_json(meta_path, metadata)

        set_status(
            run_root,
            "ready",
            finished_at=now_iso(),
            message=f"Built animation with {len(frame_indices)} frame(s).",
            output_relpath=clean_rel(out_mp4, run_root),
            metadata_relpath=clean_rel(meta_path, run_root),
            frame_count=int(len(frame_indices)),
            video_seconds=round(len(frame_indices) / fps, 3),
            hours_per_frame=hpf,
            fps=fps,
        )

        if pretty:
            print(json.dumps(metadata, indent=2))

        return metadata

    finally:
        ds.close()


def main():
    parser = argparse.ArgumentParser(description="Build Review flood animation from SFINCS zs(t) and zb.")
    parser.add_argument("run_root", nargs="?", default=str(DEFAULT_RUN))
    parser.add_argument("--hours-per-frame", type=float, default=3.0)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()

    try:
        metadata = build_animation(
            run_root=run_root,
            hours_per_frame=args.hours_per_frame,
            fps=args.fps,
            force=args.force,
            pretty=args.pretty,
        )
        if not args.pretty:
            print(f"OK: {metadata['output_relpath']}")
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
