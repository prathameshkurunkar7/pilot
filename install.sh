# #!/bin/bash
# set -e

# # TARGET CONFIGURATION
# INSTALL_URL="https://raw.githubusercontent.com/frappe/bench-cli/main/install.sh"
# BENCH_CLI_DIR="$HOME/bench-cli"
# DEFAULT_USER="frappe"

# # ── arguments / environment (non-interactive support) ───────────────────────
# BENCH_USER="${BENCH_USER:-}"
# NONINTERACTIVE="${BENCH_YES:-0}"
# SUDO_PASS=""

# while [ $# -gt 0 ]; do
#     case "$1" in
#         --user) BENCH_USER="$2"; shift 2 ;;
#         --user=*) BENCH_USER="${1#*=}"; shift ;;
#         -y|--yes) NONINTERACTIVE=1; shift ;;
#         --sudo-password|--sudo-pass) SUDO_PASS="$2"; shift 2 ;;
#         --sudo-password=*|--sudo-pass=*) SUDO_PASS="${1#*=}"; shift ;;
#         *) echo "Unknown option: $1"; exit 1 ;;
#     esac
# done

# # Smart Sudo Wrapper: Safely injects password when provided non-interactively
# run_sudo() {
#     if [ "$(id -u)" -eq 0 ]; then
#         "$@"
#     elif [ -n "$SUDO_PASS" ]; then
#         echo "$SUDO_PASS" | sudo -S "$@"
#     else
#         sudo "$@"
#     fi
# }

# # ── passwordless sudo configuration ──────────────────────────────────────────
# write_sudoers() {
#     local user="$1"
#     local file="/etc/sudoers.d/$user"
#     local tmp
#     tmp="$(mktemp)"
    
#     # Disable requiretty globally if present to avoid non-interactive execution errors
#     if run_sudo grep -q "requiretty" /etc/sudoers 2>/dev/null; then
#         run_sudo sed -i 's/Defaults[[:space:]]*requiretty/# Defaults requiretty/g' /etc/sudoers 2>/dev/null || true
#     fi

#     printf '# Frappe bench — managed by install.sh, do not edit\n%s ALL=(ALL) NOPASSWD: ALL\n' "$user" > "$tmp"
#     if run_sudo visudo -cf "$tmp" >/dev/null; then
#         run_sudo install -m 0440 "$tmp" "$file"
#         echo "Configured passwordless sudo at $file"
        
#         # Fallback: Append directly to /etc/sudoers if the include directory isn't active
#         if ! run_sudo grep -q "$user ALL=(ALL) NOPASSWD: ALL" /etc/sudoers; then
#             run_sudo bash -c "echo '$user ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers"
#         fi
#     else
#         echo "Generated sudoers file is invalid — aborting."
#         rm -f "$tmp"
#         exit 1
#     fi
#     rm -f "$tmp"
# }

# ensure_passwordless_sudo() {
#     [ "$(uname)" = "Darwin" ] && return 0
#     command -v sudo >/dev/null 2>&1 || return 0

#     if sudo -n true 2>/dev/null; then
#         return 0
#     fi

#     if [ "$NONINTERACTIVE" = "1" ] && [ -z "$SUDO_PASS" ]; then
#         echo "Passwordless sudo is required but not configured, and running non-interactively."
#         exit 1
#     fi

#     echo "Bench needs passwordless sudo to install packages and manage services."
#     if [ -n "$SUDO_PASS" ]; then
#         if ! echo "$SUDO_PASS" | sudo -S -v >/dev/null 2>&1; then
#             echo "sudo authentication failed."
#             exit 1
#         fi
#     else
#         if ! sudo -v; then
#             echo "sudo authentication failed."
#             exit 1
#         fi
#     fi
#     write_sudoers "$(id -un)"
# }

# # ── Phase 1: User Initialization ─────────────────────────────────────────────
# setup_user_and_exit() {
#     if [ "$(uname)" = "Darwin" ]; then
#         echo "Warning: running as root on macOS — continuing as root (dev only)."
#         return 0
#     fi



#!/bin/bash
set -e

# TARGET CONFIGURATION
BRANCH_NAME="simpler-setup"
INSTALL_URL="https://raw.githubusercontent.com/frappe/bench-cli/simpler-setup/install.sh"
BENCH_CLI_DIR="$HOME/bench-cli"
DEFAULT_USER="frappe"

# ── arguments / environment (non-interactive support) ───────────────────────
BENCH_USER="${BENCH_USER:-}"
NONINTERACTIVE="${BENCH_YES:-0}"
SUDO_PASS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --user) BENCH_USER="$2"; shift 2 ;;
        --user=*) BENCH_USER="${1#*=}"; shift ;;
        -y|--yes) NONINTERACTIVE=1; shift ;;
        --sudo-password|--sudo-pass) SUDO_PASS="$2"; shift 2 ;;
        --sudo-password=*|--sudo-pass=*) SUDO_PASS="${1#*=}"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Smart Sudo Wrapper: Safely injects password when provided non-interactively
run_sudo() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif [ -n "$SUDO_PASS" ]; then
        echo "$SUDO_PASS" | sudo -S "$@"
    else
        sudo "$@"
    fi
}

# ── passwordless sudo configuration ──────────────────────────────────────────
write_sudoers() {
    local user="$1"
    local file="/etc/sudoers.d/$user"
    local tmp
    tmp="$(mktemp)"
    
    # Disable requiretty globally if present to avoid non-interactive execution errors
    if run_sudo grep -q "requiretty" /etc/sudoers 2>/dev/null; then
        run_sudo sed -i 's/Defaults[[:space:]]*requiretty/# Defaults requiretty/g' /etc/sudoers 2>/dev/null || true
    fi

    printf '# Frappe bench — managed by install.sh, do not edit\n%s ALL=(ALL) NOPASSWD: ALL\n' "$user" > "$tmp"
    if run_sudo visudo -cf "$tmp" >/dev/null; then
        run_sudo install -m 0440 "$tmp" "$file"
        echo "Configured passwordless sudo at $file"
        
        # Fallback: Append directly to /etc/sudoers if the include directory isn't active
        if ! run_sudo grep -q "$user ALL=(ALL) NOPASSWD: ALL" /etc/sudoers; then
            run_sudo bash -c "echo '$user ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers"
        fi
    else
        echo "Generated sudoers file is invalid — aborting."
        rm -f "$tmp"
        exit 1
    fi
    rm -f "$tmp"
}

ensure_passwordless_sudo() {
    [ "$(uname)" = "Darwin" ] && return 0
    command -v sudo >/dev/null 2>&1 || return 0

    if sudo -n true 2>/dev/null; then
        return 0
    fi

    if [ "$NONINTERACTIVE" = "1" ] && [ -z "$SUDO_PASS" ]; then
        echo "Passwordless sudo is required but not configured, and running non-interactively."
        exit 1
    fi

    echo "Bench needs passwordless sudo to install packages and manage services."
    if [ -n "$SUDO_PASS" ]; then
        if ! echo "$SUDO_PASS" | sudo -S -v >/dev/null 2>&1; then
            echo "sudo authentication failed."
            exit 1
        fi
    else
        if ! sudo -v; then
            echo "sudo authentication failed."
            exit 1
        fi
    fi
    write_sudoers "$(id -un)"
}

# ── Phase 1: User Initialization ─────────────────────────────────────────────
setup_user_and_exit() {
    if [ "$(uname)" = "Darwin" ]; then
        echo "Warning: running as root on macOS — continuing as root (dev only)."
        return 0
    fi

    echo "Setting up non-root user '$TARGET_USER'..."

    if ! id "$TARGET_USER" >/dev/null 2>&1; then
        echo "Creating user '$TARGET_USER'..."
        run_sudo useradd -m -s /bin/bash "$TARGET_USER"
        run_sudo usermod -aG sudo "$TARGET_USER" 2>/dev/null || true
    fi

    write_sudoers "$TARGET_USER"

    echo ""
    echo "========================================================================"
    echo " SUCCESS: User '$TARGET_USER' is ready with passwordless sudo privileges."
    echo "========================================================================"
    echo "Please copy, paste, and run the following commands to complete the setup:"
    echo ""
    
    if [ -f "$0" ] && [ "$0" != "bash" ] && [ "$0" != "/bin/bash" ]; then
        run_sudo cp "$0" "/home/$TARGET_USER/install.sh"
        run_sudo chown "$TARGET_USER:$TARGET_USER" "/home/$TARGET_USER/install.sh"
        run_sudo chmod +x "/home/$TARGET_USER/install.sh"
        echo "  su - $TARGET_USER"
        echo "  ./install.sh"
    else
        echo "  su - $TARGET_USER"
        echo "  curl -fsSL $INSTALL_URL | bash"
    fi
    echo ""
    echo "========================================================================"
    exit 0
}

# Determine if we need to run Phase 1 (User Setup)
TARGET_USER="${BENCH_USER:-$DEFAULT_USER}"
CURRENT_USER="$(id -un)"

if [ "$CURRENT_USER" != "$TARGET_USER" ]; then
    setup_user_and_exit
fi

# ── Phase 2: Execution (Runs natively inside target user shell) ──────────────
ensure_passwordless_sudo

# Clone or update the specific branch
if [ -d "$BENCH_CLI_DIR" ]; then
    echo "Updating bench-cli..."
    git -C "$BENCH_CLI_DIR" pull
else
    echo "Cloning bench-cli ($BRANCH_NAME branch)..."
    git clone -b "$BRANCH_NAME" https://github.com/frappe/bench-cli "$BENCH_CLI_DIR"
fi

chmod +x "$BENCH_CLI_DIR/bench"

# Install uv if not present
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Install Node.js
if ! command -v node >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    echo "Installing Node.js..."
    # Download script to file first to ensure sudo -S does not intercept stdin stream
    NODE_SETUP_TMP="$(mktemp)"
    curl -fsSL https://deb.nodesource.com/setup_24.x -o "$NODE_SETUP_TMP"
    run_sudo bash "$NODE_SETUP_TMP"
    rm -f "$NODE_SETUP_TMP"
    run_sudo apt-get install -y nodejs
fi

# ── add bench to PATH ───────────────────────────────────────────────────────
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

# ── admin venv ──────────────────────────────────────────────────────────────
ADMIN_VENV="$BENCH_CLI_DIR/.admin-venv"
if [ ! -f "$ADMIN_VENV/bin/python" ]; then
    echo "Setting up admin environment..."
    uv venv "$ADMIN_VENV" --quiet
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
    uv pip install --python "$ADMIN_VENV/bin/python" --quiet $ADMIN_DEPS
    echo "Admin environment ready."
fi

echo ""
echo "bench installed to $BENCH_CLI_DIR"
echo ""
echo "Quick start:"
echo "  bench new my-bench"
echo "  bench init"
echo "  new-site site1.localhost"
echo "  bench start"
echo ""
echo "If 'bench' is not found, open a new terminal or run: source ~/.bashrc"
