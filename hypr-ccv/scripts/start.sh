#!/usr/bin/env bash
set -euo pipefail

RESOLUTION="${CC_RESOLUTION:-1920x1080}"
VNC_PORT="${CC_VNC_PORT:-5999}"
ENABLE_VNC="${CC_VNC:-1}"
# Hyprland 0.54 ignores HYPRLAND_INSTANCE_SIGNATURE from env — it auto-generates
# its own (format: <git-commit>_<unixtime>_<random>). We detect it post-start.

SKILL_DIR="$HOME/.claude/skills/hypr-ccv"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/cc-vdisplay"
LOGDIR="$RUNTIME_DIR/logs"
PIDFILE="$RUNTIME_DIR/state.pid"
mkdir -p "$LOGDIR"

if [[ -f "$PIDFILE" ]]; then
    pid="$(awk -F= '/^hyprland=/{print $2}' "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "Already running (Hyprland PID $pid). Use stop.sh first to restart."
        exit 0
    fi
    rm -f "$PIDFILE"
fi

# Snapshot existing Hyprland instance dirs so we can detect ours post-start
HYPR_BASE_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypr"
mkdir -p "$HYPR_BASE_DIR"
PRE_DIRS="$(ls "$HYPR_BASE_DIR" 2>/dev/null | sort -u)"

for cmd in Hyprland hyprctl jq wtype ydotool grim; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: '$cmd' not found. Run install.sh first." >&2
        exit 1
    fi
done

# Materialise the resolved config
RESOLVED_CONFIG="$RUNTIME_DIR/headless-resolved.conf"
sed "s|@RESOLUTION@|$RESOLUTION|g" "$SKILL_DIR/scripts/headless.conf" > "$RESOLVED_CONFIG"

echo "Starting Hyprland sandbox (headless, monitor=$RESOLUTION)..."

# Pre-register windowrules for class:aquamarine (the nested Hyprland's
# Wayland window class on the parent compositor). Doing this BEFORE the
# child appears avoids a focus-flicker frame where the user's active
# window briefly loses focus to the new child.
#
#   - float on        : floating placement (off-screen position needs float).
#   - maximize off    : block parent compositor from auto-maximising the
#                       toplevel — Aquamarine wayland clients tend to map
#                       at full monitor size otherwise.
#   - size 1920 1080  : exact virtual screen size requested by the sandbox.
#   - move 0 100%+10  : just below the active monitor's bottom edge.
#                       Frame submission still happens (floating windows
#                       are not culled), so wl_screencopy (grim/wayvnc)
#                       returns valid frames.
#   - workspace 1     : pin to ws 1 silently. ws 1 is on a visible
#                       monitor in nearly all layouts, which means the
#                       parent commits frames for it (a sandbox window on
#                       an inactive workspace gets frame-suspended → grim
#                       hangs). The 'silent' suffix avoids stealing focus.
#
# Hyprland 0.50+ ships windowrule v3 (windowrulev2 is deprecated and
# silently rejected). v3 syntax is `match:<sel> <val>, <action> <val>`.
# v3 dropped `nofullscreen`, `noinitialfocus`, `nofocus` — those are
# handled in the post-map fallback dispatch below.
if command -v hyprctl >/dev/null 2>&1; then
    hyprctl --batch "\
        keyword windowrule 'match:class ^(aquamarine)$, float on'; \
        keyword windowrule 'match:class ^(aquamarine)$, maximize off'; \
        keyword windowrule 'match:class ^(aquamarine)$, size 1920 1080'; \
        keyword windowrule 'match:class ^(aquamarine)$, move -2400 -2400'; \
        keyword windowrule 'match:class ^(aquamarine)$, workspace 1 silent'" \
        >/dev/null 2>&1 || true
fi

# Nested Wayland backend: the sandbox runs as a window inside the parent
# Hyprland compositor. WAYLAND_DISPLAY is inherited so Aquamarine's Wayland
# backend can wl_display_connect to the parent. WLR_DRM_DEVICES is unset so
# we don't accidentally try DRM.
#
# Headless was investigated and rejected for this environment: Aquamarine
# 0.10 has no dedicated headless backend (only DRM and Wayland), and the
# main session already owns the libseat seat, so DRM cannot start in the
# child either. AQ_HEADLESS_OUTPUTS only *adds* outputs to a working
# backend — it does not replace one.
setsid env -u WLR_DRM_DEVICES \
    Hyprland --config "$RESOLVED_CONFIG" \
    > "$LOGDIR/hyprland.log" 2>&1 &
HYPR_PID=$!

# Wait for the new instance dir + live socket to appear (up to 30s)
INSTANCE_SIG=""
HYPR_SOCK_DIR=""
for _ in $(seq 1 120); do
    if ! kill -0 "$HYPR_PID" 2>/dev/null; then
        echo "ERROR: Hyprland exited before opening its IPC socket." >&2
        echo "Last 60 log lines ($LOGDIR/hyprland.log):" >&2
        tail -n 60 "$LOGDIR/hyprland.log" >&2 || true
        exit 1
    fi
    POST_DIRS="$(ls "$HYPR_BASE_DIR" 2>/dev/null | sort -u)"
    NEW_SIG="$(comm -23 <(echo "$POST_DIRS") <(echo "$PRE_DIRS") | head -n1)"
    if [[ -n "$NEW_SIG" ]] && [[ -S "$HYPR_BASE_DIR/$NEW_SIG/.socket.sock" ]]; then
        INSTANCE_SIG="$NEW_SIG"
        HYPR_SOCK_DIR="$HYPR_BASE_DIR/$INSTANCE_SIG"
        break
    fi
    sleep 0.25
done

if [[ -z "$INSTANCE_SIG" ]]; then
    echo "ERROR: No new Hyprland IPC dir appeared in $HYPR_BASE_DIR after 30s." >&2
    echo "Last 60 log lines ($LOGDIR/hyprland.log):" >&2
    tail -n 60 "$LOGDIR/hyprland.log" >&2 || true
    kill "$HYPR_PID" 2>/dev/null || true
    exit 1
fi

# Resolve the wayland socket name the sandbox picked
WL_SOCKET=""
for _ in $(seq 1 25); do
    WL_SOCKET="$(hyprctl -i "$INSTANCE_SIG" instances -j 2>/dev/null \
        | jq -r --arg s "$INSTANCE_SIG" '.[] | select(.instance==$s) | .wl_socket // empty' \
        | head -n1)"
    [[ -n "$WL_SOCKET" ]] && break
    sleep 0.2
done

if [[ -z "$WL_SOCKET" ]]; then
    WL_SOCKET="$(grep -m1 -oE 'wayland-[0-9]+' "$LOGDIR/hyprland.log" || true)"
fi

VNC_PID=""
if [[ "$ENABLE_VNC" == "1" ]] && [[ -n "$WL_SOCKET" ]] && command -v wayvnc >/dev/null 2>&1; then
    echo "Starting wayvnc on localhost:$VNC_PORT..."
    setsid env WAYLAND_DISPLAY="$WL_SOCKET" \
        wayvnc 127.0.0.1 "$VNC_PORT" \
        > "$LOGDIR/wayvnc.log" 2>&1 &
    VNC_PID=$!
fi

# Post-map fallback: even with the windowrules above the parent compositor
# can map the Aquamarine toplevel as fullscreen (Aquamarine asks for
# fullscreen by default). A fullscreen window rejects setfloating /
# resizewindowpixel / movewindowpixel with "Window is fullscreen", and a
# fullscreen sandbox on an inactive workspace gets frame-suspended →
# grim hangs.
#
# Strategy: poll the parent client list for a class=aquamarine entry,
# then in one batch (a) drop fullscreen, (b) ensure floating, (c) move
# to ws 1 silently, (d) resize exact, (e) place off-screen at the
# active monitor's bottom edge.
if command -v hyprctl >/dev/null 2>&1 && [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
    SANDBOX_ADDR=""
    for _ in $(seq 1 50); do
        SANDBOX_ADDR="$(hyprctl clients -j 2>/dev/null \
            | jq -r '.[] | select(.class=="aquamarine") | .address' \
            | head -n1)"
        if [[ -n "$SANDBOX_ADDR" && "$SANDBOX_ADDR" != "null" ]]; then
            break
        fi
        sleep 0.1
    done

    if [[ -n "$SANDBOX_ADDR" && "$SANDBOX_ADDR" != "null" ]]; then
        hyprctl --batch "\
            dispatch fullscreenstate -1 0,address:$SANDBOX_ADDR; \
            dispatch setfloating address:$SANDBOX_ADDR; \
            dispatch movetoworkspacesilent 1,address:$SANDBOX_ADDR; \
            dispatch resizewindowpixel exact 1920 1080,address:$SANDBOX_ADDR; \
            dispatch movewindowpixel exact -2400 -2400,address:$SANDBOX_ADDR" \
            >/dev/null 2>&1 || true
    fi
fi

{
    echo "hyprland=$HYPR_PID"
    [[ -n "$VNC_PID" ]] && echo "wayvnc=$VNC_PID"
    echo "wayland_display=$WL_SOCKET"
    echo "hyprland_instance_signature=$INSTANCE_SIG"
    echo "vnc_port=$VNC_PORT"
    echo "resolution=$RESOLUTION"
} > "$PIDFILE"

cat <<EOF

Sandbox ready.
  Hyprland PID                  $HYPR_PID
  HYPRLAND_INSTANCE_SIGNATURE   $INSTANCE_SIG
  WAYLAND_DISPLAY               ${WL_SOCKET:-(unknown — check logs)}
  Resolution                    $RESOLUTION
EOF

if [[ -n "$VNC_PID" ]]; then
    cat <<EOF
  wayvnc                        localhost:$VNC_PORT  (PID $VNC_PID)

Watch the sandbox:
  vncviewer localhost:$VNC_PORT
EOF
fi

cat <<'EOF'

Use it (after sourcing env.sh):
  source ~/.claude/skills/hypr-ccv/scripts/env.sh
  export YDOTOOL_SOCKET=/run/user/1000/.ydotool_socket
  hyprctl monitors
  wtype 'hello'
  hyprctl dispatch movecursor 540 320 && sleep 0.2 && ydotool click 0xC0
  grim /tmp/v.png

Launch apps in the sandbox:
  ~/.claude/skills/hypr-ccv/scripts/cc-run.sh firefox

Stop:
  ~/.claude/skills/hypr-ccv/scripts/stop.sh
EOF
