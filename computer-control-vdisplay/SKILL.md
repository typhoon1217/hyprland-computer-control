---
name: computer-control-vdisplay
description: >
  Run a sandboxed second Hyprland instance as a nested floating window inside
  the user's existing session, sized 1920x1080 and positioned just below the
  visible monitors so the user's screen is undisturbed. Drive it with the same
  Wayland tooling (hyprctl, wtype, grim, wl-copy) — all of which scope by
  WAYLAND_DISPLAY / HYPRLAND_INSTANCE_SIGNATURE, so input cannot leak into the
  main session. Use when the user wants to test or automate Hyprland behavior
  — keybindings, dispatchers, window rules, configs, Wayland app GUI flow —
  in isolation. Triggers: Hyprland sandbox, nested Hyprland, virtual display,
  second Hyprland instance, isolated Hyprland, test Hyprland config, sandbox
  automation, "don't take over my screen", parallel Hyprland.
---

# Computer Control: Hyprland Sandbox

Runs a *second* Hyprland instance as a **nested floating Wayland window**
inside the user's existing session. The user's main Hyprland is untouched;
the sandbox lives on its own `WAYLAND_DISPLAY` (e.g. `wayland-2`) with its
own auto-generated `HYPRLAND_INSTANCE_SIGNATURE`. Same Wayland tooling as
the real session (`hyprctl`, `wtype`, `grim`, etc.), just targeted at the
sandbox.

## Architecture: nested + floating off-screen (verified working)

```
Real session                                  Visible monitors
  HYPRLAND_INSTANCE_SIGNATURE=<original>        DP-8 (0..1920, y=240..1320)
  Hyprland 0.54.x  ← user keeps working         DP-7 (1080..3000, y=0..1080)
  ─────────────────────────────────────────     eDP-2 (1080..3000, y=1080..2160)
                                                ─────────────────────────────
   ┌── sandbox window (class=aquamarine) ──┐    Below visible area:
   │ floating, 1920x1080                   │    y = 100% + 10 px
   │ HYPRLAND_INSTANCE_SIGNATURE=          │    (off-screen, but the parent
   │   <git>_<unixtime>_<random>           │    compositor still submits
   │ WAYLAND_DISPLAY=wayland-N             │    frames → grim works)
   │  ├── wayvnc → localhost:5999          │
   │  └── apps via cc-run firefox          │
   └────────────────────────────────────────┘
```

**Why nested + floating off-screen, not headless or special-workspace:**

- **Headless impossible:** Hyprland 0.54.3 / Aquamarine 0.10 has no
  dedicated headless backend (only DRM and Wayland). DRM cannot start in a
  child because the main session owns the libseat seat
  (`Device or resource busy`). `AQ_HEADLESS_OUTPUTS=1` only adds outputs to
  a working backend; it doesn't replace one. `AQ_DRM_DEVICES=/dev/null`
  makes both backends fail (`no allocator`).
- **Special workspace + fullscreen breaks `grim`:** Frame submission is
  suspended for windows on hidden special workspaces. `wl_screencopy`
  clients (grim) block forever waiting for a frame. wayvnc with persistent
  capture sometimes works; single-frame `grim` never does.
- **Floating off-screen works:** Floating windows are always rendered
  regardless of position. The parent compositor submits frames, screencopy
  succeeds, `grim` returns a valid 1920x1080 PNG. The user's monitors do
  not show the sandbox because it sits at `y = 100%+10` (just past the
  bottom edge).

## When to use this skill vs `computer-control`

| Situation | Skill |
|-----------|-------|
| Test Hyprland configs/keybinds without breaking the real session | **vdisplay** |
| Long-running Wayland app automation | **vdisplay** |
| Try a config change that might be unstable | **vdisplay** |
| Interact with what is *already on the user's screen* | `computer-control` |
| Quick action on the real workspace | `computer-control` |

The two share no Wayland state. Apps in the sandbox are invisible on the
real screen, and the sandbox does not source `~/.config/hypr/hyprland.conf`.

## One-time setup

```bash
~/.claude/skills/computer-control-vdisplay/scripts/install.sh
```

Installs `wayvnc` and `jq` from official repos. The other required tools
(Hyprland, hyprctl, wtype, ydotool, grim, slurp, wl-clipboard) are the same
ones the existing `/computer-control` skill uses on this machine and are
assumed already installed.

## Lifecycle (short commands — preferred)

After `setup.sh`, the dispatcher `hypr-ccv` is on `~/.local/bin`. Everything below routes to the underlying scripts but is much shorter to type:

```bash
hypr-ccv start                 # spawn nested Hyprland, floating off-screen, + wayvnc
hypr-ccv status                # processes + IPC reachability
hypr-ccv stop                  # polite hyprctl exit + clean up
hypr-ccv help                  # full subcommand list
```

The long-form scripts still work and are equivalent:

```bash
~/.claude/skills/computer-control-vdisplay/scripts/start.sh
~/.claude/skills/computer-control-vdisplay/scripts/status.sh
~/.claude/skills/computer-control-vdisplay/scripts/stop.sh
```

Tunables (env vars, set before `start.sh`):

| var | default | meaning |
|-----|---------|---------|
| `CC_RESOLUTION` | `1920x1080` | virtual monitor size hint |
| `CC_VNC` | `1` | start wayvnc for monitoring |
| `CC_VNC_PORT` | `5999` | VNC port (localhost only) |

State at `$XDG_RUNTIME_DIR/cc-vdisplay/state.pid` (key=value lines).
The sandbox's auto-generated `HYPRLAND_INSTANCE_SIGNATURE` and
`WAYLAND_DISPLAY` are recorded there post-launch.

> Hyprland 0.54 ignores `HYPRLAND_INSTANCE_SIGNATURE` from env and generates
> its own (`<git-commit>_<unixtime>_<random>`). `start.sh` snapshots
> `$XDG_RUNTIME_DIR/hypr/` before/after launch and detects the new signature
> via `comm -23`.

## Quick reference (`hypr-ccv` cheat sheet)

```bash
hypr-ccv start                          # spawn / stop / status
hypr-ccv stop
hypr-ccv status

hypr-ccv run firefox                    # launch app inside sandbox
hypr-ccv run alacritty
hypr-ccv run chromium --ozone-platform=wayland https://example.com

hypr-ccv click 540 320                  # left click (isolated via wayvnc)
hypr-ccv click 540 320 --button right
hypr-ccv dblclick 540 320
hypr-ccv move 540 320                   # pointer move only
hypr-ccv scroll 540 320 -3              # scroll down 3 ticks
hypr-ccv drag 100 200 400 500           # smooth click-drag

hypr-ccv type 'Hello'                   # wtype (isolated)
hypr-ccv key Return
hypr-ccv key Escape
hypr-ccv key Tab

hypr-ccv shot /tmp/v.png                # grim (isolated)
hypr-ccv copy 'text'                    # wl-copy (isolated)
hypr-ccv paste                          # wl-paste

hypr-ccv hypr clients -j                # any hyprctl arg, -i SIG injected
hypr-ccv focus class:firefox            # dispatch focuswindow
hypr-ccv spawn firefox                  # dispatch exec
hypr-ccv cursor 540 320                 # dispatch movecursor

hypr-ccv vnc                            # → "localhost:5999"
hypr-ccv sig                            # current HYPRLAND_INSTANCE_SIGNATURE
hypr-ccv wl                             # current WAYLAND_DISPLAY
eval "$(hypr-ccv env)"                  # export both into current shell
```

**`hypr-cc`** is the equivalent dispatcher for the user's REAL desktop (no isolation):

```bash
hypr-cc click 540 320                   # ydotool click on real screen
hypr-cc type 'Hello'
hypr-cc shot active                     # active-window screenshot
hypr-cc focus class:firefox
hypr-cc vol --get-volume / -i 5 / -t    # pamixer
hypr-cc bri set +10%                    # brightnessctl
hypr-cc media play-pause                # playerctl
hypr-cc notify "Title" "Body"
```

The full prose docs below explain *why* and the underlying mechanisms; the cheat sheet above is the fast path.

## Targeting the sandbox (long form)

The sandbox needs **two** env vars set on every command:

| var | for what |
|-----|----------|
| `WAYLAND_DISPLAY` | apps and Wayland-protocol tools (`wtype`, `grim`, `wl-copy`) |
| `HYPRLAND_INSTANCE_SIGNATURE` | `hyprctl` IPC routing (or use `hyprctl -i $SIG`) |

Two patterns:

**Per-command** (Bash tool default — recommended):
```bash
SIG=$(awk -F= '/^hyprland_instance_signature=/{print $2}' "$XDG_RUNTIME_DIR/cc-vdisplay/state.pid")
WL=$(awk -F= '/^wayland_display=/{print $2}'             "$XDG_RUNTIME_DIR/cc-vdisplay/state.pid")

hyprctl -i "$SIG" monitors
WAYLAND_DISPLAY="$WL" wtype 'hello'
WAYLAND_DISPLAY="$WL" grim /tmp/v.png
```

**Session** (chain commands in one Bash call):
```bash
source ~/.claude/skills/computer-control-vdisplay/scripts/env.sh && \
  hyprctl monitors && \
  wtype 'hello' && \
  grim /tmp/v.png
```

`env.sh` reads `state.pid` and exports both `WAYLAND_DISPLAY` and
`HYPRLAND_INSTANCE_SIGNATURE`, then unsets `DISPLAY` so X11 apps cannot
leak to the real `:0`/`:1`.

## Isolation guarantees (verified 2026-04-29)

| Tool | Mechanism | Isolation |
|------|-----------|-----------|
| `hyprctl -i $SIG` | Hyprland IPC (per-instance socket) | ✅ **complete** |
| `wtype` | `virtual-keyboard-v1` (per `WAYLAND_DISPLAY`) | ✅ **complete** |
| `wl-copy` / `wl-paste` | `wlr-data-control` (per `WAYLAND_DISPLAY`) | ✅ **complete** |
| `grim` | `wlr-screencopy` (per `WAYLAND_DISPLAY`) | ✅ **complete** |
| `cc-click.py` (RFB → wayvnc) | `zwlr_virtual_pointer_v1` via wayvnc | ✅ **complete** |
| `ydotool` (click/key) | kernel `/dev/uinput` (system-wide single seat) | ❌ **NOT isolated** |

**Click isolation is achieved through `cc-click.py`**, a small RFB
(VNC protocol) client that connects to the already-running `wayvnc`
on `localhost:5999`. wayvnc receives the pointer event and forwards it
through wlroots' `zwlr_virtual_pointer_v1` protocol — which is scoped
to the sandbox compositor. The user's main seat is never touched.

`ydotool` cannot be confined to the sandbox because it talks to a
single system-wide `ydotoold` daemon that writes to `/dev/uinput`,
which creates a virtual input device on the user's only seat. The
injected event lands on whichever window the seat currently focuses —
which can be the user's real session if focus flips at the wrong
moment. **Use `cc-click.py` instead, or drive the sandbox over wayvnc
from a real VNC client.**

## Window management — `hyprctl -i $SIG`

```bash
hyprctl -i "$SIG" monitors                                  # virtual monitor info
hyprctl -i "$SIG" clients -j | jq '.[] | {class,title,workspace:.workspace.id,at,size}'
hyprctl -i "$SIG" activewindow -j
hyprctl -i "$SIG" dispatch exec "kitty"
hyprctl -i "$SIG" dispatch focuswindow "class:firefox"
hyprctl -i "$SIG" dispatch workspace 3
hyprctl -i "$SIG" dispatch movetoworkspace 3
hyprctl -i "$SIG" dispatch killactive
hyprctl -i "$SIG" dispatch fullscreen 0
hyprctl -i "$SIG" dispatch togglefloating
hyprctl -i "$SIG" dispatch movecursor 540 320
hyprctl -i "$SIG" cursorpos
```

## Launching applications

```bash
SCRIPTS=~/.claude/skills/computer-control-vdisplay/scripts

$SCRIPTS/cc-run.sh firefox
$SCRIPTS/cc-run.sh chromium --ozone-platform=wayland https://example.com
$SCRIPTS/cc-run.sh kitty
$SCRIPTS/cc-run.sh alacritty
```

`cc-run.sh` exports `WAYLAND_DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE`,
`MOZ_ENABLE_WAYLAND=1`, `QT_QPA_PLATFORM=wayland`, `GDK_BACKEND=wayland`,
unsets `DISPLAY`, and detaches via `setsid`. Logs land at
`$XDG_RUNTIME_DIR/cc-vdisplay/logs/app-<name>-<pid>.log`.

## Keyboard / text — `wtype` (isolated)

`wtype` uses `virtual-keyboard-v1`, which is scoped to `WAYLAND_DISPLAY`.
The keys land in whatever window has keyboard focus *inside the sandbox*.
Nothing leaks to the user's session.

```bash
WAYLAND_DISPLAY="$WL" wtype 'Hello World'
WAYLAND_DISPLAY="$WL" wtype -k Return
WAYLAND_DISPLAY="$WL" wtype -k Escape
WAYLAND_DISPLAY="$WL" wtype -k Tab
WAYLAND_DISPLAY="$WL" wtype -k BackSpace
WAYLAND_DISPLAY="$WL" wtype -k space
WAYLAND_DISPLAY="$WL" wtype -k Up -k Down -k Left -k Right
WAYLAND_DISPLAY="$WL" wtype -M ctrl -k l -m ctrl                # Ctrl+L
WAYLAND_DISPLAY="$WL" wtype -M ctrl -k c -m ctrl                # Ctrl+C
WAYLAND_DISPLAY="$WL" wtype -M ctrl -M shift -k t -m shift -m ctrl  # Ctrl+Shift+T
```

`-M` = modifier down, `-m` = modifier up. Key names follow XKB
(`Return`, `Escape`, `Tab`, `BackSpace`, `space`, `F1`–`F12`, `Page_Up`,
`Page_Down`, `Home`, `End`, etc.).

## Screenshots — `grim` (isolated, works because window is floating)

```bash
WAYLAND_DISPLAY="$WL" grim /tmp/full.png
WAYLAND_DISPLAY="$WL" grim -g "100,100 800x600" /tmp/region.png
```

For "active window" geometry:
```bash
WAYLAND_DISPLAY="$WL" grim -g "$(hyprctl -i "$SIG" activewindow -j \
    | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')" /tmp/active.png
```

After capturing, **use the Read tool** on the .png to inspect the sandbox
state visually before deciding next coordinates.

## Clipboard — `wl-copy` / `wl-paste` (isolated)

Each Wayland session has its own clipboard. Verified: writing with
`WAYLAND_DISPLAY=$WL wl-copy` does *not* change the user's main clipboard.

```bash
echo "text" | WAYLAND_DISPLAY="$WL" wl-copy
WAYLAND_DISPLAY="$WL" wl-paste
```

## Mouse clicks — `cc-click.py` (isolated, recommended)

`cc-click.py` is the primary click tool. It speaks RFB (VNC protocol) to
the wayvnc instance that `start.sh` already runs on `localhost:5999`.
wayvnc forwards the event through wlroots' `zwlr_virtual_pointer_v1`,
which is scoped to the sandbox — the user's seat never sees it.

```bash
SCRIPTS=~/.claude/skills/computer-control-vdisplay/scripts

$SCRIPTS/cc-click.py click 555 333                  # left click
$SCRIPTS/cc-click.py click 555 333 --button right   # right click
$SCRIPTS/cc-click.py click 555 333 --button middle  # middle click
$SCRIPTS/cc-click.py double 555 333                 # double click
$SCRIPTS/cc-click.py move 100 200                   # move only
$SCRIPTS/cc-click.py scroll 555 333 -3              # scroll down 3 ticks
$SCRIPTS/cc-click.py scroll 555 333  5              # scroll up 5 ticks
$SCRIPTS/cc-click.py drag 100 200 400 500           # drag with smooth path
```

Coordinates are in the sandbox's virtual screen (1920x1080 at origin).
No external dependencies — Python stdlib only. Each call opens a fresh
RFB session, so it adds ~5–10ms per click, which is fine for automation.

For absolute cursor positioning without clicking, prefer
`hyprctl -i $SIG dispatch movecursor X Y` — it goes through Hyprland IPC
directly and doesn't depend on wayvnc.

### Standard click pattern

```bash
SCRIPTS=~/.claude/skills/computer-control-vdisplay/scripts

# Position via Hyprland IPC, click via cc-click — both isolated.
hyprctl -i "$SIG" dispatch movecursor 540 320
$SCRIPTS/cc-click.py click 540 320
```

### Why not `ydotool`?

`ydotool` writes to `/dev/uinput` via a single system-wide daemon. It
ignores `WAYLAND_DISPLAY` and lands on whichever window the user's seat
focuses. To use it against the sandbox, the user's main compositor would
have to focus the `class:aquamarine` window first — which requires
overriding the `nofocus` / `noinitialfocus` rules and accepting that
keyboard typing will go to the sandbox during the click. **Use
`cc-click.py` instead** unless you have a specific need for `ydotool`.

If you must, `ydotool mousemove --absolute` is still broken on Hyprland
(same gotcha as the main skill); use `hyprctl -i $SIG dispatch movecursor`
for absolute moves.

### Alternative: `vncdotool` (extra repo)

Equivalent functionality, but adds a Python package dependency:

```bash
sudo pacman -S vncdotool
vncdo -s localhost::5999 click 1 -- 540 320
vncdo -s localhost::5999 type 'hello'      # also works for text input
```

`cc-click.py` is preferred because it has zero dependencies and ships
with the skill, but `vncdotool` is fine if it's already installed.

## Visual feedback loop

```bash
SCRIPTS=~/.claude/skills/computer-control-vdisplay/scripts
source $SCRIPTS/env.sh

# 1. snapshot
grim /tmp/v.png
# 2. Read /tmp/v.png with the Read tool to see UI state
# 3. compute coords
# 4. act — all paths fully isolated from the user's session
hyprctl dispatch movecursor 540 320
$SCRIPTS/cc-click.py click 540 320
hyprctl dispatch focuswindow "class:firefox"
wtype 'search query'
# 5. verify
grim /tmp/v2.png
```

## Live monitoring

When `CC_VNC=1` (default), `wayvnc` exposes the sandbox at `localhost:5999`:

```bash
vncviewer localhost:5999
remmina vnc://localhost:5999
```

`wayvnc` binds `127.0.0.1` only — never reachable from the network.

## Coordinate system

The sandbox has a **single** virtual monitor at origin (0, 0), default
1920×1080. No multi-monitor offset, no fractional scaling. Unlike the
user's real eDP-2 (which sits at virtual `x=1080`), the sandbox starts at
(0, 0). `hyprctl -i $SIG dispatch movecursor 0 0` lands at the top-left
of the sandbox, never on a real monitor.

## Safety / scope

- VNC and Hyprland IPC are localhost-only.
- The sandbox uses a separate `HYPRLAND_INSTANCE_SIGNATURE`. Accidental
  `hyprctl` (without `-i $SIG`) targets the user's real session, not the
  sandbox — the conservative default.
- The sandbox does **not** source `~/.config/hypr/hyprland.conf`; it runs
  the minimal config at `scripts/headless.conf`. Test config snippets
  explicitly.
- The sandbox window is positioned *just below* the bottom monitor edge.
  On extreme negative-y panel layouts you may see a 1–2 px sliver — bump
  the `move 0 100%+10` rule to a larger offset if so.

## Troubleshooting

- **`hyprctl -i $SIG monitors` fails with "couldn't connect"** — sandbox
  not running, or you copied the signature from a previous run. Re-read
  `state.pid` (the signature changes every start). `status.sh` to confirm.
- **Hyprland did not start (no IPC socket)** — check
  `$XDG_RUNTIME_DIR/cc-vdisplay/logs/hyprland.log`. Common causes: NVIDIA
  module quirks (try `WLR_RENDERER=pixman` env override before
  `start.sh`).
- **`grim` hangs forever** — the sandbox window was made hidden somehow.
  Floating off-screen works; hidden special workspaces do not.
  `hyprctl -i $SIG clients -j | jq '.[] | {hidden, mapped}'` should show
  `mapped:true, hidden:false`.
- **`wayvnc` connection refused** — run `status.sh`; wayvnc only binds
  `127.0.0.1`.
- **`wtype` / `wl-copy` errors with "couldn't connect"** —
  `WAYLAND_DISPLAY` not exported. `source env.sh` first or set inline.
- **`ydotool` clicks don't land on sandbox** — *expected*; the sandbox
  window doesn't hold seat focus by default. Either
  `hyprctl dispatch focuswindow "class:aquamarine"` first, or drive via
  VNC.
- **Apps appear empty/black in screenshots** — Hyprland may not have
  raised the window. Try `hyprctl -i $SIG dispatch focuswindow "class:<X>"`.
- **GPU contention / NVIDIA crashes** — set `CC_RESOLUTION=1280x720` and
  prepend `WLR_RENDERER=pixman` to start.sh:
  `WLR_RENDERER=pixman ~/.claude/.../start.sh`.

## Files

```
~/.claude/skills/computer-control-vdisplay/
├── SKILL.md
└── scripts/
    ├── install.sh             # one-time pacman install (wayvnc, jq)
    ├── headless.conf          # minimal Hyprland config (templated)
    ├── start.sh               # boot nested Hyprland + wayvnc, place floating off-screen
    ├── stop.sh                # graceful hyprctl exit + cleanup
    ├── status.sh              # processes + IPC reachability
    ├── env.sh                 # source: export WAYLAND_DISPLAY + HYPRLAND_INSTANCE_SIGNATURE
    ├── cc-run.sh              # cc-run firefox  (launch app in sandbox)
    └── cc-click.py            # isolated mouse input via wayvnc (RFB protocol)
```
