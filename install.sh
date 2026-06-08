#!/bin/sh
set -e

BENCH_CLI_DIR="$HOME/bench-cli"

# Run a command as root, using sudo only when we are not already root.
maybe_sudo() {
    if [ "$(id -u)" = 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# Alpine ships almost nothing by default and uses apk + musl. Install the tools
# needed to clone bench, run uv, and build the admin venv (psutil compiles).
if [ -f /etc/alpine-release ]; then
    echo "Alpine detected — installing base dependencies via apk..."
    maybe_sudo apk add --no-cache git curl bash python3 python3-dev build-base linux-headers
fi

# Clone or update
if [ -d "$BENCH_CLI_DIR" ]; then
    echo "Updating bench-cli..."
    git -C "$BENCH_CLI_DIR" pull || echo "  (skipping update — not a tracking clone)"
else
    echo "Cloning bench-cli..."
    git clone https://github.com/frappe/bench-cli "$BENCH_CLI_DIR"
fi

chmod +x "$BENCH_CLI_DIR/bench"

# Install uv if not present
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Add to PATH in the appropriate shell rc file
add_to_path() {
    rc="$1"
    line="export PATH=\"\$HOME/bench-cli:\$PATH\""
    if ! grep -qF 'bench-cli' "$rc" 2>/dev/null; then
        echo "$line" >> "$rc"
        echo "Added bench to PATH in $rc"
    fi
}

case "$SHELL" in
    */fish)
        FISH_CONFIG="$HOME/.config/fish/config.fish"
        mkdir -p "$(dirname "$FISH_CONFIG")"
        if ! grep -qF 'bench-cli' "$FISH_CONFIG" 2>/dev/null; then
            echo "fish_add_path \$HOME/bench-cli" >> "$FISH_CONFIG"
            echo "Added bench to PATH in $FISH_CONFIG"
        fi
        ;;
    */zsh)
        add_to_path "$HOME/.zshrc"
        ;;
    */ash|*/sh|"")
        # Alpine/POSIX login shells read ~/.profile.
        add_to_path "$HOME/.profile"
        ;;
    *)
        add_to_path "$HOME/.bashrc"
        ;;
esac

export PATH="$BENCH_CLI_DIR:$PATH"

# Set up the admin venv (Flask backend for the setup wizard and admin UI)
ADMIN_VENV="$BENCH_CLI_DIR/.admin-venv"
if [ ! -f "$ADMIN_VENV/bin/python" ]; then
    echo "Setting up admin environment..."
    uv venv "$ADMIN_VENV" --quiet
    # Read deps from pyproject.toml if python3 is available, otherwise use known defaults
    if command -v python3 >/dev/null 2>&1; then
        ADMIN_DEPS=$(python3 -c "
import tomllib, sys
with open('$BENCH_CLI_DIR/pyproject.toml', 'rb') as f:
    d = tomllib.load(f)
deps = d.get('project', {}).get('optional-dependencies', {}).get('admin', [])
print(' '.join(deps))
" 2>/dev/null)
    fi
    if [ -z "$ADMIN_DEPS" ]; then
        ADMIN_DEPS="flask>=3.0 psutil>=5.9 pymysql>=1.1"
    fi
    # shellcheck disable=SC2086
    uv pip install --python "$ADMIN_VENV/bin/python" --quiet $ADMIN_DEPS
    echo "Admin environment ready."
fi

echo ""
echo "bench installed to $BENCH_CLI_DIR"
echo ""
echo "Quick start:"
echo "  bench new my-bench"
echo "  bench init"
echo "  bench new-site site1.localhost"
echo "  bench start"
echo ""
echo "If 'bench' is not found, open a new terminal or run: source ~/.profile"
