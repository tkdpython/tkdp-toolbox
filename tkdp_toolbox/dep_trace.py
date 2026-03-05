"""Trace which top-level dependency in a requirements.txt pulls in a specific package.

Useful for identifying which requirement (or transitive dependency chain) is responsible
for installing a package with a known vulnerability (e.g. a package flagged by a CVE).

Uses the PyPI JSON API to resolve dependency trees without needing to install packages.
Supports mixed environments where some packages are on an internal Nexus PyPI proxy and
others are only on public PyPI. When --pypi-url is provided, each package is looked up
on the internal registry first, falling back to public PyPI if not found there.

Packages that exist only on the internal registry and have no PyPI-compatible metadata
(e.g. custom internal packages) cannot be resolved and will be flagged as unresolvable.

Example usage:
    tkdp-toolbox dep-trace --requirements requirements.txt --package ecdsa
    tkdp-toolbox dep-trace --requirements requirements.txt --package ecdsa --pypi-url https://repo.bcr.io/repository/pypi-public/pypi
"""

import re
import sys
from pathlib import Path
from typing import Optional

import requests

PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"
PYPI_LATEST_URL = "https://pypi.org/pypi/{name}/json"


def _parse_requirements(path: Path) -> list:
    """Parse a requirements.txt and return list of (package_name, version) tuples.

    Only pinned versions (==) are used for exact lookups. Unpinned packages fall
    back to the latest version on PyPI.
    """
    packages = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            # Skip blank lines, comments and pip options (e.g. -r, --index-url)
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Pinned version  e.g.  requests==2.31.0
            match = re.match(r"^([A-Za-z0-9_\-\.]+)\s*==\s*([^\s;,]+)", line)
            if match:
                packages.append((match.group(1).lower().replace("-", "_"), match.group(2)))
                continue
            # Any other specifier or bare name - just grab the name
            match = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
            if match:
                packages.append((match.group(1).lower().replace("-", "_"), None))
    return packages


def _fetch_from_url(url: str) -> Optional[list]:
    """Fetch requires_dist from a PyPI JSON API URL. Returns dep list or None on failure."""
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        requires_dist = resp.json().get("info", {}).get("requires_dist") or []
        deps = []
        for dep in requires_dist:
            dep_clean = re.split(r";", dep)[0].strip()
            dep_name = re.match(r"^([A-Za-z0-9_\-\.]+)", dep_clean)
            if dep_name:
                deps.append(dep_name.group(1).lower().replace("-", "_"))
        return deps
    except Exception:
        return None


def _get_dependencies(name: str, version: Optional[str], pypi_base: Optional[str] = None) -> tuple:
    """Fetch the list of dependency names for a package.

    Tries the internal Nexus PyPI proxy first (if --pypi-url provided), then falls
    back to public PyPI. Returns (deps, source) where source is 'nexus', 'pypi',
    or None if the package could not be resolved from either.
    """
    if pypi_base:
        base = pypi_base.rstrip("/")
        url = f"{base}/{name}/{version}/json" if version else f"{base}/{name}/json"
        deps = _fetch_from_url(url)
        if deps is not None:
            return deps, "nexus"

    # Fall back to public PyPI
    url = PYPI_URL.format(name=name, version=version) if version else PYPI_LATEST_URL.format(name=name)
    deps = _fetch_from_url(url)
    if deps is not None:
        return deps, "pypi"

    return [], None


def _find_paths(
    target: str,
    current: str,
    version: Optional[str],
    visited: set,
    path: list,
    max_depth: int,
    pypi_base: Optional[str],
    unresolvable: set,
) -> list:
    """Recursively find all dependency chains from `current` that reach `target`.

    Returns a list of paths, where each path is a list of package names from
    the top-level requirement down to the target.
    """
    if len(path) > max_depth:
        return []
    if current in visited:
        return []

    visited = visited | {current}
    deps, source = _get_dependencies(current, version, pypi_base)

    if source is None:
        unresolvable.add(current)

    paths_found = []
    for dep in deps:
        new_path = path + [dep]
        if dep == target:
            paths_found.append(new_path)
        else:
            sub_paths = _find_paths(target, dep, None, visited, new_path, max_depth, pypi_base, unresolvable)
            paths_found.extend(sub_paths)

    return paths_found


def run_dep_trace(
    requirements_path: Optional[Path],
    target_package: str,
    max_depth: int = 6,
    pypi_url: Optional[str] = None,
) -> None:
    """Trace which top-level requirements in a requirements.txt pull in target_package."""
    target = target_package.lower().replace("-", "_")

    if not requirements_path:
        requirements_path = Path("requirements.txt")

    if not requirements_path.exists():
        print(f"ERROR: requirements file not found: {requirements_path}", file=sys.stderr)
        sys.exit(1)

    packages = _parse_requirements(requirements_path)
    if not packages:
        print("ERROR: No packages found in requirements file.", file=sys.stderr)
        sys.exit(1)

    print(f"\nScanning '{requirements_path}' for dependency chains leading to '{target}'...")
    if pypi_url:
        print(f"Registry: {pypi_url} (falling back to https://pypi.org for packages not found internally)")
    else:
        print("Registry: https://pypi.org (no --pypi-url provided; internal-only packages will not resolve)")
    print(f"Max depth: {max_depth}\n")

    found_any = False
    unresolvable: set = set()

    for name, version in packages:
        label = f"{name}=={version}" if version else name

        # Direct hit
        if name == target:
            print(f"  ✓ DIRECT:  {label}  ← is itself a top-level requirement")
            found_any = True
            continue

        print(f"  Checking {label} ...", end=" ", flush=True)
        paths = _find_paths(target, name, version, set(), [label], max_depth, pypi_url, unresolvable)

        if paths:
            print(f"FOUND  ({len(paths)} chain(s))")
            found_any = True
            for chain in paths:
                print(f"    {'  →  '.join(chain)}")
        else:
            print("not found")

    print()
    if not found_any:
        print(f"'{target}' was not found in the dependency tree (max depth {max_depth}).")

    if unresolvable:
        print("\n⚠  The following packages could not be resolved from any registry")
        print("   (likely internal/private packages with no PyPI-compatible JSON API):")
        for pkg in sorted(unresolvable):
            print(f"   - {pkg}")
        print("   Their transitive dependencies could not be checked.")
        if not pypi_url:
            print("   Tip: try --pypi-url to point at your internal Nexus PyPI proxy.")
