#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 11:12:40 2026

@author: epsilon
"""

# %%
from pathlib import Path
import subprocess
import pandas as pd


# =============================================================================
# USER SETTINGS
# =============================================================================

USER_NAME = "epsilon"

# Include both running and pending jobs.
JOB_STATES = "R,PD"

# Only show pipeline jobs with these prefixes.
PIPELINE_PREFIXES = ("pre_", "prep_", "sf_", "post_")

SHOW_NON_PIPELINE_JOBS = False


# =============================================================================
# Helpers
# =============================================================================

def run_squeue():
    cmd = [
        "squeue",
        "-u", USER_NAME,
        "-t", JOB_STATES,
        "-h",
        "-o", "%i|%j|%T|%M|%l|%C|%m|%R",
    ]

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "squeue failed:\n"
            + result.stderr
        )

    rows = []

    for line in result.stdout.splitlines():
        parts = line.split("|")

        if len(parts) < 8:
            continue

        job_id, job_name, state, time_used, time_limit, cpus, mem, reason = parts[:8]

        stage = "other"
        run_name = job_name

        if job_name.startswith("sf_"):
            stage = "sfincs"
            run_name = job_name.removeprefix("sf_")
        elif job_name.startswith("post_"):
            stage = "postprocess"
            run_name = job_name.removeprefix("post_")
        elif job_name.startswith("pre_"):
            stage = "preprocess"
            run_name = job_name.removeprefix("pre_")
        elif job_name.startswith("prep_"):
            stage = "preprocess"
            run_name = job_name.removeprefix("prep_")

        if stage == "other" and not SHOW_NON_PIPELINE_JOBS:
            continue

        try:
            cpus_int = int(cpus)
        except Exception:
            cpus_int = 0

        rows.append({
            "job_id": job_id,
            "stage": stage,
            "state": state,
            "cpus": cpus_int,
            "time_used": time_used,
            "time_limit": time_limit,
            "run_name": run_name,
            "job_name": job_name,
            "reason": reason,
        })

    return pd.DataFrame(rows)


# =============================================================================
# Main
# =============================================================================

df = run_squeue()

if df.empty:
    print(f"No matching active/pending pipeline jobs found for {USER_NAME}.")
else:
    df = df.sort_values(
        by=["state", "stage", "cpus", "run_name"],
        ascending=[True, True, False, True],
    )

    print("\n=== Current active/pending pipeline jobs ===")
    print(df[[
        "job_id",
        "stage",
        "state",
        "cpus",
        "time_used",
        "time_limit",
        "run_name",
        "reason",
    ]].to_string(index=False))

    running_df = df[df["state"] == "RUNNING"].copy()
    pending_df = df[df["state"] == "PENDING"].copy()

    print("\n=== Running CPU total ===")
    print(f"TOTAL_RUNNING_CPUS = {running_df['cpus'].sum()}")

    print("\n=== Running jobs by stage ===")
    if running_df.empty:
        print("None")
    else:
        print(
            running_df.groupby("stage")["cpus"]
            .agg(["count", "sum"])
            .rename(columns={"count": "job_count", "sum": "running_cpus"})
            .to_string()
        )

    print("\n=== Pending jobs by reason ===")
    if pending_df.empty:
        print("None")
    else:
        print(
            pending_df.groupby("reason")["cpus"]
            .agg(["count", "sum"])
            .rename(columns={"count": "job_count", "sum": "pending_cpus"})
            .sort_values("pending_cpus", ascending=False)
            .to_string()
        )

    print("\n=== SFINCS jobs only ===")
    sfincs_df = df[df["stage"] == "sfincs"].copy()

    if sfincs_df.empty:
        print("None")
    else:
        print(sfincs_df[[
            "job_id",
            "state",
            "cpus",
            "time_used",
            "time_limit",
            "run_name",
            "reason",
        ]].to_string(index=False))