"""Recursive environment find-and-replace tool.

Performs batch find-and-replace operations across .md, .yaml, and .yml files
using a configuration file (.far.yml) that defines per-environment value maps.

The tool searches up the directory tree from the working directory to locate a
.far.yml config file. The --src-env and --dst-env arguments select two named
environments from that config; every value belonging to the source environment
is replaced with the corresponding value from the destination environment.

Example .far.yml:

    environments:
      staging:
        DB_HOST: db-staging.internal
        API_URL: https://api-staging.example.com
      production:
        DB_HOST: db.internal
        API_URL: https://api.example.com

Running with --src-env staging --dst-env production on a file containing
"db-staging.internal" would replace it with "db.internal".
"""

import sys
from pathlib import Path
from typing import Dict, Optional

import yaml

_CONFIG_FILENAME = ".far.yml"
_TARGET_EXTENSIONS = {".md", ".yaml", ".yml"}


def _find_config(start: Path) -> Optional[Path]:
    """Walk up the directory tree from *start* looking for .far.yml.

    Returns the first path found, or None if the file is not found before the
    filesystem root is reached.
    """
    current = start.resolve()
    while True:
        candidate = current / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _load_config(config_path: Path) -> dict:
    """Load and return the parsed .far.yml config."""
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _build_replacements(config: dict, src_env: str, dst_env: str) -> Dict[str, str]:
    """Return a mapping of {src_value: dst_value} for the given environment pair.

    Raises SystemExit with a descriptive message if either environment key is
    missing from the config.
    """
    environments: dict = config.get("environments", {})

    if src_env not in environments:
        available = ", ".join(environments.keys()) if environments else "(none)"
        print(
            f"ERROR: source environment '{src_env}' not found in config. "
            f"Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    if dst_env not in environments:
        available = ", ".join(environments.keys()) if environments else "(none)"
        print(
            f"ERROR: destination environment '{dst_env}' not found in config. "
            f"Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    src_vals: dict = environments[src_env]
    dst_vals: dict = environments[dst_env]

    replacements = {}  # type: Dict[str, str]
    for key, src_value in src_vals.items():
        dst_value = dst_vals.get(key)
        if dst_value is None:
            print(
                f"WARNING: key '{key}' present in '{src_env}' but missing from "
                f"'{dst_env}' — skipping.",
                file=sys.stderr,
            )
            continue
        if str(src_value) != str(dst_value):
            replacements[str(src_value)] = str(dst_value)

    return replacements


def _replace_in_file(path: Path, replacements: Dict[str, str], dry_run: bool = False) -> int:
    """Apply *replacements* to the file at *path*.

    Returns the number of substitutions made (0 if the file was unchanged or
    if dry_run is True and changes would have been made).
    """
    original = path.read_text(encoding="utf-8")
    updated = original
    for src, dst in replacements.items():
        updated = updated.replace(src, dst)

    changes = original != updated
    if not changes:
        return 0

    count = sum(original.count(src) for src in replacements if src in original)
    if dry_run:
        print(f"  (dry-run) would update: {path}  [{count} replacement(s)]")
        return count

    path.write_text(updated, encoding="utf-8")
    print(f"  updated: {path}  [{count} replacement(s)]")
    return count


def run_env_replace(
    src_env: str,
    dst_env: str,
    search_path: Optional[Path] = None,
    dry_run: bool = False,
) -> None:
    """Entry point for the env-replace command."""
    if search_path is None:
        search_path = Path.cwd()

    config_path = _find_config(search_path)
    if config_path is None:
        print(
            f"ERROR: could not find '{_CONFIG_FILENAME}' in '{search_path}' or any parent directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Config:  {config_path}")
    print(f"Env:     {src_env} → {dst_env}")
    if dry_run:
        print("(dry-run mode — no files will be modified)\n")

    config = _load_config(config_path)
    replacements = _build_replacements(config, src_env, dst_env)

    if not replacements:
        print("No replacements to apply (source and destination values are identical).")
        return

    print(f"\nReplacements ({len(replacements)}):")
    for src, dst in replacements.items():
        print(f"  {src!r} → {dst!r}")

    # Recursively collect target files relative to the config file's directory
    root = config_path.parent
    target_files = [
        p for p in root.rglob("*") if p.is_file() and p.suffix in _TARGET_EXTENSIONS
    ]

    print(f"\nScanning {len(target_files)} file(s) under {root} …\n")

    total_changes = 0
    for file_path in sorted(target_files):
        total_changes += _replace_in_file(file_path, replacements, dry_run)

    print()
    if dry_run:
        print(f"Dry-run complete. {total_changes} replacement(s) would be applied.")
    else:
        print(f"Done. {total_changes} replacement(s) applied.")
