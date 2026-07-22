#!/usr/bin/env python3
"""
Author: Reichen Schaller
Command-line entry point for the config-driven SFINCS pipeline runner.

The future HTML launcher should create/edit config JSON files and call this
runner. Batch tools can also call this runner directly on many config files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from config_schema import VALID_RUNNER_MODES, default_config
from runner_core import (
    apply_cli_overrides,
    apply_defaults,
    load_config_json,
    prepare_run_folders,
    print_config_summary,
    print_runner_complete,
    resolve_runtime_paths,
    set_pipeline_mode_from_runner_mode,
    validate_config,
    write_frozen_run_config,
)
from slurm_tools import submit_slurm_chain, write_job_ids, write_slurm_scripts


def parse_set_value(raw: str) -> Any:
    """Parse --set values.

    Examples:
      --set run_name=my_run
      --set use_wind=true
      --set sfincs_cpus_per_task=8
      --set native_static_sfincs_input_dirs='["/path/a"]'
    """
    text = raw.strip()

    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None

    try:
        return json.loads(text)
    except Exception:
        return text

def parse_overrides(items: list[str] | None) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"--set entries must look like key=value, got: {item!r}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"--set key is blank in: {item!r}")
        overrides[key] = parse_set_value(raw_value)
    return overrides


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the SFINCS pipeline backend from a saved JSON config.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to user config JSON.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=sorted(VALID_RUNNER_MODES),
        help="Runner action: preflight, build_scripts, or submit.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override one config value after loading JSON. May be repeated.",
    )
    return parser


def run_from_args(args: argparse.Namespace) -> int:
    runner_file = Path(__file__).resolve()
    code_dir = runner_file.parent
    pipeline_root = code_dir.parent

    config_path = Path(args.config).expanduser()
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()

    print("SFINCS pipeline runner")
    print(f"Runner file:   {runner_file}")
    print(f"Pipeline root: {pipeline_root}")
    print(f"Config path:   {config_path}")
    print(f"Mode:          {args.mode}")

    cfg = load_config_json(config_path)
    cfg = apply_defaults(cfg, default_config(pipeline_root))
    cfg = apply_cli_overrides(cfg, parse_overrides(args.set))
    cfg = resolve_runtime_paths(cfg, pipeline_root)
    cfg = set_pipeline_mode_from_runner_mode(cfg, args.mode)

    if bool(cfg.get("print_config_summary", True)):
        print_config_summary(cfg, args.mode)

    if bool(cfg.get("validate_paths_before_submit", True)):
        validate_config(cfg, args.mode)

    if args.mode == "preflight":
        print_runner_complete(cfg, args.mode, job_ids=None)
        return 0

    prepare_run_folders(cfg)
    write_frozen_run_config(cfg, runner_file)
    write_slurm_scripts(cfg)

    if args.mode == "build_scripts":
        print_runner_complete(cfg, args.mode, job_ids=None)
        return 0

    job_ids = submit_slurm_chain(cfg)
    write_job_ids(cfg, job_ids)
    print_runner_complete(cfg, args.mode, job_ids=job_ids)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run_from_args(args)
    except KeyboardInterrupt:
        print("\nRunner interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print("\nRUNNER FAILED", file=sys.stderr)
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())