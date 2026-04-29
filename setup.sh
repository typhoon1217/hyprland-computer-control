#!/bin/bash
# Setup script for hyprland-computer-control Claude Code skills.
# Installs both the real-desktop skill (computer-control) and the sandbox
# skill (computer-control-vdisplay).
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

echo "[1/6] Installing packages..."
sudo pacman -S --needed --noconfirm \
    ydotool wtype grim slurp wl-clipboard \
    libnotify playerctl brightnessctl pamixer jq \
    wayvnc

echo ""
echo "[2/6] Setting up uinput access..."
if [ ! -f /etc/udev/rules.d/99-uinput.rules ]; then
    echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
    sudo udevadm control --reload-rules
    echo "  udev rule created."
else
    echo "  udev rule already exists."
fi

echo ""
echo "[3/6] Adding user to input group..."
if groups "$USER" | grep -q '\binput\b'; then
    echo "  Already in input group."
else
    sudo usermod -aG input "$USER"
    echo "  Added $USER to input group (re-login required for full effect)."
fi

echo ""
echo "[4/6] Enabling ydotool daemon..."
systemctl --user enable --now ydotool.service 2>/dev/null || true
if systemctl --user is-active ydotool.service &>/dev/null; then
    echo "  ydotool daemon is running."
else
    echo "  WARNING: ydotool daemon failed to start. Try after re-login."
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "[5/6] Installing computer-control skill (real desktop)..."
SKILL_DIR="$HOME/.claude/skills/computer-control"
mkdir -p "$SKILL_DIR"
cp "$SCRIPT_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"
echo "  Installed to $SKILL_DIR"

echo ""
echo "[6/6] Installing computer-control-vdisplay skill (sandbox)..."
VSKILL_DIR="$HOME/.claude/skills/computer-control-vdisplay"
mkdir -p "$VSKILL_DIR/scripts"
cp "$SCRIPT_DIR/computer-control-vdisplay/SKILL.md"      "$VSKILL_DIR/SKILL.md"
cp "$SCRIPT_DIR/computer-control-vdisplay/scripts/"*     "$VSKILL_DIR/scripts/"
chmod +x "$VSKILL_DIR/scripts/"*.sh
echo "  Installed to $VSKILL_DIR"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Verify the real-desktop skill with:"
echo "  wtype --help                    # text input"
echo "  hyprctl dispatch movecursor 0 0 # mouse move"
echo "  grim /tmp/test.png              # screenshot"
echo "  pamixer --get-volume            # volume"
echo ""
echo "Verify the sandbox skill with:"
echo "  ~/.claude/skills/computer-control-vdisplay/scripts/start.sh"
echo "  ~/.claude/skills/computer-control-vdisplay/scripts/status.sh"
echo "  vncviewer localhost:5999        # live view of the sandbox"
echo "  ~/.claude/skills/computer-control-vdisplay/scripts/stop.sh"
echo ""
echo "NOTE: If ydotool doesn't work, try:"
echo "  1. Re-login (for input group)"
echo '  2. export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"'
echo "  3. systemctl --user restart ydotool.service"
