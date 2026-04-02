---
name: computer-control
description: >
  Direct control of Arch Linux desktop with Hyprland. Use when the user asks to
  interact with the desktop, automate GUI tasks, click/type/move mouse, take
  screenshots, manage windows/workspaces, control media/volume/brightness,
  manage clipboard, open/close/focus applications, or any task requiring
  desktop automation. Triggers: click, type, screenshot, mouse, window, focus,
  workspace, volume, brightness, media, clipboard, open app, close app, move
  window, resize, fullscreen, notification, screen record, color pick.
---

# Computer Control Skill for Hyprland (Arch Linux)

Control the Arch Linux (Hyprland/Wayland) desktop directly through CLI tools.

## Prerequisites

Install required packages:

```bash
sudo pacman -S ydotool wtype grim slurp wl-clipboard libnotify playerctl brightnessctl pamixer jq
```

Then run the setup:

```bash
# Enable ydotool daemon
systemctl --user enable --now ydotool.service

# Ensure uinput access (persistent across reboots)
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules

# Add user to input group (takes effect after re-login)
sudo usermod -aG input $USER
```

## Tool Selection (IMPORTANT — choose the right layer)

### Text Input & Key Presses → `wtype`

Respects your Wayland keymap (any layout, compose keys, input methods).
**Always prefer over ydotool for typing/keys.**

```bash
wtype 'Hello World'                    # Type text
wtype -k Return                        # Enter
wtype -k Escape                        # Escape
wtype -k Tab                           # Tab
wtype -k BackSpace                     # Backspace
wtype -k space                         # Space
wtype -k Up / Down / Left / Right      # Arrow keys
wtype -M ctrl -k l -m ctrl            # Ctrl+L
wtype -M ctrl -k c -m ctrl            # Ctrl+C
wtype -M ctrl -k v -m ctrl            # Ctrl+V
wtype -M ctrl -k s -m ctrl            # Ctrl+S
wtype -M ctrl -k a -m ctrl            # Ctrl+A
wtype -M ctrl -k z -m ctrl            # Ctrl+Z
wtype -M alt -k F4 -m alt             # Alt+F4
wtype -M ctrl -k t -m ctrl            # Ctrl+T (new tab)
```

`wtype` uses XKB key names. `-M` = modifier down, `-m` = modifier up.

### Mouse Movement → `hyprctl dispatch movecursor`

Accurate on Hyprland. Uses virtual coordinates.

```bash
hyprctl dispatch movecursor X Y        # Move cursor (virtual coords)
hyprctl cursorpos                      # Get current position
```

**DO NOT use `ydotool mousemove --absolute`** — coordinates are broken on Hyprland.

### Mouse Clicks → `ydotool click`

```bash
export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"

ydotool click 0xC0                     # Left click
ydotool click 0xC1                     # Right click
ydotool click --repeat 2 --next-delay 50 0xC0   # Double click
ydotool mousemove --wheel -- -5        # Scroll down
ydotool mousemove --wheel -- 5         # Scroll up
```

**ALWAYS set `YDOTOOL_SOCKET` before any ydotool command.**

### Standard Click Pattern

```bash
export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"
hyprctl dispatch movecursor X Y && sleep 0.2 && ydotool click 0xC0
```

**Warning:** Mouse/click operations conflict with user's physical input. User should not touch mouse during automation.

### DO NOT use ydotool for:

- `ydotool type` — bypasses keymap, use `wtype` instead
- `ydotool key` — raw keycodes ignore your layout, use `wtype -k` instead
- `ydotool mousemove --absolute` — broken on Hyprland, use `hyprctl dispatch movecursor`

## Coordinate System

Hyprland uses a virtual coordinate space. If you have multiple monitors or an
offset, coordinates differ from monitor-local pixels.

To discover your layout:

```bash
# Get monitor positions and sizes
hyprctl monitors -j | jq '.[] | {name, x, y, width, height, scale}'
```

Example: a single monitor at offset x=0 means virtual coords = monitor pixels.
A monitor at x=1080 means virtual (1080,0) = monitor top-left corner.

`hyprctl dispatch movecursor`, `grim -g`, and `hyprctl clients -j` all use virtual coordinates.

## Window Management (hyprctl)

```bash
# List all windows
hyprctl clients -j | jq '.[] | {class, title, workspace: .workspace.id, at, size}'

# Focus a window by class
hyprctl dispatch focuswindow "class:firefox"
hyprctl dispatch focuswindow "class:chromium"
hyprctl dispatch focuswindow "class:kitty"

# Launch an application
hyprctl dispatch exec "firefox"
hyprctl dispatch exec "[float;size 800 600;center] kitty"

# Workspace control
hyprctl dispatch workspace 3
hyprctl dispatch movetoworkspace 3

# Window actions
hyprctl dispatch killactive
hyprctl dispatch fullscreen 0
hyprctl dispatch togglefloating
hyprctl dispatch movefocus l   # l/r/u/d

# Get active window info
hyprctl activewindow -j
```

## Screenshots (grim)

```bash
# Full screen
grim /tmp/screenshot.png

# Active window
grim -g "$(hyprctl activewindow -j | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')" /tmp/window.png

# Custom region (virtual coords)
grim -g "100,200 500x300" /tmp/region.png

# To clipboard
grim - | wl-copy

# Then use Read tool on the .png to see it visually
```

## Clipboard (wl-copy / wl-paste)

```bash
echo "text" | wl-copy     # Copy text
wl-copy < file.txt         # Copy file content
wl-paste                   # Read clipboard
wl-copy --clear            # Clear
```

## Volume (pamixer)

```bash
pamixer --get-volume       # Get current (0-100)
pamixer --set-volume 50    # Set to 50%
pamixer -i 5 / -d 5       # Increase/decrease by 5%
pamixer -t                 # Toggle mute
```

## Brightness (brightnessctl)

```bash
brightnessctl set 50%      # Set
brightnessctl set +10%     # Increase
brightnessctl set 10%-     # Decrease
```

## Media (playerctl)

```bash
playerctl play-pause       # Toggle play/pause
playerctl next / previous  # Track control
playerctl status           # Playing/Paused/Stopped
playerctl metadata         # Current track info
```

## Notifications (notify-send)

```bash
notify-send "Title" "Body"
notify-send -u critical "Alert" "Something important"
notify-send -t 5000 "Title" "Disappears in 5s"
```

## Visual Feedback Loop

The standard pattern for GUI automation that requires finding and clicking elements:

```bash
export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"

# 1. Screenshot
grim /tmp/screenshot.png
# 2. Read screenshot with Read tool to see current state
# 3. Identify target coordinates from the image
# 4. Move and click
hyprctl dispatch movecursor X Y && sleep 0.2 && ydotool click 0xC0
# 5. Screenshot again to verify
grim /tmp/screenshot.png
```

To zoom into a region for precision:

```bash
# Get window position
hyprctl clients -j | jq '.[] | select(.class == "firefox") | {at, size}'
# Screenshot just that region
grim -g "100,200 800x600" /tmp/zoomed.png
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| ydotool silently fails | `export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"` |
| ydotool daemon not running | `systemctl --user restart ydotool.service` |
| uinput permission denied | `sudo chmod 0666 /dev/uinput` (temp) or add udev rule |
| Mouse won't move | Use `hyprctl dispatch movecursor`, NOT `ydotool mousemove --absolute` |
| Wrong characters typed | Use `wtype`, NOT `ydotool type` or `ydotool key` |
| Input conflicts with user | Warn user not to touch mouse/keyboard during automation |
| Coordinates seem wrong | Check `hyprctl monitors -j` for virtual offset |
