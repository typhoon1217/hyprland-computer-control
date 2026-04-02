# Hyprland Computer Control

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill for controlling Arch Linux desktops running Hyprland (Wayland).

Gives Claude direct control over your desktop — mouse, keyboard, windows, screenshots, volume, brightness, media, clipboard, and notifications — all through native Wayland tools.

## Why?

Claude Code can already run shell commands, but it doesn't know *which* commands work on Hyprland/Wayland. This skill teaches it the right tools and patterns, including hard-won gotchas:

- **`ydotool mousemove --absolute` is broken on Hyprland** — use `hyprctl dispatch movecursor` instead
- **`ydotool type/key` bypasses your keymap** — use `wtype` instead (supports any layout, compose keys, input methods)
- **`ydotool` needs a socket env var** or it silently fails
- **Coordinates are virtual**, not monitor-local (matters with multi-monitor setups)

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/hyprland-computer-control.git
cd hyprland-computer-control
chmod +x setup.sh
./setup.sh
```

The setup script:
1. Installs all required packages via pacman
2. Creates a udev rule for uinput access
3. Adds your user to the `input` group
4. Enables the ydotool daemon
5. Copies the skill to `~/.claude/skills/computer-control/`

## Manual Install

```bash
# Install dependencies
sudo pacman -S ydotool wtype grim slurp wl-clipboard libnotify playerctl brightnessctl pamixer jq

# Copy skill
mkdir -p ~/.claude/skills/computer-control
cp SKILL.md ~/.claude/skills/computer-control/SKILL.md

# Setup ydotool
systemctl --user enable --now ydotool.service
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo usermod -aG input $USER
# Re-login for group change to take effect
```

## What It Can Do

| Task | Tool Used | Input Conflicts? |
|------|-----------|-----------------|
| Type text / press keys | `wtype` | No |
| Move mouse | `hyprctl dispatch movecursor` | No |
| Click / scroll | `ydotool click` | Yes (don't touch mouse) |
| Window management | `hyprctl dispatch` | No |
| Screenshots | `grim` | No |
| Clipboard | `wl-copy` / `wl-paste` | No |
| Volume | `pamixer` | No |
| Brightness | `brightnessctl` | No |
| Media playback | `playerctl` | No |
| Notifications | `notify-send` | No |

## Tool Hierarchy

The skill teaches Claude to pick the right tool for each job:

```
Need to type text or press keys?
  → wtype (respects keymap, no conflicts)

Need to move the mouse?
  → hyprctl dispatch movecursor (accurate on Hyprland)

Need to click?
  → ydotool click (only option, warn about input conflicts)

Need to manage windows/volume/brightness?
  → Direct CLI commands (hyprctl, pamixer, brightnessctl, playerctl)
```

## GUI Automation Pattern

For tasks that need visual feedback (finding and clicking UI elements):

1. `grim /tmp/screenshot.png` — take screenshot
2. Claude reads the screenshot visually (multimodal)
3. Identifies target coordinates
4. `hyprctl dispatch movecursor X Y && sleep 0.2 && ydotool click 0xC0`
5. Screenshots again to verify

## Multi-Monitor Note

Hyprland uses a virtual coordinate space. If your monitor has an offset:

```bash
# Check your layout
hyprctl monitors -j | jq '.[] | {name, x, y, width, height}'
```

A monitor at position `x=1920` means its top-left corner is virtual coordinate `(1920, 0)`, not `(0, 0)`.

## Browser Automation

This skill is for **desktop** control only. For browser automation, use:
- [claude-in-chrome](https://github.com/nichochar/claude-in-chrome) — Chrome extension MCP (works with your logged-in sessions)
- [Playwright MCP](https://github.com/anthropics/claude-code/tree/main/plugins/playwright) — DOM-level browser control

## Requirements

- Arch Linux (or Arch-based distro)
- Hyprland (Wayland compositor)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Troubleshooting

| Problem | Fix |
|---------|-----|
| ydotool silently fails | `export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"` |
| ydotool daemon not running | `systemctl --user restart ydotool.service` |
| Permission denied on uinput | Check udev rule + re-login for input group |
| Mouse coordinates are wrong | Use `hyprctl dispatch movecursor`, check monitor offset |
| Wrong characters when typing | Use `wtype` instead of `ydotool type` |
| Input conflicts during automation | Don't touch mouse/keyboard while Claude is clicking |

## License

MIT
