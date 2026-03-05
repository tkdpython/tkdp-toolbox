# tkdp-toolbox

Swiss army knife toolbox for a devops engineer.

## Installation

```bash
pip install tkdp-toolbox
```

After installation the `tkdptoolbox` (and `tkdp-toolbox`) commands will be available on your PATH.

---

## Commands

### `mirror` — Mirror images and Helm charts to a private registry

Reads a `sources.yaml` file and mirrors container images and Helm charts from public registries into your private registry.

#### Prerequisites

- **Docker** must be installed and you must already be **logged in** to your target Docker registry before running this command (`docker login <registry>`). The tool does not handle Docker authentication.
- **Helm** must be installed and available on your PATH.
- **Helm chart uploads** are supported for **Nexus3 hosted Helm repositories only**. You will be prompted for credentials at runtime if any charts are present in the sources file.

#### Usage

```bash
# Run from the directory containing sources.yaml
tkdptoolbox mirror

# Specify a sources file explicitly
tkdptoolbox mirror --sources /path/to/sources.yaml

# Preview what would happen without executing anything
tkdptoolbox mirror --dry-run
```

#### `sources.yaml` format

```yaml
groups:
  <group-name>:
    images:
      - source: <registry>/<image>:<tag>
    charts:
      - chart: <chart-name>
        repo: <helm-repo-url>
        version: <version>

target-repo:
  docker: <target-docker-registry>        # e.g. ctr.local
  helm: <nexus3-host>/<repository-name>   # e.g. repo.local/helm
```

Multiple groups can be defined; they are processed in order.

#### Example `sources.yaml`

```yaml
groups:
  monitoring:
    images:
      - source: docker.io/grafana/grafana:12.3.0
      - source: ghcr.io/grafana/grafana-operator:v5.21.4
      - source: quay.io/prometheus/prometheus:v3.9.1

    charts:
      - chart: kube-prometheus-stack
        repo: https://prometheus-community.github.io/helm-charts
        version: 80.13.3
      - chart: grafana-operator
        repo: https://grafana.github.io/helm-charts
        version: 5.21.4

target-repo:
  docker: ctr.local
  helm: repo.local/helm
```

#### How images are mirrored

Each image is pulled from its source, retagged, and pushed with the target registry prepended:

```
docker.io/grafana/grafana:12.3.0  →  ctr.local/docker.io/grafana/grafana:12.3.0
ghcr.io/grafana/grafana-operator:v5.21.4  →  ctr.local/ghcr.io/grafana/grafana-operator:v5.21.4
```

This preserves the full original path under the target registry, making it easy to see the origin of each image.

#### How Helm charts are mirrored

Charts are pulled from their source Helm repository using `helm pull` and uploaded to the Nexus3 hosted Helm repository via the Nexus3 REST API (`POST /service/rest/v1/components?repository=<name>`).

> **Note:** Only **Nexus3 hosted Helm repositories** are supported as the chart upload target. Credentials are prompted once at startup if any charts are present.

The `helm` value in `target-repo` must be in the form `<host>/<repository-name>`, where `<repository-name>` matches the name of the hosted Helm repository in Nexus3.

---

### `env-replace` — Recursively replace environment-specific values in files

Reads a `.far.yml` configuration file and replaces all values belonging to the source environment with the corresponding values from the destination environment across every `.md`, `.yaml`, and `.yml` file under the config's directory.

The tool walks up the directory tree from the working directory (or a specified `--path`) to locate the nearest `.far.yml` file.

#### Usage

```bash
# Replace staging values with production values (searches for .far.yml from cwd)
tkdptoolbox env-replace --src-env staging --dst-env production

# Preview what would change without modifying any files
tkdptoolbox env-replace --src-env staging --dst-env production --dry-run

# Start the file search from a specific directory
tkdptoolbox env-replace --src-env staging --dst-env production --path /path/to/project
```

#### `.far.yml` format

```yaml
- <src-env>: <value to find>
  <dst-env>: <replacement value>
- <src-env>: <another value to find>
  <dst-env>: <another replacement value>
```

The file is a YAML list. Each item is a mapping with environment names as keys and the environment-specific string as the value. When replacing from `--src-env` to `--dst-env`, every source value found in a file is substituted with the matching destination value.

#### Example `.far.yml`

```yaml
- staging: db-staging.internal
  production: db.internal
- staging: https://api-staging.example.com
  production: https://api.example.com
- staging: registry-staging.example.com
  production: registry.example.com
```

Running `tkdptoolbox env-replace --src-env staging --dst-env production` would replace:

```
db-staging.internal              →  db.internal
https://api-staging.example.com  →  https://api.example.com
registry-staging.example.com    →  registry.example.com
```

---

### `dep-trace` — Trace which dependency pulls in a vulnerable package

Given a `requirements.txt` and a target package name, walks the dependency tree to find which top-level requirement (or chain of transitive dependencies) is responsible for pulling in that package.

Useful when a vulnerability scanner (e.g. Trivy) flags a package CVE and you need to know which of your direct dependencies to upgrade or replace.

Supports mixed environments where some packages are on an internal Nexus PyPI proxy and others are on public PyPI. When `--pypi-url` is provided, each package is looked up on the internal registry first, falling back to public PyPI automatically. Packages that cannot be resolved from either registry (internal-only packages with no PyPI-compatible JSON API) are flagged clearly at the end.

#### Usage

```bash
# Search for the package that pulls in 'ecdsa' (CVE-2024-23342)
tkdptoolbox dep-trace --package ecdsa

# Specify a requirements file explicitly
tkdptoolbox dep-trace --requirements /path/to/requirements.txt --package ecdsa

# Use an internal Nexus PyPI proxy (tries Nexus first, falls back to pypi.org)
tkdptoolbox dep-trace --package ecdsa --pypi-url https://repo.bcr.io/repository/pypi-public/pypi

# Increase search depth for deeply nested dependency trees
tkdptoolbox dep-trace --package ecdsa --max-depth 10
```

#### Example output

```
Scanning 'requirements.txt' for dependency chains leading to 'ecdsa'...
Registry: https://repo.bcr.io/repository/pypi-public/pypi (falling back to https://pypi.org for packages not found internally)
Max depth: 6

  Checking nat_logger==1.2.0 ... not found
  Checking fastapi==0.115.0 ... not found
  Checking python_jose==3.3.0 ... FOUND  (1 chain(s))
    python_jose==3.3.0  →  ecdsa
  Checking requests==2.31.0 ... not found

⚠  The following packages could not be resolved from any registry
   (likely internal/private packages with no PyPI-compatible JSON API):
   - nat_logger
   Their transitive dependencies could not be checked.
```

In the above example, `python-jose` is the culprit — upgrading or replacing it resolves the CVE.

---

## Options reference

| Command | Option | Description |
|---|---|---|
| `mirror` | `--sources FILE` | Path to `sources.yaml`. Defaults to `./sources.yaml`. |
| `mirror` | `--dry-run` | Print all commands and API calls without executing them. |
| `env-replace` | `--src-env ENV` | **(required)** Source environment key in `.far.yml` (values to find). |
| `env-replace` | `--dst-env ENV` | **(required)** Destination environment key in `.far.yml` (values to substitute). |
| `env-replace` | `--path DIR` | Directory to start the `.far.yml` search from. Defaults to the current directory. |
| `env-replace` | `--dry-run` | Preview replacements without modifying any files. |
| `dep-trace` | `--package PACKAGE` | **(required)** Package name to search for (e.g. `ecdsa`). |
| `dep-trace` | `--requirements FILE` | Path to `requirements.txt`. Defaults to `./requirements.txt`. |
| `dep-trace` | `--pypi-url URL` | Base URL of a PyPI-compatible JSON API (e.g. internal Nexus proxy). Falls back to `pypi.org` if package not found. |
| `dep-trace` | `--max-depth N` | Maximum dependency tree depth to search. Defaults to `6`. |
