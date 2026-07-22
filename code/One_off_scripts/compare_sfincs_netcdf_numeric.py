#!/usr/bin/env python3
"""
compare_sfincs_netcdf_numeric.py

Chunked / Slurm-safe SFINCS run comparison tool.

Default behavior:
  - Compare sfincs.inp semantically.
  - Compare key input files by existence, size, and byte identity where safe.
  - Compare selected important NetCDF variables using chunked reads.
  - Treat total_runtime as metadata, not flood physics.
  - Support --json for the web launcher.

Usage:
  python compare_sfincs_netcdf_numeric.py OLD_RUN NEW_RUN
  python compare_sfincs_netcdf_numeric.py --json OLD_RUN NEW_RUN
  python compare_sfincs_netcdf_numeric.py --all-vars OLD_RUN NEW_RUN
"""

from __future__ import annotations

import argparse
import filecmp
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from netCDF4 import Dataset


IMPORTANT_INP_KEYS = [
    "tref", "tstart", "tstop",
    "epsg", "crsgeo", "coriolis", "baro", "pavbnd", "inputformat",
    "x0", "y0", "dx", "dy", "mmax", "nmax", "rotation",
    "depfile", "mskfile", "indexfile", "sbgfile", "manningfile",
    "bndfile", "srcfile", "obsfile", "scsfile", "thdfile",
    "bzsfile", "disfile", "netamprfile",
]

BYTE_COMPARE_FILES = [
    "sfincs.inp",
    "sfincs.dep",
    "sfincs.msk",
    "sfincs.ind",
    "sfincs.sbg",
    "sfincs.manning",
    "sfincs.bnd",
    "sfincs.src",
    "sfincs.obs",
    "sfincs.scs",
    "sfincs.thd",
    "sfincs.bzs",
    "sfincs.dis",
    "precip_2d.nc",
    "sfincs.log",
]

OUTPUT_NC_FILES = [
    "sfincs_map.nc",
    "sfincs_his.nc",
]

DEFAULT_COMPARE_VARS = {
    "sfincs_map.nc": [
        "zsmax",
        "zs",
        "zb",
        "qinf",
    ],
    "sfincs_his.nc": [
        "point_zs",
        "point_zb",
        "point_qinf",
        "crosssection_discharge",
    ],
}

METADATA_VARIABLES = {
    "total_runtime",
    "runtime",
    "run_time",
    "walltime",
    "wall_time",
}

RAIN_HINTS = ["rain", "precip", "ampr", "netampr"]


def log(message: str) -> None:
    """Progress messages go to stderr so --json stdout stays clean."""
    print(message, file=sys.stderr, flush=True)


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def resolve_model_dir(run_path: Path) -> Path:
    run_path = run_path.expanduser()
    if (run_path / "sfincs.inp").exists():
        return run_path
    return run_path / "model"


def normalize_value(value: str) -> str:
    parts = value.strip().split()
    out = []

    for part in parts:
        try:
            out.append(f"{float(part):.12g}")
        except ValueError:
            out.append(part)

    return " ".join(out)


def parse_inp(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}

    if not path.exists():
        return out

    for line in path.read_text(errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()

        if not line or "=" not in line:
            continue

        key, value = line.split("=", 1)
        out[key.strip().lower()] = normalize_value(value.strip())

    return out


def compare_inp(old_model: Path, new_model: Path) -> Dict[str, Any]:
    old_path = old_model / "sfincs.inp"
    new_path = new_model / "sfincs.inp"

    old = parse_inp(old_path)
    new = parse_inp(new_path)

    diffs = []
    for key in sorted(set(old) | set(new)):
        if old.get(key) != new.get(key):
            diffs.append({
                "key": key,
                "old": old.get(key),
                "new": new.get(key),
                "important": key in IMPORTANT_INP_KEYS,
            })

    important_rows = []
    for key in IMPORTANT_INP_KEYS:
        important_rows.append({
            "key": key,
            "old": old.get(key),
            "new": new.get(key),
            "same": old.get(key) == new.get(key),
        })

    warnings = []

    for key in ["tref", "tstart", "tstop"]:
        if old.get(key) != new.get(key):
            warnings.append(
                f"Different {key}: OLD={old.get(key)} NEW={new.get(key)}. "
                "Runs may not be apples-to-apples."
            )

    for key in ["dx", "dy", "mmax", "nmax", "epsg", "crsgeo"]:
        if old.get(key) != new.get(key):
            warnings.append(
                f"Different grid/CRS key {key}: OLD={old.get(key)} NEW={new.get(key)}."
            )

    return {
        "old_path": str(old_path),
        "new_path": str(new_path),
        "old_exists": old_path.exists(),
        "new_exists": new_path.exists(),
        "same_semantic": len(diffs) == 0,
        "diff_count": len(diffs),
        "diffs": diffs,
        "important_rows": important_rows,
        "warnings": warnings,
    }


def file_size(path: Path) -> Optional[int]:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None


def compare_byte_files(old_model: Path, new_model: Path) -> List[Dict[str, Any]]:
    rows = []

    for filename in BYTE_COMPARE_FILES:
        old_path = old_model / filename
        new_path = new_model / filename

        old_exists = old_path.exists()
        new_exists = new_path.exists()

        byte_identical = None
        if old_exists and new_exists:
            try:
                byte_identical = filecmp.cmp(old_path, new_path, shallow=False)
            except OSError:
                byte_identical = None

        rows.append({
            "file": filename,
            "old_exists": old_exists,
            "new_exists": new_exists,
            "old_size": file_size(old_path),
            "new_size": file_size(new_path),
            "byte_identical": byte_identical,
        })

    return rows


def get_nc_attr(var: Any, name: str, default: str = "") -> str:
    try:
        value = getattr(var, name)
        return str(value)
    except Exception:
        return default


def units_of(var: Any) -> str:
    return get_nc_attr(var, "units", "") or get_nc_attr(var, "unit", "")


def is_numeric_var(var: Any) -> bool:
    try:
        return np.issubdtype(np.dtype(var.dtype), np.number)
    except Exception:
        return False


def is_meter_like(name: str, units: str) -> bool:
    lname = name.lower()
    u = units.lower().strip()

    return (
        u in ["m", "meter", "meters", "metre", "metres"]
        or any(s in lname for s in ["zs", "zb", "hmax", "water", "level"])
    )


def is_rain_like(name: str, units: str) -> bool:
    lname = name.lower()
    u = units.lower()

    return (
        any(h in lname for h in RAIN_HINTS)
        or "rain" in u
        or "precip" in u
        or "mm" in u
    )


def classify_variable(name: str, units: str) -> str:
    lname = name.lower()

    if lname in METADATA_VARIABLES:
        return "metadata"

    if is_meter_like(name, units) or is_rain_like(name, units):
        return "physical"

    if "discharge" in lname or "qinf" in lname:
        return "physical"

    return "other_numeric"


def summarize_nc(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "dims": {},
            "data_vars": [],
            "variables": [],
            "open_error": None,
        }

    try:
        with Dataset(path, "r") as ds:
            dims = {str(name): int(len(dim)) for name, dim in ds.dimensions.items()}
            variables = []

            for name, var in ds.variables.items():
                shape = tuple(int(x) for x in var.shape)
                units = units_of(var)

                variables.append({
                    "name": str(name),
                    "dims": [str(d) for d in getattr(var, "dimensions", ())],
                    "shape": list(shape),
                    "dtype": str(var.dtype),
                    "units": units,
                    "numeric": is_numeric_var(var),
                    "category": classify_variable(str(name), units) if is_numeric_var(var) else "non_numeric",
                    "rain_like": is_rain_like(str(name), units),
                    "meter_like": is_meter_like(str(name), units),
                })

            return {
                "exists": True,
                "path": str(path),
                "dims": dims,
                "data_vars": sorted([str(k) for k in ds.variables.keys()]),
                "variables": variables,
                "open_error": None,
            }

    except Exception as exc:
        return {
            "exists": True,
            "path": str(path),
            "dims": {},
            "data_vars": [],
            "variables": [],
            "open_error": str(exc),
        }


def choose_variables(ds: Dataset, filename: str, all_vars: bool, explicit_vars: Optional[List[str]]) -> List[str]:
    numeric_names = [
        str(name) for name, var in ds.variables.items()
        if is_numeric_var(var)
    ]

    if explicit_vars:
        return [name for name in explicit_vars if name in numeric_names]

    if all_vars:
        return numeric_names

    desired = DEFAULT_COMPARE_VARS.get(filename, [])
    chosen = [name for name in desired if name in numeric_names]

    if filename == "precip_2d.nc":
        for name in numeric_names:
            if is_rain_like(name, units_of(ds.variables[name])) and name not in chosen:
                chosen.append(name)

    return chosen


class StreamingStats:
    def __init__(self, estimated_total_count: int, sample_limit: int) -> None:
        self.count = 0
        self.sum_abs = 0.0
        self.sum_sq = 0.0
        self.max_abs = 0.0
        self.sample_limit = int(sample_limit)
        self.samples: List[np.ndarray] = []
        self.sample_count = 0
        self.sample_step = max(1, int(math.ceil(max(estimated_total_count, 1) / max(sample_limit, 1))))

    def update(self, old_values: np.ndarray, new_values: np.ndarray) -> None:
        old_array = np.asarray(old_values)
        new_array = np.asarray(new_values)

        if np.ma.isMaskedArray(old_array):
            old_array = old_array.astype(np.float64).filled(np.nan)
        if np.ma.isMaskedArray(new_array):
            new_array = new_array.astype(np.float64).filled(np.nan)

        old_array = old_array.astype(np.float64, copy=False)
        new_array = new_array.astype(np.float64, copy=False)

        finite = np.isfinite(old_array) & np.isfinite(new_array)
        if not np.any(finite):
            return

        diff = old_array[finite] - new_array[finite]
        abs_diff = np.abs(diff)

        self.count += int(abs_diff.size)
        self.sum_abs += float(np.sum(abs_diff, dtype=np.float64))
        self.sum_sq += float(np.sum(diff * diff, dtype=np.float64))

        local_max = float(np.max(abs_diff))
        if local_max > self.max_abs:
            self.max_abs = local_max

        if self.sample_count < self.sample_limit:
            sample = abs_diff.ravel()[::self.sample_step]
            if sample.size > 0:
                room = self.sample_limit - self.sample_count
                sample = sample[:room]
                self.samples.append(sample.astype(np.float64, copy=True))
                self.sample_count += int(sample.size)

    def finalize(self) -> Dict[str, Any]:
        if self.count == 0:
            return {
                "finite_overlap": 0,
                "max_abs": None,
                "mean_abs": None,
                "rmse": None,
                "p95": None,
                "p99": None,
                "percentiles_approx": True,
            }

        if self.samples:
            sample = np.concatenate(self.samples)
            p95 = float(np.percentile(sample, 95))
            p99 = float(np.percentile(sample, 99))
        else:
            p95 = None
            p99 = None

        return {
            "finite_overlap": self.count,
            "max_abs": self.max_abs,
            "mean_abs": self.sum_abs / self.count,
            "rmse": math.sqrt(self.sum_sq / self.count),
            "p95": p95,
            "p99": p99,
            "percentiles_approx": True,
        }


def variable_total_count(shape: Tuple[int, ...]) -> int:
    if not shape:
        return 1
    total = 1
    for n in shape:
        total *= int(n)
    return int(total)


def chunk_slices(shape: Tuple[int, ...], dtype_size: int, chunk_mb: int) -> List[Tuple[Any, ...]]:
    if not shape:
        return [tuple()]

    total_count = variable_total_count(shape)
    total_bytes_for_two_arrays = total_count * max(dtype_size, 1) * 2

    max_bytes = max(1, int(chunk_mb)) * 1024 * 1024

    if total_bytes_for_two_arrays <= max_bytes:
        return [(slice(None),) * len(shape)]

    trailing_count = 1
    for n in shape[1:]:
        trailing_count *= int(n)

    bytes_per_first_index = trailing_count * max(dtype_size, 1) * 2
    n_first_per_chunk = max(1, int(max_bytes // max(bytes_per_first_index, 1)))

    slices = []
    for start in range(0, int(shape[0]), n_first_per_chunk):
        stop = min(int(shape[0]), start + n_first_per_chunk)
        slices.append((slice(start, stop),) + (slice(None),) * (len(shape) - 1))

    return slices


def compare_one_variable(
    old_var: Any,
    new_var: Any,
    name: str,
    filename: str,
    chunk_mb: int,
    sample_limit: int,
) -> Dict[str, Any]:
    old_shape = tuple(int(x) for x in old_var.shape)
    new_shape = tuple(int(x) for x in new_var.shape)
    units = units_of(old_var) or units_of(new_var)

    category = classify_variable(name, units)
    meter_like = is_meter_like(name, units)
    rain_like = is_rain_like(name, units)

    base = {
        "name": name,
        "file": filename,
        "units": units,
        "category": category,
        "shape": list(old_shape),
        "rain_like": rain_like,
        "meter_like": meter_like,
    }

    if old_shape != new_shape:
        base.update({
            "shape_mismatch": True,
            "old_shape": list(old_shape),
            "new_shape": list(new_shape),
        })
        return base

    estimated_total = variable_total_count(old_shape)
    stats = StreamingStats(estimated_total, sample_limit=sample_limit)

    dtype_size = max(np.dtype(old_var.dtype).itemsize, np.dtype(new_var.dtype).itemsize)
    chunks = chunk_slices(old_shape, dtype_size=dtype_size, chunk_mb=chunk_mb)

    log(f"Comparing {filename}:{name} shape={old_shape} chunks={len(chunks)} chunk_mb={chunk_mb}")

    for i, key in enumerate(chunks, start=1):
        if len(chunks) > 1:
            log(f"  chunk {i}/{len(chunks)}")

        old_values = old_var[...] if key == tuple() else old_var[key]
        new_values = new_var[...] if key == tuple() else new_var[key]
        stats.update(old_values, new_values)

    out = dict(base)
    out.update(stats.finalize())

    if out.get("max_abs") is not None and meter_like:
        out["max_mm"] = out["max_abs"] * 1000.0
        out["mean_mm"] = out["mean_abs"] * 1000.0
        out["rmse_mm"] = out["rmse"] * 1000.0
        out["p95_mm"] = None if out["p95"] is None else out["p95"] * 1000.0
        out["p99_mm"] = None if out["p99"] is None else out["p99"] * 1000.0
    else:
        out["max_mm"] = None
        out["mean_mm"] = None
        out["rmse_mm"] = None
        out["p95_mm"] = None
        out["p99_mm"] = None

    return out


def compare_nc_file(
    old_model: Path,
    new_model: Path,
    filename: str,
    all_vars: bool,
    explicit_vars: Optional[List[str]],
    chunk_mb: int,
    sample_limit: int,
) -> Dict[str, Any]:
    old_path = old_model / filename
    new_path = new_model / filename

    result: Dict[str, Any] = {
        "file": filename,
        "old_path": str(old_path),
        "new_path": str(new_path),
        "old_exists": old_path.exists(),
        "new_exists": new_path.exists(),
        "old_summary": summarize_nc(old_path),
        "new_summary": summarize_nc(new_path),
        "variables": [],
        "only_old": [],
        "only_new": [],
        "skipped_numeric": [],
        "open_error": None,
    }

    if not old_path.exists() or not new_path.exists():
        return result

    try:
        with Dataset(old_path, "r") as old_ds, Dataset(new_path, "r") as new_ds:
            old_vars = set(str(k) for k in old_ds.variables.keys())
            new_vars = set(str(k) for k in new_ds.variables.keys())

            result["only_old"] = sorted(old_vars - new_vars)
            result["only_new"] = sorted(new_vars - old_vars)

            old_chosen = set(choose_variables(old_ds, filename, all_vars, explicit_vars))
            new_chosen = set(choose_variables(new_ds, filename, all_vars, explicit_vars))
            chosen = sorted((old_chosen | new_chosen) & old_vars & new_vars)

            numeric_shared = sorted(
                name for name in old_vars & new_vars
                if is_numeric_var(old_ds.variables[name]) and is_numeric_var(new_ds.variables[name])
            )
            result["skipped_numeric"] = [
                name for name in numeric_shared
                if name not in chosen
            ]

            for name in chosen:
                old_var = old_ds.variables[name]
                new_var = new_ds.variables[name]

                if not is_numeric_var(old_var) or not is_numeric_var(new_var):
                    continue

                row = compare_one_variable(
                    old_var=old_var,
                    new_var=new_var,
                    name=name,
                    filename=filename,
                    chunk_mb=chunk_mb,
                    sample_limit=sample_limit,
                )
                result["variables"].append(row)

            result["variables"].sort(
                key=lambda r: (
                    r.get("category") != "physical",
                    -1 if r.get("max_abs") is None else -float(r.get("max_abs", 0.0)),
                    str(r.get("name", "")),
                )
            )

    except Exception as exc:
        result["open_error"] = str(exc)

    return result


def summarize_run(run_path: Path) -> Dict[str, Any]:
    model = resolve_model_dir(run_path)

    key_files = [
        "sfincs.inp",
        "sfincs_map.nc",
        "sfincs_his.nc",
        "precip_2d.nc",
        "sfincs.bzs",
        "sfincs.dis",
        "sfincs.log",
    ]

    files = []
    for filename in key_files:
        path = model / filename
        files.append({
            "file": filename,
            "exists": path.exists(),
            "size": file_size(path),
            "path": str(path),
        })

    return {
        "run_path": str(run_path),
        "model_path": str(model),
        "run_exists": run_path.exists(),
        "model_exists": model.exists(),
        "files": files,
    }


def build_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    warnings = []

    warnings.extend(report["inp"].get("warnings", []))

    if not report["old_run"]["model_exists"]:
        warnings.append("OLD model folder does not exist.")
    if not report["new_run"]["model_exists"]:
        warnings.append("NEW model folder does not exist.")

    physical_nonzero = []
    metadata_nonzero = []
    shape_mismatch = []

    for nc in report["netcdf"].values():
        for row in nc.get("variables", []):
            if row.get("shape_mismatch"):
                shape_mismatch.append({
                    "file": nc["file"],
                    "name": row["name"],
                    "old_shape": row.get("old_shape"),
                    "new_shape": row.get("new_shape"),
                })
                continue

            max_abs = row.get("max_abs")
            if max_abs is None or float(max_abs) == 0.0:
                continue

            item = {
                "file": nc["file"],
                "name": row["name"],
                "category": row["category"],
                "units": row["units"],
                "max_abs": max_abs,
                "max_mm": row.get("max_mm"),
            }

            if row["category"] == "metadata":
                metadata_nonzero.append(item)
            else:
                physical_nonzero.append(item)

    if physical_nonzero:
        warnings.append(f"{len(physical_nonzero)} nonzero physical/other numeric NetCDF differences found.")
    if shape_mismatch:
        warnings.append(f"{len(shape_mismatch)} NetCDF variable shape mismatches found.")

    return {
        "inp_same_semantic": report["inp"]["same_semantic"],
        "inp_diff_count": report["inp"]["diff_count"],
        "physical_nonzero_count": len(physical_nonzero),
        "metadata_nonzero_count": len(metadata_nonzero),
        "shape_mismatch_count": len(shape_mismatch),
        "physical_nonzero_top": physical_nonzero[:20],
        "metadata_nonzero_top": metadata_nonzero[:20],
        "shape_mismatch_top": shape_mismatch[:20],
        "warnings": warnings,
        "clean_physical_match": (
            report["inp"]["same_semantic"]
            and len(physical_nonzero) == 0
            and len(shape_mismatch) == 0
        ),
    }


def compare_runs(
    old_run: Path,
    new_run: Path,
    all_vars: bool,
    explicit_vars: Optional[List[str]],
    chunk_mb: int,
    sample_limit: int,
) -> Dict[str, Any]:
    old_run = old_run.expanduser()
    new_run = new_run.expanduser()

    old_model = resolve_model_dir(old_run)
    new_model = resolve_model_dir(new_run)

    report: Dict[str, Any] = {
        "old_run": summarize_run(old_run),
        "new_run": summarize_run(new_run),
        "old_model": str(old_model),
        "new_model": str(new_model),
        "settings": {
            "all_vars": all_vars,
            "explicit_vars": explicit_vars,
            "chunk_mb": chunk_mb,
            "sample_limit": sample_limit,
            "percentiles": "approximate from bounded sample",
        },
        "inp": compare_inp(old_model, new_model),
        "byte_files": compare_byte_files(old_model, new_model),
        "netcdf": {},
    }

    for filename in OUTPUT_NC_FILES:
        report["netcdf"][filename] = compare_nc_file(
            old_model=old_model,
            new_model=new_model,
            filename=filename,
            all_vars=all_vars,
            explicit_vars=explicit_vars,
            chunk_mb=chunk_mb,
            sample_limit=sample_limit,
        )

    report["summary"] = build_summary(report)
    return json_safe(report)


def fmt_size(size: Optional[int]) -> str:
    if size is None:
        return "missing"

    size_f = float(size)
    for unit in ["B", "K", "M", "G", "T"]:
        if size_f < 1024 or unit == "T":
            if unit == "B":
                return f"{int(size_f)}B"
            return f"{size_f:.1f}{unit}"
        size_f /= 1024

    return str(size)


def render_text(report: Dict[str, Any]) -> str:
    lines = []

    lines.append("")
    lines.append("================ Summary ================")
    s = report["summary"]
    lines.append(f"OLD: {report['old_run']['run_path']}")
    lines.append(f"NEW: {report['new_run']['run_path']}")
    lines.append(f"sfincs.inp semantic match: {s['inp_same_semantic']}")
    lines.append(f"sfincs.inp diff count:     {s['inp_diff_count']}")
    lines.append(f"physical nonzero diffs:    {s['physical_nonzero_count']}")
    lines.append(f"metadata nonzero diffs:    {s['metadata_nonzero_count']}")
    lines.append(f"shape mismatch count:      {s['shape_mismatch_count']}")
    lines.append(f"clean physical match:      {s['clean_physical_match']}")

    if s["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for warning in s["warnings"]:
            lines.append(f"  - {warning}")

    lines.append("")
    lines.append("================ sfincs.inp semantic comparison ================")
    if report["inp"]["same_semantic"]:
        lines.append("No meaningful key/value differences after normalizing spacing and .0 formatting.")
    else:
        for diff in report["inp"]["diffs"]:
            tag = " IMPORTANT" if diff["important"] else ""
            lines.append(f"  {diff['key']}:{tag}")
            lines.append(f"    OLD = {diff['old']}")
            lines.append(f"    NEW = {diff['new']}")

    lines.append("")
    lines.append("================ Important sfincs.inp keys ================")
    lines.append(f"{'key':18s} {'same':5s} {'OLD':28s} {'NEW':28s}")
    lines.append("-" * 86)
    for row in report["inp"]["important_rows"]:
        old = "" if row["old"] is None else str(row["old"])
        new = "" if row["new"] is None else str(row["new"])
        lines.append(f"{row['key']:18s} {str(row['same']):5s} {old[:28]:28s} {new[:28]:28s}")

    lines.append("")
    lines.append("================ Byte-level file comparison ================")
    lines.append(f"{'file':18s} {'byte_same':10s} {'OLD size':10s} {'NEW size':10s}")
    lines.append("-" * 58)
    for row in report["byte_files"]:
        same = "n/a" if row["byte_identical"] is None else str(row["byte_identical"])
        lines.append(f"{row['file']:18s} {same:10s} {fmt_size(row['old_size']):10s} {fmt_size(row['new_size']):10s}")

    for filename, nc in report["netcdf"].items():
        lines.append("")
        lines.append(f"================ {filename} numeric comparison ================")

        if nc["open_error"]:
            lines.append(f"Open error: {nc['open_error']}")
            continue
        if not nc["old_exists"]:
            lines.append(f"OLD missing: {nc['old_path']}")
            continue
        if not nc["new_exists"]:
            lines.append(f"NEW missing: {nc['new_path']}")
            continue

        if nc["only_old"]:
            lines.append(f"Variables only in OLD: {nc['only_old']}")
        if nc["only_new"]:
            lines.append(f"Variables only in NEW: {nc['only_new']}")
        if nc["skipped_numeric"]:
            lines.append(f"Skipped numeric variables by default: {nc['skipped_numeric']}")
            lines.append("Use --all-vars only in a Slurm job if a full scan is needed.")

        lines.append("")
        lines.append(f"{'variable':28s} {'category':14s} {'units':10s} {'max_abs':>12s} {'mean_abs':>12s} {'rmse':>12s} {'p95':>12s} {'p99':>12s}")
        lines.append("-" * 120)

        for row in nc["variables"]:
            if row.get("shape_mismatch"):
                lines.append(f"{row['name']:28s} SHAPE MISMATCH OLD={row.get('old_shape')} NEW={row.get('new_shape')}")
                continue

            if row["max_abs"] is None:
                continue

            lines.append(
                f"{row['name']:28s} "
                f"{row['category']:14s} "
                f"{str(row['units'])[:10]:10s} "
                f"{row['max_abs']:12.6g} "
                f"{row['mean_abs']:12.6g} "
                f"{row['rmse']:12.6g} "
                f"{str(row['p95'])[:12]:>12s} "
                f"{str(row['p99'])[:12]:>12s}"
            )

        meter_rows = [
            row for row in nc["variables"]
            if row.get("max_mm") is not None
        ]
        if meter_rows:
            lines.append("")
            lines.append("Meter-like variables converted to mm:")
            lines.append(f"{'variable':28s} {'max_mm':>12s} {'mean_mm':>12s} {'rmse_mm':>12s} {'p95_mm':>12s} {'p99_mm':>12s}")
            lines.append("-" * 92)
            for row in meter_rows:
                lines.append(
                    f"{row['name']:28s} "
                    f"{row['max_mm']:12.6g} "
                    f"{row['mean_mm']:12.6g} "
                    f"{row['rmse_mm']:12.6g} "
                    f"{str(row['p95_mm'])[:12]:>12s} "
                    f"{str(row['p99_mm'])[:12]:>12s}"
                )

    return "\n".join(lines)


def parse_vars_arg(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two SFINCS run folders with chunked NetCDF reads.")
    parser.add_argument("--json", action="store_true", help="Print JSON for the web launcher.")
    parser.add_argument("--all-vars", action="store_true", help="Compare all numeric NetCDF variables. Use only in Slurm for large outputs.")
    parser.add_argument("--vars", default=None, help="Comma-separated variable names to compare, overriding defaults.")
    parser.add_argument("--chunk-mb", type=int, default=128, help="Approx max MB to read per old+new variable chunk.")
    parser.add_argument("--sample-limit", type=int, default=200000, help="Max sampled diffs used for approximate p95/p99.")
    parser.add_argument("old_run", help="Old/reference run folder.")
    parser.add_argument("new_run", help="New/comparison run folder.")

    args = parser.parse_args()

    report = compare_runs(
        old_run=Path(args.old_run),
        new_run=Path(args.new_run),
        all_vars=bool(args.all_vars),
        explicit_vars=parse_vars_arg(args.vars),
        chunk_mb=int(args.chunk_mb),
        sample_limit=int(args.sample_limit),
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))


if __name__ == "__main__":
    main()