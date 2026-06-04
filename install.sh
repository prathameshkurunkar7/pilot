#!/bin/bash
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)." >&2
    exit 1
fi

if [ -n "$SUDO_USER" ]; then
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_HOME="$HOME"
fi

BENCH_CLI_DIR="$REAL_HOME/bench-cli"

echo $BENCH_CLI_DIR

Clone or update
if [ -d "$BENCH_CLI_DIR" ]; then
    echo "Updating bench-cli..."
    git -C "$BENCH_CLI_DIR" pull
else
    echo "Cloning bench-cli..."
    git clone https://github.com/frappe/bench-cli "$BENCH_CLI_DIR"
fi

chmod +x "$BENCH_CLI_DIR/bench"

# Install uv if not present
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Add to PATH in the appropriate shell rc file
add_to_path() {
    local rc="$1"
    local line="export PATH=\"\$HOME/bench-cli:\$PATH\""
    if ! grep -qF 'bench-cli' "$rc" 2>/dev/null; then
        echo "$line" >> "$rc"
        echo "Added bench to PATH in $rc"
    fi
}

if [[ "$SHELL" == */fish ]]; then
    FISH_CONFIG="$HOME/.config/fish/config.fish"
    mkdir -p "$(dirname "$FISH_CONFIG")"
    if ! grep -qF 'bench-cli' "$FISH_CONFIG" 2>/dev/null; then
        echo "fish_add_path \$HOME/bench-cli" >> "$FISH_CONFIG"
        echo "Added bench to PATH in $FISH_CONFIG"
    fi
elif [[ "$SHELL" == */zsh ]]; then
    add_to_path "$HOME/.zshrc"
else
    add_to_path "$HOME/.bashrc"
fi

export PATH="$BENCH_CLI_DIR:$PATH"

# Configure supervisord to include bench supervisor configs
configure_supervisor() {
    local conf="/etc/supervisor/supervisord.conf"
    local include_glob="$BENCH_CLI_DIR/benches/*/config/supervisor/*.conf"

    if [ ! -f "$conf" ]; then
        echo "Warning: $conf not found — skipping supervisor include setup."
        return
    fi

    if grep -qF "$include_glob" "$conf"; then
        echo "Supervisor include already configured."
        return
    fi

    if grep -q '^\[include\]' "$conf"; then
        sed -i "/^\[include\]/a files = $include_glob" "$conf"
    else
        printf '\n[include]\nfiles = %s\n' "$include_glob" >> "$conf"
    fi
}

configure_supervisor

# Configure nginx to include bench site configs (inside the http block)
configure_nginx() {
    local conf="/etc/nginx/nginx.conf"
    local include_path="$BENCH_CLI_DIR/benches/*/config/nginx/include.conf"

    if [ ! -f "$conf" ]; then
        echo "Warning: $conf not found — skipping nginx include setup."
        return
    fi

    if grep -qF "$include_path" "$conf"; then
        echo "Nginx include already configured."
        return
    fi

    sed -i "/^\s*http\s*{/a\\    include $include_path;" "$conf"

    echo "Configured nginx to include $include_path"
    nginx -t && nginx -s reload 2>/dev/null || true
}

configure_nginx

echo ""
echo "bench installed to $BENCH_CLI_DIR"
echo ""
echo "Quick start:"
echo "  bench new my-bench"
echo "  bench init"
echo "  bench new-site site1.localhost"
echo "  bench start"
echo ""
echo "If 'bench' is not found, open a new terminal or run: source ~/.zshrc"
