# bench-cli

[![Unit Tests](https://github.com/frappe/bench-cli/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/frappe/bench-cli/actions/workflows/unit-tests.yml)

A zero-dependency CLI for managing [Frappe](https://frappeframework.com) environments with Admin UI. Single `bench.toml`. No Docker.

![Apps](docs/screenshots/apps.png)

## Improvements from legacy bench

| | Legacy | bench-cli |
|---|---|---|
| Dependencies | ~20 Python packages | Zero — stdlib only |
| Marketplace | None | App registry `apps.json` |
| Config | None | Single `bench.toml` |
| Folder layout | Wherever you `bench init` | All benches under `bench-cli/benches/` |
| Process manager | Honcho / Supervisor | Built-in Procfile runner |
| Python env | pip + virtualenv | [uv](https://github.com/astral-sh/uv) (auto-installed) |
| Admin UI | None | Built-in — app status, sites, logs, task runner |

## Requirements

**Ubuntu 22.04+** — Python 3.11+, `sudo` access  
**macOS** — Python 3.11+, [Homebrew](https://brew.sh) (dev only)

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/frappe/bench-cli/main/install.sh | bash
```

Clones to `~/bench-cli` and adds `bench` to `PATH`. Or manually:

```bash
git clone https://github.com/frappe/bench-cli ~/bench-cli
echo 'export PATH="$HOME/bench-cli:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

## Quick start

```bash
bench new my-bench       # creates bench.toml — edit it to set MariaDB password
bench init               # installs deps, creates venv, clones frappe, generates Procfile
bench get-app https://github.com/frappe/erpnext --branch version-16
bench new-site site1.localhost
bench start              # starts web, workers, Redis, and admin UI
```

- App: `http://site1.localhost:8000`
- Admin UI: `http://localhost:8002`

## bench.toml

```toml
[bench]
name = "my-bench"
python = "3.14"

[[apps]]
name = "frappe"
repo = "https://github.com/frappe/frappe"
branch = "version-16"

[mariadb]
host = "localhost"
port = 3306
root_password = "your_root_password"

[redis]
port = 13000

[workers]
default = 2
short = 1
long = 1

[admin]
port = 8002
password = "your-admin-password"   # required — admin refuses to start without this
domain = "admin.example.com"       # optional — serve admin over HTTPS via nginx

[production]
lightweight = false   # false = supervisor (default), true = systemd --user
nginx = true          # run nginx setup as part of bench setup production
```

Apps and sites are tracked by the filesystem — no need to list them in `bench.toml`.

## Commands

| Command | What it does |
|---------|-------------|
| `bench new <name>` | Scaffold a new bench |
| `bench init` | Install deps, create venv, clone framework, generate Procfile |
| `bench start` | Start all processes (web, workers, Redis, admin UI) |
| `bench stop` | Stop a running bench from another terminal |
| `bench restart` | Restart all processes — supervisor or systemd (production only) |
| `bench get-app <repo>` | Clone and install an app |
| `bench new-site <name>` | Create a site |
| `bench build` | Download pre-built assets (use `--force` to rebuild from source) |
| `bench update` | git pull + reinstall + migrate all sites |
| `bench upgrade` | Pull latest bench-cli and download the admin frontend |
| `bench setup config` | Regenerate Procfile and config files from bench.toml |
| `bench build-admin` | Rebuild admin frontend assets from source |
| `bench setup nginx` | Generate and install nginx config |
| `bench setup letsencrypt` | Obtain SSL certificates |
| `bench setup production` | Full production setup (nginx + SSL + supervisor/systemd) |

With multiple benches: `bench -b my-bench start`

## Production

```toml
[production]
nginx = true          # include nginx in bench setup production
# lightweight = true  # uncomment to use systemd --user instead of supervisor

[nginx]
enabled = true

[letsencrypt]
email = "ops@example.com"

[admin]
port = 8002
password = "your-admin-password"
domain = "admin.example.com"   # optional — serve admin UI over HTTPS
```

```bash
bench setup production         # process manager (supervisor or systemd) + nginx + SSL
bench restart                  # restart all bench processes (works with both managers)
```

**Process managers:**
- **Supervisor** (default) — runs a bench-owned `supervisord` instance, no root needed.
- **Systemd** (`lightweight = true`) — uses `systemctl --user` units; requires `loginctl enable-linger` once.

When `admin.domain` is set, `bench setup production` obtains a certificate for that domain and generates an HTTPS nginx proxy block. HTTP redirects to HTTPS automatically.

The admin UI (port 8002 / `admin.domain`) shows Start, Stop, and Restart buttons on the Processes page when running in production mode.

## Directory layout

```
bench-cli/
└── benches/
    └── my-bench/
        ├── bench.toml              # infra config (python, db, redis, workers)
        ├── apps/                   # cloned app source
        ├── sites/
        │   ├── apps.txt
        │   ├── common_site_config.json
        │   └── site1.localhost/
        ├── env/                    # Python virtualenv (managed by uv)
        ├── logs/                   # per-process log files
        ├── pids/                   # bench.pid + per-process PID files
        └── config/                 # Procfile, Redis configs, Nginx configs
```

## Testing

```bash
# Install test dependencies
pip install -e ".[test]"

# Run unit tests
pytest tests/ --ignore=tests/integration

# Run with coverage
pytest tests/ --ignore=tests/integration --cov=bench_cli --cov-report=term-missing
```

Unit tests run against mocked filesystems — no MariaDB, Redis, or network required.

Integration tests (in `tests/integration/`) run the full `bench init` → `bench new-site` lifecycle against real services and are triggered by CI on push to `main`.
