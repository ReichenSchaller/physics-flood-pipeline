#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 28 14:53:57 2026

@author: epsilon
"""

#!/usr/bin/env python3
from pathlib import Path
import sys
import numpy as np
import xarray as xr

def parse_inp(path):
    out = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().lower()
        v = " ".join(v.strip().split())
        out[k] = normalize_value(v)
    return out

def normalize_value(v):
    parts = v.split()
    normed = []
    for p in parts:
        try:
            normed.append(f"{float(p):.12g}")
        except ValueError:
            normed.append(p)
    return " ".join(normed)

def compare_inp(old_model, new_model):
    old = parse_inp(old_model / "sfincs.inp")
    new = parse_inp(new_model / "sfincs.inp")
    keys = sorted(set(old) | set(new))
    diffs = [(k, old.get(k), new.get(k)) for k in keys if old.get(k) != new.get(k)]

    print("\n================ sfincs.inp semantic comparison ================")
    if not diffs:
        print("No meaningful key/value differences after normalizing spacing and .0 formatting.")
    else:
        print(f"{len(diffs)} meaningful key/value differences:")
        for k, a, b in diffs:
            print(f"  {k}:")
            print(f"    OLD = {a}")
            print(f"    NEW = {b}")

def is_numeric(da):
    return np.issubdtype(da.dtype, np.number)

def compare_nc(old_model, new_model, fname):
    old_path = old_model / fname
    new_path = new_model / fname

    print(f"\n================ {fname} numeric comparison ================")

    if not old_path.exists():
        print(f"OLD missing: {old_path}")
        return
    if not new_path.exists():
        print(f"NEW missing: {new_path}")
        return

    ds_old = xr.open_dataset(old_path, decode_times=False)
    ds_new = xr.open_dataset(new_path, decode_times=False)

    names = sorted(set(ds_old.data_vars) & set(ds_new.data_vars))
    only_old = sorted(set(ds_old.data_vars) - set(ds_new.data_vars))
    only_new = sorted(set(ds_new.data_vars) - set(ds_old.data_vars))

    if only_old:
        print("Variables only in OLD:", only_old)
    if only_new:
        print("Variables only in NEW:", only_new)

    rows = []

    for name in names:
        a_da = ds_old[name]
        b_da = ds_new[name]

        if not is_numeric(a_da) or not is_numeric(b_da):
            continue

        if a_da.shape != b_da.shape:
            print(f"{name}: SHAPE DIFFERENT old={a_da.shape} new={b_da.shape}")
            continue

        a = np.asarray(a_da.values)
        b = np.asarray(b_da.values)

        valid = np.isfinite(a) & np.isfinite(b)
        if not np.any(valid):
            print(f"{name}: no finite overlapping values")
            continue

        d = np.abs(a[valid] - b[valid])

        max_abs = float(np.max(d))
        mean_abs = float(np.mean(d))
        rmse = float(np.sqrt(np.mean((a[valid] - b[valid]) ** 2)))
        p95 = float(np.percentile(d, 95))
        p99 = float(np.percentile(d, 99))

        units = (
            a_da.attrs.get("units")
            or a_da.attrs.get("unit")
            or b_da.attrs.get("units")
            or b_da.attrs.get("unit")
            or ""
        )

        rows.append((max_abs, name, units, mean_abs, rmse, p95, p99))

    rows.sort(reverse=True)

    print(f"{'variable':28s} {'units':10s} {'max_abs':>12s} {'mean_abs':>12s} {'rmse':>12s} {'p95':>12s} {'p99':>12s}")
    print("-" * 106)

    for max_abs, name, units, mean_abs, rmse, p95, p99 in rows:
        print(f"{name:28s} {str(units):10s} {max_abs:12.6g} {mean_abs:12.6g} {rmse:12.6g} {p95:12.6g} {p99:12.6g}")

    print("\nVariables with meter-like units converted to mm:")
    print(f"{'variable':28s} {'max_mm':>12s} {'mean_mm':>12s} {'rmse_mm':>12s} {'p95_mm':>12s} {'p99_mm':>12s}")
    print("-" * 92)

    for max_abs, name, units, mean_abs, rmse, p95, p99 in rows:
        u = str(units).lower().strip()
        likely_water = any(s in name.lower() for s in ["zs", "hmax", "h", "water", "level"])
        meter_units = u in ["m", "meter", "meters", "metre", "metres"]
        if meter_units or likely_water:
            print(f"{name:28s} {max_abs*1000:12.6g} {mean_abs*1000:12.6g} {rmse*1000:12.6g} {p95*1000:12.6g} {p99*1000:12.6g}")

def main():
    if len(sys.argv) != 3:
        print("Usage: compare_sfincs_netcdf_numeric.py OLD_RUN NEW_RUN")
        sys.exit(2)

    old_run = Path(sys.argv[1])
    new_run = Path(sys.argv[2])
    old_model = old_run / "model"
    new_model = new_run / "model"

    print(f"OLD={old_run}")
    print(f"NEW={new_run}")

    compare_inp(old_model, new_model)
    compare_nc(old_model, new_model, "sfincs_map.nc")
    compare_nc(old_model, new_model, "sfincs_his.nc")

if __name__ == "__main__":
    main()