"""Mirror container images and Helm charts from public registries to a private registry.

Reads a sources.yaml from the current directory (or a specified path) and:
  - Pulls each image and pushes it to <target-repo.docker>/<original-source>
  - Pulls each Helm chart with `helm pull` and uploads it to a Nexus3 hosted
    Helm repository via HTTP PUT using the requests library.

Example sources.yaml:
    groups:
      monitoring:
        images:
          - source: ghcr.io/grafana/grafana-operator:v5.21.4
        charts:
          - chart: kube-prometheus-stack
            repo: https://prometheus-community.github.io/helm-charts
            version: 80.13.3
    target-repo:
      docker: ctr.bcr.io
      helm: repo.bcr.io/repository/helm

Resulting image:  ctr.bcr.io/ghcr.io/grafana/grafana-operator:v5.21.4
Resulting chart:  https://repo.bcr.io/repository/helm/kube-prometheus-stack-80.13.3.tgz
"""

import getpass
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import requests
import yaml


def _load_sources(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _run(cmd: List[str], dry_run: bool = False) -> int:
    """Print and optionally execute a shell command. Returns the exit code."""
    print(f"    $ {' '.join(cmd)}")
    if dry_run:
        return 0
    result = subprocess.run(cmd)
    return result.returncode


def _prompt_helm_credentials(helm_target: str) -> Tuple[str, str]:
    """Prompt for Nexus3 credentials and return (username, password)."""
    print(f"\nHelm charts require credentials for: {helm_target}")
    username = input("  Helm registry username: ")
    password = getpass.getpass("  Helm registry password: ")
    return username, password


def _mirror_image(source: str, docker_target: str, dry_run: bool = False) -> bool:
    """Pull an image, retag it under docker_target, and push."""
    target = f"{docker_target}/{source}"
    print(f"  -> image: {source}")
    print(f"          → {target}")

    if _run(["docker", "pull", source], dry_run) != 0:
        print(f"  ERROR: failed to pull {source}", file=sys.stderr)
        return False

    if _run(["docker", "tag", source, target], dry_run) != 0:
        print(f"  ERROR: failed to tag {source}", file=sys.stderr)
        return False

    if _run(["docker", "push", target], dry_run) != 0:
        print(f"  ERROR: failed to push {target}", file=sys.stderr)
        return False

    return True


def _mirror_chart(
    chart: str,
    repo: str,
    version: str,
    helm_target: str,
    username: str,
    password: str,
    dry_run: bool = False,
) -> bool:
    """Pull a Helm chart and upload it to a Nexus3 hosted Helm repository.

    Uses the Nexus3 REST API endpoint:
      POST /service/rest/v1/components?repository=<repo-name>
    with the chart .tgz supplied as the `helm.asset` multipart field.

    helm_target should be in the form `hostname/repo-name`
    e.g. `repo.bcr.io/helm`
    """
    host, _, repo_name = helm_target.partition("/")
    upload_url = f"https://{host}/service/rest/v1/components?repository={repo_name}"
    print(f"  -> chart: {chart} {version}")
    print(f"          → {upload_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        if (
            _run(
                ["helm", "pull", chart, "--repo", repo, "--version", version, "--destination", tmpdir],
                dry_run,
            )
            != 0
        ):
            print(f"  ERROR: failed to pull chart {chart}", file=sys.stderr)
            return False

        if dry_run:
            print(f"    POST {upload_url} (helm.asset={chart}-{version}.tgz)")
            return True

        tgz_files = list(Path(tmpdir).glob("*.tgz"))
        if not tgz_files:
            print(f"  ERROR: no .tgz found after helm pull for {chart}", file=sys.stderr)
            return False

        tgz = tgz_files[0]
        print(f"    POST {upload_url} (helm.asset={tgz.name})")
        with open(tgz, "rb") as f:
            response = requests.post(
                upload_url,
                files={"helm.asset": (tgz.name, f, "application/octet-stream")},
                auth=(username, password),
            )
        if not response.ok:
            print(f"  ERROR: upload failed ({response.status_code} {response.reason})", file=sys.stderr)
            return False

    return True


def run_mirror(sources_path: Optional[Path] = None, dry_run: bool = False) -> None:
    """Entry point for the mirror command."""
    if sources_path is None:
        sources_path = Path.cwd() / "sources.yaml"

    if not sources_path.exists():
        print(f"ERROR: sources file not found: {sources_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading sources from: {sources_path}")
    if dry_run:
        print("(dry-run mode — no commands will be executed)\n")

    data = _load_sources(sources_path)
    docker_target: str = data.get("target-repo", {}).get("docker", "")
    helm_target: str = data.get("target-repo", {}).get("helm", "")
    groups: dict = data.get("groups", {})

    if not docker_target and not helm_target:
        print("ERROR: no target-repo defined in sources.yaml", file=sys.stderr)
        sys.exit(1)

    # Check upfront if any charts are present across all groups
    has_charts = any(group.get("charts") for group in groups.values())
    helm_user, helm_pass = "", ""
    if has_charts and helm_target:
        helm_user, helm_pass = _prompt_helm_credentials(helm_target)

    failures: List[str] = []

    for group_name, group in groups.items():
        print(f"\n[{group_name}]")

        for img in group.get("images", []):
            source: str = img["source"]
            if not _mirror_image(source, docker_target, dry_run):
                failures.append(f"image: {source}")

        for chart_entry in group.get("charts", []):
            chart: str = chart_entry["chart"]
            repo: str = chart_entry["repo"]
            version: str = str(chart_entry["version"])
            if not _mirror_chart(chart, repo, version, helm_target, helm_user, helm_pass, dry_run):
                failures.append(f"chart: {chart}")

    print()
    if failures:
        print(f"Completed with {len(failures)} failure(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)
    else:
        print("All items mirrored successfully.")
