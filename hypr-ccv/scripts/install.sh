#!/usr/bin/env bash
# One-time install of the extras needed for the Hyprland sandbox.
# (Hyprland, hyprctl, wtype, grim, slurp, ydotool, wl-clipboard are required
# by the existing /hypr-cc skill and are assumed already installed.)
set -euo pipefail

PACMAN_PACKAGES=(
    wayvnc       # VNC server for a Wayland compositor
    jq           # JSON parsing for hyprctl -j output
)

echo "Installing official-repo packages via pacman..."
echo "  ${PACMAN_PACKAGES[*]}"
echo
sudo pacman -S --needed "${PACMAN_PACKAGES[@]}"

echo
echo "Tools required by the skill (verify):"
for c in Hyprland hyprctl wtype ydotool grim slurp wl-copy wayvnc jq; do
    if command -v "$c" >/dev/null 2>&1; then
        echo "  [ok]      $c"
    else
        echo "  [MISSING] $c — install before running start.sh"
    fi
done

echo
echo "Done."
echo
echo "Next:"
echo "  Start the sandbox:"
echo "    ~/.claude/skills/hypr-ccv/scripts/start.sh"
echo "  Optionally watch it (any VNC viewer):"
echo "    vncviewer localhost:5999"
