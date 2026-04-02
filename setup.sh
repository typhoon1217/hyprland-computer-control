#!/bin/bash
# Setup script for hyprland-computer-control Claude Code skill
# For Arch Linux + Hyprland (Wayland) users

set -e

echo "=== Hyprland Computer Control - Setup ==="
echo ""

# Check if running on Arch Linux
if ! command -v pacman &> /dev/null; then
    echo "ERROR: This script requires pacman (Arch Linux)."
    exit 1
fi

# Check if Hyprland is running
if [ "$XDG_CURRENT_DESKTOP" != "Hyprland" ]; then
    echo "WARNING: Hyprland not detected as current desktop."
    echo "  XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

echo "[1/5] Installing packages..."
sudo pacman -S --needed --noconfirm \
    ydotool wtype grim slurp wl-clipboard \
    libnotify playerctl brightnessctl pamixer jq

echo ""
echo "[2/5] Setting up uinput access..."
if [ ! -f /etc/udev/rules.d/99-uinput.rules ]; then
    echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
    sudo udevadm control --reload-rules
    echo "  udev rule created."
else
    echo "  udev rule already exists."
fi

echo ""
echo "[3/5] Adding user to input group..."
if groups "$USER" | grep -q '\binput\b'; then
    echo "  Already in input group."
else
    sudo usermod -aG input "$USER"
    echo "  Added $USER to input group (re-login required for full effect)."
fi

echo ""
echo "[4/5] Enabling ydotool daemon..."
systemctl --user enable --now ydotool.service 2>/dev/null || true
if systemctl --user is-active ydotool.service &>/dev/null; then
    echo "  ydotool daemon is running."
else
    echo "  WARNING: ydotool daemon failed to start. Try after re-login."
fi

echo ""
echo "[5/5] Installing Claude Code skill..."
SKILL_DIR="$HOME/.claude/skills/computer-control"
mkdir -p "$SKILL_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"
echo "  Installed to $SKILL_DIR"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Verify with:"
echo "  wtype --help                    # text input"
echo "  hyprctl dispatch movecursor 0 0 # mouse move"
echo "  grim /tmp/test.png              # screenshot"
echo "  pamixer --get-volume            # volume"
echo ""
echo "NOTE: If ydotool doesn't work, try:"
echo "  1. Re-login (for input group)"
echo '  2. export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"'
echo "  3. systemctl --user restart ydotool.service"
