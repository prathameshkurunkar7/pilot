# bench.yml — Configuration Specification

`bench.yml` is the single source of truth for a bench environment. It lives at the root of the bench directory.

---

## Full schema

```yaml
# ── Bench identity ────────────────────────────────────────────────────────────
bench:
  name: my-bench            # used in process names and log prefixes
  python: "3.14"            # Python version to use for the virtualenv
  process_manager: honcho   # honcho (dev, foreground) | supervisor (production, daemon)

# ── Apps to clone and install ─────────────────────────────────────────────────
apps:
  - name: frappe            # must be a valid Python package name
    repo: https://github.com/frappe/frappe
    branch: version-16

  - name: erpnext
    repo: https://github.com/frappe/erpnext
    branch: version-16
    branches:               # optional: list of branches switchable from the admin UI
      - version-15
      - version-16

# ── Sites ─────────────────────────────────────────────────────────────────────
sites:
  - name: site1.localhost
    admin_password: "admin" # Frappe administrator password for this site
    apps:                   # apps to install on this site, in order
      - frappe
      - erpnext

# ── MariaDB ───────────────────────────────────────────────────────────────────
mariadb:
  host: localhost
  port: 3306
  root_password: "root"     # used only during bench init to create databases/users
  version: "10.6"           # optional — pin to a specific MariaDB version

# ── Redis ─────────────────────────────────────────────────────────────────────
redis:
  port: 13000               # single Redis instance for all services (simplest)
  version: "7"              # optional — pin to a specific Redis major version
  # or use separate instances:
  # cache_port: 13000
  # queue_port: 11000
  # socketio_port: 12000

# ── Workers ───────────────────────────────────────────────────────────────────
workers:
  default: 2                # handles normal background jobs
  short: 1                  # handles quick jobs (< 5 seconds expected)
  long: 1                   # handles slow/bulk jobs

# ── Nginx (production only) ───────────────────────────────────────────────────
nginx:
  enabled: false            # set to true to enable production nginx setup
  http_port: 80
  https_port: 443
  config_dir: /etc/nginx/conf.d
  worker_processes: auto
  client_max_body_size: 50m

# ── Let's Encrypt (production only) ──────────────────────────────────────────
letsencrypt:
  email: admin@example.com  # required if any site has ssl: true
  webroot_path: /var/www/letsencrypt

# ── Admin UI ──────────────────────────────────────────────────────────────────
admin:
  port: 8002        # port the admin UI listens on
  enabled: false    # set to true to enable the admin UI
  timeout: 180      # seconds of inactivity before auto-stop (standalone mode only)
```

---

## Field reference

### `bench`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Human-readable bench name. Used in process labels and log file names. |
| `python` | string | yes | — | Python version string (e.g. `"3.14"`). Must be available on the system or installable via `deadsnakes/ppa`. |
| `process_manager` | string | no | `honcho` | Process manager to use. `honcho` runs processes in the foreground (development). `supervisor` runs them as a background daemon managed by supervisord (production). |

### `apps[]`

Each entry describes a git repository to clone into `apps/`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Directory name under `apps/` and the Python package name used for `uv pip install -e`. |
| `repo` | string | yes | Git remote URL (HTTPS or SSH). |
| `branch` | string | yes | The currently active git branch to checkout. |
| `branches` | list of strings | no | All branches available to switch between via the admin UI. When set, `branch` must be one of the listed values. |

**Example with multiple branches:**
```yaml
apps:
  - name: gameplan
    repo: https://github.com/frappe/gameplan
    branch: main
    branches:
      - main
      - develop
```

Clicking a branch chip in the admin UI triggers a `switch-branch` task: git checkout → pip reinstall → asset rebuild. The `branch` field in `bench.yml` is updated automatically after a successful switch.

**Constraints:**
- `name` values must be unique.
- The first app listed is treated as the **framework app** (frappe). It must expose a `bench` CLI entry point for site management commands.
- Apps are installed into the virtualenv in the order listed.
- When `branches` is provided, `branch` must appear in that list.

### `sites[]`

Each entry describes a Frappe site to create under `sites/`.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Site directory name and the hostname used to access the site. |
| `admin_password` | string | no | `"admin"` | Frappe administrator password set during `new-site`. |
| `apps[]` | list of strings | yes | — | App names to install, in order. Must all appear in the top-level `apps` list. `frappe` (or the first app) must be listed first. |
| `domains[]` | list of strings | no | `[]` | Additional public hostnames that serve this site. Included in the Nginx `server_name` directive and as SANs on the SSL certificate. |
| `ssl` | bool | no | `false` | When `true`, Nginx terminates TLS using a Let's Encrypt certificate covering `name` and all `domains`. |

> **Note:** MariaDB database name and credentials are generated automatically by frappe's `new-site` and written into `sites/<name>/site_config.json`. You do not configure them in `bench.yml`.

**Constraints:**
- `name` values must be unique.
- Every string in `apps` must match a `name` in the top-level `apps` list.

### `mariadb`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `host` | string | no | `localhost` | MariaDB server host. |
| `port` | int | no | `3306` | MariaDB server port. |
| `root_password` | string | yes | — | Root password used to create site databases and users during `bench init`. |
| `version` | string | no | — | MariaDB version to install (e.g. `"10.6"`, `"10.11"`, `"11.4"`). On macOS, selects the `mariadb@<version>` Homebrew formula; on Ubuntu, installs the `mariadb-server-<version>` apt package. Omit to install whichever version the package manager offers by default. |

### `redis`

**Single-instance mode** (recommended for most benches): specify one `port` and a single Redis server handles all three services using separate database numbers (`/0` cache, `/1` queue, `/2` socketio).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `port` | int | no | — | Run a single Redis instance on this port for all services. When set, `cache_port`/`queue_port`/`socketio_port` are ignored. |
| `cache_port` | int | no | `13000` | Port for the Redis cache instance (multi-instance mode). |
| `queue_port` | int | no | `11000` | Port for the Redis queue instance (multi-instance mode). |
| `socketio_port` | int | no | `12000` | Port for the Redis socketio instance (multi-instance mode). |
| `version` | string | no | — | Redis version to install (e.g. `"7"`, `"7.0"`). On macOS, selects the `redis@<version>` Homebrew formula. On Ubuntu, apt has no versioned redis package names — use the official Redis apt repository for version pinning, then omit this field. |

In single-instance mode, one `redis` process appears in the Procfile and one `redis.conf` is written to `config/`. In multi-instance mode, three separate processes (`redis_cache`, `redis_queue`, `redis_socketio`) and three config files are generated. All ports must be in the range 1024–65535.

### `workers`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `default` | int | no | `2` | Number of default-queue worker processes. |
| `short` | int | no | `1` | Number of short-queue worker processes. |
| `long` | int | no | `1` | Number of long-queue worker processes. |

### `nginx` _(production only)_

Omit this section entirely for development benches. The section is only read by `bench setup nginx` and `bench setup production`.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | yes | `false` | Must be `true` for `bench setup nginx` to proceed. Acts as an explicit opt-in to production nginx setup. |
| `http_port` | int | no | `80` | Port Nginx listens on for plain HTTP. |
| `https_port` | int | no | `443` | Port Nginx listens on for HTTPS. |
| `config_dir` | string | no | `/etc/nginx/conf.d` | System directory where the bench include-pointer file is symlinked. Requires sudo. |
| `worker_processes` | string or int | no | `auto` | Passed to the Nginx `worker_processes` directive. |
| `client_max_body_size` | string | no | `50m` | Maximum upload size. Increase for large file imports. |

### `letsencrypt` _(production only)_

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `email` | string | yes (if any `ssl: true`) | — | Contact email for ACME account registration. |
| `webroot_path` | string | no | `/var/www/letsencrypt` | Directory certbot writes HTTP-01 challenge files to. Nginx serves this path at `/.well-known/acme-challenge/`. |

### `admin`

The admin process always starts as part of the Procfile. When `enabled` is `false` (the default), every request returns a plain "Admin is off" page — no data is read and no API logic runs. Set `enabled: true` in `bench.yml` to turn on the full UI; no restart is required since the config is re-read on each request.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `port` | int | no | `8002` | Port the admin process listens on. |
| `enabled` | bool | no | `false` | Set to `true` to enable the admin UI. When `false`, all routes return a "Admin is off" page. |
| `timeout` | int | no | `180` | Seconds of inactivity before the admin process auto-stops. Only applies when started standalone via `bench start-admin`, not when managed by the Procfile. |

---

## Validation rules

bench validates `bench.yml` before executing any command. Violations produce a clear error message that names the offending field.

1. Required fields must be present.
2. `bench.name` must match `^[a-zA-Z][a-zA-Z0-9_-]*$`.
3. `bench.process_manager` must be `honcho` or `supervisor` if provided.
4. All `apps[].name` values must be unique.
5. All `sites[].name` values must be unique.
6. All `sites[].apps` values must reference a name in `apps[].name`.
7. Each `sites[].apps` list must begin with the framework app (first entry in `apps`).
8. All Redis ports must be integers in the range 1024–65535. In multi-instance mode (`cache_port`/`queue_port`/`socketio_port`), each port must be distinct.
9. Worker counts must be positive integers.
10. If any `sites[].ssl` is `true`, then `nginx.enabled` must be `true` and `letsencrypt.email` must be non-empty.
11. `letsencrypt.email` must match a basic email pattern (`^[^@]+@[^@]+\.[^@]+$`) when present.
12. All entries in `sites[].domains` must be valid hostnames (no spaces, no path separators).
13. `nginx.http_port` and `nginx.https_port` must be distinct.
14. `mariadb.version` and `redis.version`, when present, must match `^\d+(\.\d+)*$` (e.g. `"10.6"`, `"7"`, `"7.0"`).

---

## Minimal example

```yaml
bench:
  name: dev
  python: "3.14"

apps:
  - name: frappe
    repo: https://github.com/frappe/frappe
    branch: version-16

sites:
  - name: site1.localhost
    apps:
      - frappe

mariadb:
  root_password: "root"

redis:
  port: 13000
```
