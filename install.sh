#!/bin/bash
set -e

BENCH_CLI_DIR="$HOME/bench-cli"

# Clone or update bench-cli
if [ -d "$BENCH_CLI_DIR" ]; then
    echo "Updating bench-cli..."
    git -C "$BENCH_CLI_DIR" pull
else
    echo "Cloning bench-cli..."
    git clone https://github.com/frappe/bench-cli "$BENCH_CLI_DIR"
fi

# Make the bench wrapper executable
chmod +x "$BENCH_CLI_DIR/bench"

# Add ~/bench-cli to PATH permanently so `bench` is available anywhere
SHELL_RC="$HOME/.bashrc"
if [[ "$SHELL" == */zsh ]]; then
    SHELL_RC="$HOME/.zshrc"
fi

PATH_LINE="export PATH=\"\$HOME/bench-cli:\$PATH\""
if ! grep -qF 'bench-cli' "$SHELL_RC" 2>/dev/null; then
    echo "$PATH_LINE" >> "$SHELL_RC"
fi

export PATH="$BENCH_CLI_DIR:$PATH"

echo ""
echo "bench installed to $BENCH_CLI_DIR"
echo "bench commands are available from any directory."
echo ""
echo "Run: bench new my-bench"
echo ""
echo "If bench is not found, run: source $SHELL_RC"
