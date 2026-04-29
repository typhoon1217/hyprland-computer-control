# Hyprland Computer Control

Two [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for controlling Arch Linux desktops running Hyprland (Wayland):

1. **`computer-control`** — direct control of the user's real desktop (mouse, keyboard, windows, screenshots, volume, brightness, media, clipboard, notifications). Useful when Claude needs to act on what's already on screen.
2. **`computer-control-vdisplay`** — a *sandboxed* second Hyprland instance running as a nested floating window, sized 1920x1080, positioned just below the visible monitors. Useful when Claude needs to test/automate Hyprland behavior without disturbing the user's real screen.

## Why?

Claude Code can already run shell commands, but it doesn't know *which* commands work on Hyprland/Wayland. These skills teach it the right tools and patterns, including hard-won gotchas:

- **`ydotool mousemove --absolute` is broken on Hyprland** — use `hyprctl dispatch movecursor` instead
- **`ydotool type/key` bypasses your keymap** — use `wtype` instead (supports any layout, compose keys, input methods)
- **`ydotool` needs a socket env var** or it silently fails
- **`ydotool` is kernel-level** — even inside a nested compositor, its events go to the user's active seat (only Wayland-protocol tools like `wtype`, `grim`, `wl-copy` are properly isolated)
- **Coordinates are virtual**, not monitor-local (matters with multi-monitor setups)
- **Hyprland 0.40+ has no real headless backend** — Aquamarine forces nested-Wayland or DRM. Sandbox runs nested + floating off-screen.
- **Hidden special-workspace windows skip frame submission** — `grim` hangs on them. Floating off-screen windows render normally.

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/hyprland-computer-control.git
cd hyprland-computer-control
chmod +x setup.sh
./setup.sh
```

The setup script:
1. Installs all required packages via pacman (including `wayvnc` and `jq` for the sandbox)
2. Creates a udev rule for uinput access
3. Adds your user to the `input` group
4. Enables the ydotool daemon
5. Copies the `computer-control` skill to `~/.claude/skills/computer-control/`
6. Copies the `computer-control-vdisplay` skill to `~/.claude/skills/computer-control-vdisplay/`

## Manual Install

```bash
# Real-desktop skill dependencies
sudo pacman -S ydotool wtype grim slurp wl-clipboard libnotify playerctl brightnessctl pamixer jq

# Sandbox skill extras
sudo pacman -S wayvnc

# Copy real-desktop skill
mkdir -p ~/.claude/skills/computer-control
cp SKILL.md ~/.claude/skills/computer-control/SKILL.md

# Copy sandbox skill
mkdir -p ~/.claude/skills/computer-control-vdisplay
cp -r computer-control-vdisplay/* ~/.claude/skills/computer-control-vdisplay/

# Setup ydotool
systemctl --user enable --now ydotool.service
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo usermod -aG input $USER
# Re-login for group change to take effect
```

## What `computer-control` Can Do

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

## What `computer-control-vdisplay` Adds

A second Hyprland instance running invisibly inside the user's session. Apps launched in it never appear on the user's monitors, but they are reachable through:

- `hyprctl -i $SIG …` — full Hyprland IPC, scoped to the sandbox
- `WAYLAND_DISPLAY=$WL wtype …` — typing into the sandbox
- `WAYLAND_DISPLAY=$WL grim …` — screenshotting the sandbox
- `WAYLAND_DISPLAY=$WL wl-copy …` — sandbox-private clipboard
- VNC at `localhost:5999` for live monitoring (if `wayvnc` is installed)

### Lifecycle

After `setup.sh`, two short dispatchers are on `~/.local/bin`:

- **`hypr-cc`** — drives the user's REAL desktop (mouse / keyboard / windows / volume / brightness / media / notifications)
- **`hypr-ccv`** — drives the SANDBOX (everything fully isolated by `WAYLAND_DISPLAY` / instance signature / wayvnc)

```bash
hypr-ccv start                          # spawn sandbox (nested, floating off-screen, 1920x1080) + wayvnc
hypr-ccv status                         # PIDs, IPC reachability, VNC port
hypr-ccv stop                           # graceful shutdown + cleanup
hypr-ccv run firefox                    # launch an app inside the sandbox

hypr-ccv click 540 320                  # isolated click (via wayvnc)
hypr-ccv type 'hello'                   # isolated key input (via WAYLAND_DISPLAY)
hypr-ccv shot /tmp/v.png                # isolated screenshot
hypr-ccv hypr clients -j                # any hyprctl arg, scoped to sandbox
hypr-ccv help                           # full subcommand list
```

Real-desktop equivalents (caution — they touch the user's actual session):

```bash
hypr-cc click 540 320
hypr-cc type 'hello'
hypr-cc shot active                     # active-window screenshot
hypr-cc focus class:firefox
hypr-cc vol -i 5                        # pamixer wrapper
hypr-cc bri set +10%                    # brightnessctl wrapper
hypr-cc media play-pause                # playerctl wrapper
hypr-cc help
```

### Isolation Guarantees (verified 2026-04-29)

| Tool | Mechanism | Isolated? |
|------|-----------|-----------|
| `hyprctl -i $SIG` | Hyprland IPC (per-instance) | ✅ Complete |
| `wtype` | `virtual-keyboard-v1` (per `WAYLAND_DISPLAY`) | ✅ Complete |
| `wl-copy` / `wl-paste` | `wlr-data-control` (per `WAYLAND_DISPLAY`) | ✅ Complete |
| `grim` | `wlr-screencopy` (per `WAYLAND_DISPLAY`) | ✅ Complete |
| `cc-click.py` (RFB → wayvnc) | `zwlr_virtual_pointer_v1` via wayvnc | ✅ Complete |
| `ydotool` (click/key) | kernel `/dev/uinput` (system-wide) | ❌ NOT isolated |

**Click isolation is achieved through `cc-click.py`** — a small RFB (VNC protocol) client (Python stdlib only, ~200 LoC) that connects to the wayvnc instance `start.sh` already runs on `localhost:5999`. wayvnc forwards the pointer event through wlroots' `zwlr_virtual_pointer_v1` protocol, which is scoped to the sandbox compositor. Verified: clicking sandbox coordinate `(960, 540)` with `cc-click.py click 960 540` brings sandbox `Alacritty` to focus while the user's main `kitty (tmux)` window stays focused on the real screen.

`ydotool` cannot be confined to the sandbox because it talks to a single system-wide `ydotoold` daemon writing to `/dev/uinput`. Use `cc-click.py` for clicks and `hyprctl dispatch …` (focuswindow, exec, killactive, etc.) for window operations — both fully isolated.

## Tool Hierarchy

The skills teach Claude to pick the right tool for each job:

```
Need to type text or press keys?
  → wtype (respects keymap, no conflicts, isolated by WAYLAND_DISPLAY)

Need to move the mouse?
  → hyprctl dispatch movecursor (accurate on Hyprland, isolated)

Need to click?
  → cc-click.py click X Y (sandbox; isolated via wayvnc + virtual-pointer)
  → ydotool click          (real desktop only; system-wide, NOT isolated)

Need to manage windows / take screenshots / clipboard?
  → hyprctl dispatch / grim / wl-copy — all isolated by WAYLAND_DISPLAY
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

The sandbox is at virtual `(0, 0)` with a single 1920x1080 monitor — no offsets, no scaling.

## Browser Automation

These skills are for **desktop** control only. For browser automation, use:
- [claude-in-chrome](https://github.com/nichochar/claude-in-chrome) — Chrome extension MCP (works with your logged-in sessions)
- [Playwright MCP](https://github.com/anthropics/claude-code/tree/main/plugins/playwright) — DOM-level browser control

## Requirements

- Arch Linux (or Arch-based distro)
- Hyprland 0.40+ (Aquamarine backend)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Troubleshooting

### `computer-control`

| Problem | Fix |
|---------|-----|
| ydotool silently fails | `export YDOTOOL_SOCKET="/run/user/$(id -u)/.ydotool_socket"` |
| ydotool daemon not running | `systemctl --user restart ydotool.service` |
| Permission denied on uinput | Check udev rule + re-login for input group |
| Mouse coordinates are wrong | Use `hyprctl dispatch movecursor`, check monitor offset |
| Wrong characters when typing | Use `wtype` instead of `ydotool type` |
| Input conflicts during automation | Don't touch mouse/keyboard while Claude is clicking |

### `computer-control-vdisplay`

| Problem | Fix |
|---------|-----|
| `hyprctl -i $SIG` "couldn't connect" | Re-read `state.pid` — signature changes each start |
| Sandbox window not invisible | Check `windowrulev2 'move 0 100%+10, class:aquamarine'` is registered |
| `grim` hangs | Window is hidden; floating off-screen works, hidden workspaces don't |
| `cc-click.py` "cannot connect" | wayvnc not running — `status.sh` to confirm, restart with `CC_VNC=1` |
| `wayvnc` connection refused | Check `status.sh` — wayvnc binds 127.0.0.1 only |
| Hyprland fails to start | Try `WLR_RENDERER=pixman ~/.claude/.../start.sh` (NVIDIA quirks) |

## License

MIT
