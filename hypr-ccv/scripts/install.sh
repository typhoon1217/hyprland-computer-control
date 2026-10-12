#!/bin/bash
set -euo pipefail
# No kernel-input daemon or uinput permissions are needed by the sandbox.
sudo pacman -S --needed hyprland python jq wtype grim wl-clipboard wayvnc dbus ffmpeg
