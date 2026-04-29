#!/bin/bash
# Setup script for hyprland-computer-control Claude Code skills.
# Installs both the real-desktop skill (hypr-cc) and the sandbox
# skill (hypr-ccv), plus short dispatcher commands
# (hypr-cc, hypr-ccv) on ~/.local/bin.
# For Arch Linux + Hyprland (Wayland) users.

set -e

echo "=== Hyprland Computer Control - Setup ==="
echo ""

if ! command -v pacman &> /dev/null; then
    echo "ERROR: This script requires pacman (Arch Linux)."
    exit 1
fi

if [ "$XDG_CURRENT_DESKTOP" != "Hyprland" ]; then
    echo "WARNING: Hyprland not detected as current desktop."
    echo "  XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

echo "[1/7] Installing packages..."
sudo pacman -S --needed --noconfirm \
    ydotool wtype grim slurp wl-clipboard \
    libnotify playerctl brightnessctl pamixer jq \
    wayvnc

echo ""
echo "[2/7] Setting up uinput access..."
if [ ! -f /etc/udev/rules.d/99-uinput.rules ]; then
    echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
    sudo udevadm control --reload-rules
    echo "  udev rule created."
else
    echo "  udev rule already exists."
fi

echo ""
echo "[3/7] Adding user to input group..."
if groups "$USER" | grep -q '\binput\b'; then
    echo "  Already in input group."
else
    sudo usermod -aG input "$USER"
    echo "  Added $USER to input group (re-login required for full effect)."
fi

echo ""
echo "[4/7] Enabling ydotool daemon..."
systemctl --user enable --now ydotool.service 2>/dev/null || true
if systemctl --user is-active ydotool.service &>/dev/null; then
    echo "  ydotool daemon is running."
else
    echo "  WARNING: ydotool daemon failed to start. Try after re-login."
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "[5/7] Installing hypr-cc skill (real desktop)..."
SKILL_DIR="$HOME/.claude/skills/hypr-cc"
mkdir -p "$SKILL_DIR/bin"
cp "$SCRIPT_DIR/hypr-cc/SKILL.md" "$SKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/hypr-cc/bin/hypr-cc" "$SKILL_DIR/bin/hypr-cc"
chmod +x "$SKILL_DIR/bin/hypr-cc"
echo "  Installed to $SKILL_DIR"

echo ""
echo "[6/7] Installing hypr-ccv skill (sandbox)..."
VSKILL_DIR="$HOME/.claude/skills/hypr-ccv"
mkdir -p "$VSKILL_DIR/scripts"
cp "$SCRIPT_DIR/hypr-ccv/SKILL.md"      "$VSKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/hypr-ccv/scripts/"*     "$VSKILL_DIR/scripts/"
chmod +x "$VSKILL_DIR/scripts/"*.sh "$VSKILL_DIR/scripts/cc-click.py" "$VSKILL_DIR/scripts/hypr-ccv"
echo "  Installed to $VSKILL_DIR"

echo ""
echo "[7/7] Linking dispatchers to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
ln -sf "$SKILL_DIR/bin/hypr-cc"          "$HOME/.local/bin/hypr-cc"
ln -sf "$VSKILL_DIR/scripts/hypr-ccv"    "$HOME/.local/bin/hypr-ccv"
echo "  Linked $HOME/.local/bin/hypr-cc → $SKILL_DIR/bin/hypr-cc"
echo "  Linked $HOME/.local/bin/hypr-ccv → $VSKILL_DIR/scripts/hypr-ccv"

if ! echo ":$PATH:" | grep -q ":$HOME/.local/bin:"; then
    echo ""
    echo "  WARNING: ~/.local/bin is NOT on your PATH."
    echo "  Add this to your shell rc (e.g., ~/.zshrc, ~/.bashrc):"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Real-desktop skill (touches user's actual session):"
echo "  hypr-cc help"
echo "  hypr-cc shot /tmp/screen.png"
echo "  hypr-cc click 540 320"
echo "  hypr-cc type 'hello'"
echo ""
echo "Sandbox skill (isolated):"
echo "  hypr-ccv start"
echo "  hypr-ccv status"
echo "  hypr-ccv run firefox"
echo "  hypr-ccv click 540 320"
echo "  hypr-ccv type 'hello'"
echo "  hypr-ccv shot /tmp/sandbox.png"
echo "  hypr-ccv stop"
echo ""
echo "NOTE: If ydotool doesn't work, try:"
echo "  1. Re-login (for input group)"
echo '  2. export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"'
echo "  3. systemctl --user restart ydotool.service"
