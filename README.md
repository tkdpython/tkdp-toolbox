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
environments:
  <env-name>:
    <KEY>: <value>
    ...
  <other-env-name>:
    <KEY>: <value>
    ...
```

Each top-level key under `environments` is an environment name. Keys within an environment map a logical variable name to the environment-specific string value. When replacing from `--src-env` to `--dst-env`, every source value found in a file is substituted with the matching destination value.

#### Example `.far.yml`

```yaml
environments:
  staging:
    DB_HOST: db-staging.internal
    API_URL: https://api-staging.example.com
    REGISTRY: registry-staging.example.com

  production:
    DB_HOST: db.internal
    API_URL: https://api.example.com
    REGISTRY: registry.example.com
```

Running `tkdptoolbox env-replace --src-env staging --dst-env production` would replace:

```
db-staging.internal            →  db.internal
https://api-staging.example.com  →  https://api.example.com
registry-staging.example.com  →  registry.example.com
```

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
