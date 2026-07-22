#!/usr/bin/env python3
"""
Backup SFINCS code files to NAS/home storage.

Purpose:
- Make a timestamped snapshot of lightweight code files.
- Include:
    /proj/zefflab/projects/Flooding/pipeline/code
    /proj/zefflab/projects/Flooding/pipeline/web_launcher
    /proj/zefflab/projects/Flooding/Validation/Code
- Include web_launcher/static JS helpers automatically.
- Exclude backup/broken/recovery/cache/env junk.
- Check NAS/home storage before writing.
- Write a manifest with hashes and file sizes.

This script is intentionally Python-only to avoid fragile bash line continuation issues.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------
# User/project paths
# ---------------------------------------------------------------------

FLOODING_ROOT = Path("/proj/zefflab/projects/Flooding")
PIPELINE_ROOT = FLOODING_ROOT / "pipeline"

SOURCE_ROOTS = [
    PIPELINE_ROOT / "code",
    PIPELINE_ROOT / "web_launcher",
    FLOODING_ROOT / "Validation" / "Code",
]

# On Longleaf, $HOME is on NAS. Keep the backups there.
BACKUP_ROOT = Path.home() / "sfincs_code_backups"

# ---------------------------------------------------------------------
# Safety limits
# ---------------------------------------------------------------------

# Fail if the selected code snapshot is unexpectedly huge.
# Normal should be tiny: MBs to maybe low hundreds of MB.
MAX_SINGLE_SNAPSHOT_BYTES = 2 * 1024**3  # 2 GiB

# Fail if NAS/home free space after writing would drop below this.
MIN_FREE_BYTES_AFTER_BACKUP = 5 * 1024**3  # 5 GiB

# Warn if all code backups exceed this. Does not auto-delete.
WARN_BACKUP_ROOT_BYTES = 10 * 1024**3  # 10 GiB

# Longleaf home quota guard.
# df reports the whole shared NAS filesystem, not the user's quota.
HOME_SOFT_QUOTA_BYTES = 50 * 1024**3  # 50 GiB soft quota
HOME_HARD_QUOTA_BYTES = 75 * 1024**3  # 75 GiB hard quota

# Stop before getting too close to quota.
MAX_HOME_USAGE_AFTER_BACKUP_BYTES = 45 * 1024**3  # conservative soft-quota guard

# ---------------------------------------------------------------------
# Include/exclude rules
# ---------------------------------------------------------------------

INCLUDE_SUFFIXES = {
    ".py",
    ".html",
    ".js",
    ".css",
    ".json",
    ".md",
    ".txt",
    ".sh",
    ".sl",
    ".sbatch",
    ".r",
    ".R",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
}

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".ipynb_checkpoints",
    ".git",
    ".vscode",
    ".spyproject",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "env",
    "envs",
    "venv",
    ".venv",
}

# Any path component containing one of these tokens is skipped.
# This avoids copying app.py.BROKEN_..., .bak files, recovery reports, etc.
EXCLUDE_NAME_TOKENS = {
    ".bak",
    "backup",
    "broken",
    "recovered",
    "recovery",
    "accidental_overwrite",
    "emergency_rescue",
    "audit_report",
    "terminal_output",
}


def bytes_to_human(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(n)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{n} B"


def run_text_command(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=60,
        )
        return proc.stdout.strip()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def should_skip_path(path: Path) -> tuple[bool, str]:
    parts_lower = [part.lower() for part in path.parts]
    name_lower = path.name.lower()

    for part in parts_lower:
        if part in {x.lower() for x in EXCLUDE_DIR_NAMES}:
            return True, f"excluded directory component: {part}"

    for token in EXCLUDE_NAME_TOKENS:
        if token.lower() in name_lower:
            return True, f"excluded name token: {token}"

    if path.suffix not in INCLUDE_SUFFIXES:
        return True, f"suffix not included: {path.suffix or '<none>'}"

    return False, ""


def source_label_for_path(path: Path) -> str:
    """
    Return a stable top-level backup label for each source tree.
    """
    if path.is_relative_to(PIPELINE_ROOT / "code"):
        return "pipeline/code"

    if path.is_relative_to(PIPELINE_ROOT / "web_launcher"):
        return "pipeline/web_launcher"

    validation_code = FLOODING_ROOT / "Validation" / "Code"
    if path.is_relative_to(validation_code):
        return "Validation/Code"

    raise ValueError(f"Path is outside known source roots: {path}")


def backup_relative_path(path: Path) -> Path:
    label = source_label_for_path(path)

    if label == "pipeline/code":
        return Path(label) / path.relative_to(PIPELINE_ROOT / "code")

    if label == "pipeline/web_launcher":
        return Path(label) / path.relative_to(PIPELINE_ROOT / "web_launcher")

    if label == "Validation/Code":
        return Path(label) / path.relative_to(FLOODING_ROOT / "Validation" / "Code")

    raise ValueError(f"Unknown source label: {label}")


def collect_files() -> tuple[list[Path], list[dict]]:
    selected: list[Path] = []
    skipped: list[dict] = []

    for root in SOURCE_ROOTS:
        if not root.exists():
            skipped.append({
                "path": str(root),
                "reason": "source root missing",
            })
            continue

        for dirpath, dirnames, filenames in os.walk(root):
            dirpath_p = Path(dirpath)

            # Prune excluded directories in-place.
            keep_dirs = []
            for dirname in dirnames:
                d = dirpath_p / dirname
                skip, reason = should_skip_path(d)
                if skip and dirname.lower() in {x.lower() for x in EXCLUDE_DIR_NAMES}:
                    skipped.append({"path": str(d), "reason": reason})
                    continue
                keep_dirs.append(dirname)
            dirnames[:] = keep_dirs

            for filename in filenames:
                path = dirpath_p / filename
                skip, reason = should_skip_path(path)

                if skip:
                    skipped.append({"path": str(path), "reason": reason})
                    continue

                if not path.is_file():
                    skipped.append({"path": str(path), "reason": "not a regular file"})
                    continue

                selected.append(path)

    selected = sorted(set(selected), key=lambda p: str(p))
    return selected, skipped

def du_bytes(path: Path) -> int:
    """
    Return apparent disk usage in bytes using du.

    This is better than df for quota-ish home checks because df reports the
    whole shared /nas/longleaf filesystem, not the user's personal quota.
    """
    proc = subprocess.run(
        ["du", "-sb", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"du failed for {path}")

    first = proc.stdout.strip().split()[0]
    return int(first)

def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0

    total = 0

    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            pass

    return total


def update_latest_pointer(snapshot_dir: Path) -> None:
    latest = BACKUP_ROOT / "latest"

    try:
        if latest.is_symlink() or latest.exists():
            if latest.is_dir() and not latest.is_symlink():
                # Avoid deleting a real directory named latest.
                marker = BACKUP_ROOT / f"latest_NOT_UPDATED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                marker.write_text(
                    f"Could not update latest symlink because {latest} is a real directory.\n"
                    f"Newest snapshot: {snapshot_dir}\n",
                    encoding="utf-8",
                )
                return
            latest.unlink()

        latest.symlink_to(snapshot_dir, target_is_directory=True)

    except Exception as exc:
        marker = BACKUP_ROOT / f"latest_SYMLINK_FAILED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        marker.write_text(
            f"Could not update latest symlink: {type(exc).__name__}: {exc}\n"
            f"Newest snapshot: {snapshot_dir}\n",
            encoding="utf-8",
        )


def main() -> int:
    start = time.time()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = BACKUP_ROOT / f"sfincs_code_snapshot_{stamp}"

    print("=" * 90)
    print("SFINCS CODE BACKUP TO NAS")
    print("=" * 90)
    print(f"Time:        {datetime.now().isoformat(timespec='seconds')}")
    print(f"Backup root: {BACKUP_ROOT}")
    print(f"Snapshot:    {snapshot_dir}")
    print("")

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    print("NAS/home storage check:")
    print(run_text_command(["df", "-h", str(BACKUP_ROOT)]))
    print("")

    selected, skipped = collect_files()
    total_bytes = sum(p.stat().st_size for p in selected)
    existing_backup_bytes = directory_size_bytes(BACKUP_ROOT)

    # df/shutil.disk_usage reports the whole shared NAS filesystem.
    # Keep it for context, but do not use it as the main safety guard.
    usage = shutil.disk_usage(BACKUP_ROOT)

    home_usage_before_bytes = du_bytes(Path.home())
    estimated_home_usage_after_bytes = home_usage_before_bytes + total_bytes

    print("Selection summary:")
    print(f"  selected files: {len(selected)}")
    print(f"  selected bytes: {bytes_to_human(total_bytes)}")
    print(f"  skipped entries: {len(skipped)}")
    print(f"  existing backup root size: {bytes_to_human(existing_backup_bytes)}")
    print(f"  HOME usage before backup by du -sb: {bytes_to_human(home_usage_before_bytes)}")
    print(f"  Estimated HOME usage after backup:  {bytes_to_human(estimated_home_usage_after_bytes)}")
    print(f"  Conservative stop threshold:        {bytes_to_human(MAX_HOME_USAGE_AFTER_BACKUP_BYTES)}")
    print(f"  Soft quota reference:               {bytes_to_human(HOME_SOFT_QUOTA_BYTES)}")
    print(f"  Hard quota reference:               {bytes_to_human(HOME_HARD_QUOTA_BYTES)}")
    print(f"  Shared filesystem free by df:        {bytes_to_human(usage.free)}")
    print("  Note: df free space is shared NAS capacity, not your personal quota.")
    print("")

    if total_bytes > MAX_SINGLE_SNAPSHOT_BYTES:
        print("FAIL: selected code snapshot is unexpectedly large.")
        print(f"Selected: {bytes_to_human(total_bytes)}")
        print(f"Limit:    {bytes_to_human(MAX_SINGLE_SNAPSHOT_BYTES)}")
        return 2

    if estimated_home_usage_after_bytes > MAX_HOME_USAGE_AFTER_BACKUP_BYTES:
        print("FAIL: estimated home usage after backup would exceed the conservative quota guard.")
        print(f"HOME usage before:      {bytes_to_human(home_usage_before_bytes)}")
        print(f"Snapshot size:          {bytes_to_human(total_bytes)}")
        print(f"Estimated after:        {bytes_to_human(estimated_home_usage_after_bytes)}")
        print(f"Stop threshold:         {bytes_to_human(MAX_HOME_USAGE_AFTER_BACKUP_BYTES)}")
        print(f"Soft quota reference:   {bytes_to_human(HOME_SOFT_QUOTA_BYTES)}")
        print(f"Hard quota reference:   {bytes_to_human(HOME_HARD_QUOTA_BYTES)}")
        print("No backup was written.")
        return 3

    if existing_backup_bytes > WARN_BACKUP_ROOT_BYTES:
        print("WARNING: backup root is getting large.")
        print(f"Current backup root size: {bytes_to_human(existing_backup_bytes)}")
        print(f"Warning threshold:        {bytes_to_human(WARN_BACKUP_ROOT_BYTES)}")
        print("No files were deleted automatically.")
        print("")

    snapshot_dir.mkdir(parents=False, exist_ok=False)

    manifest_files = []
    copied_bytes = 0

    for src in selected:
        rel = backup_relative_path(src)
        dst = snapshot_dir / rel

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        size = dst.stat().st_size
        copied_bytes += size

        manifest_files.append({
            "source": str(src),
            "backup_relative_path": str(rel),
            "size_bytes": size,
            "sha256": sha256_file(dst),
        })

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "hostname": run_text_command(["hostname"]),
        "user": os.environ.get("USER", ""),
        "backup_root": str(BACKUP_ROOT),
        "snapshot_dir": str(snapshot_dir),
        "source_roots": [str(p) for p in SOURCE_ROOTS],
        "include_suffixes": sorted(INCLUDE_SUFFIXES),
        "exclude_dir_names": sorted(EXCLUDE_DIR_NAMES),
        "exclude_name_tokens": sorted(EXCLUDE_NAME_TOKENS),
        "selected_file_count": len(selected),
        "copied_bytes": copied_bytes,
        "copied_human": bytes_to_human(copied_bytes),
        "existing_backup_root_bytes_before": existing_backup_bytes,
        "existing_backup_root_human_before": bytes_to_human(existing_backup_bytes),
        "disk_usage_before": {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "total_human": bytes_to_human(usage.total),
            "used_human": bytes_to_human(usage.used),
            "free_human": bytes_to_human(usage.free),
        },
        "df_human": run_text_command(["df", "-h", str(BACKUP_ROOT)]),
        "du_backup_root_human_after": run_text_command(["du", "-sh", str(BACKUP_ROOT)]),
        "files": manifest_files,
        "skipped_count": len(skipped),
        "skipped_sample": skipped[:500],
        "elapsed_seconds": round(time.time() - start, 3),
        "home_usage_before_bytes": home_usage_before_bytes,
        "home_usage_before_human": bytes_to_human(home_usage_before_bytes),
        "estimated_home_usage_after_bytes": estimated_home_usage_after_bytes,
        "estimated_home_usage_after_human": bytes_to_human(estimated_home_usage_after_bytes),
        "home_soft_quota_reference_bytes": HOME_SOFT_QUOTA_BYTES,
        "home_hard_quota_reference_bytes": HOME_HARD_QUOTA_BYTES,
        "max_home_usage_after_backup_bytes": MAX_HOME_USAGE_AFTER_BACKUP_BYTES,
    }

    manifest_path = snapshot_dir / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary_path = snapshot_dir / "SUMMARY.txt"
    summary_path.write_text(
        "\n".join([
            "SFINCS code backup snapshot",
            f"created_at: {manifest['created_at']}",
            f"snapshot_dir: {snapshot_dir}",
            f"selected_file_count: {len(selected)}",
            f"copied: {bytes_to_human(copied_bytes)}",
            "",
            "Source roots:",
            *[f"  - {p}" for p in SOURCE_ROOTS],
            "",
            "NAS/home df:",
            manifest["df_human"],
            "",
            "Backup root du after:",
            manifest["du_backup_root_human_after"],
            "",
        ]) + "\n",
        encoding="utf-8",
    )

    update_latest_pointer(snapshot_dir)

    print("Backup complete.")
    print(f"  snapshot: {snapshot_dir}")
    print(f"  manifest: {manifest_path}")
    print(f"  summary:  {summary_path}")
    print(f"  copied files: {len(selected)}")
    print(f"  copied bytes: {bytes_to_human(copied_bytes)}")
    print("")
    print("Backup root size after:")
    print(run_text_command(["du", "-sh", str(BACKUP_ROOT)]))
    print("")
    print("Latest pointer:")
    print(run_text_command(["ls", "-l", str(BACKUP_ROOT / "latest")]))
    print("")
    print("FINAL: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())