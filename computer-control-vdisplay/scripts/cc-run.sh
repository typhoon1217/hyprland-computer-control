#!/usr/bin/env bash
# Launch a command in the Hyprland sandbox, detached.
#
#   cc-run firefox
#   cc-run chromium --ozone-platform=wayland https://example.com
#   cc-run kitty
set -euo pipefail

if [[ $# -eq 0 ]]; then
    cat <<'EOF' >&2
Usage: cc-run <command> [args...]
Runs a command in the headless Hyprland sandbox.
EOF
    exit 1
fi

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/cc-vdisplay"
PIDFILE="$RUNTIME_DIR/state.pid"
LOGDIR="$RUNTIME_DIR/logs"
mkdir -p "$LOGDIR"

if [[ ! -f "$PIDFILE" ]]; then
    echo "ERROR: sandbox not running." >&2
    echo "       Start it: ~/.claude/skills/computer-control-vdisplay/scripts/start.sh" >&2
    exit 1
fi

WL_SOCKET=""
INSTANCE_SIG=""
while IFS='=' read -r k v; do
    case "$k" in
        wayland_display) WL_SOCKET="$v" ;;
        hyprland_instance_signature) INSTANCE_SIG="$v" ;;
    esac
done < "$PIDFILE"

if [[ -z "$WL_SOCKET" ]]; then
    echo "ERROR: WAYLAND_DISPLAY not in state file (sandbox started incorrectly)." >&2
    exit 1
fi

cmd_name="$(basename "$1")"
logfile="$LOGDIR/app-${cmd_name}-$$.log"

echo "Launching '$*' on WAYLAND_DISPLAY=$WL_SOCKET"
echo "Log: $logfile"

# Common Wayland-friendly hints: MOZ_ENABLE_WAYLAND for firefox, ozone for chromium-class apps.
setsid env -u DISPLAY \
    WAYLAND_DISPLAY="$WL_SOCKET" \
    HYPRLAND_INSTANCE_SIGNATURE="$INSTANCE_SIG" \
    MOZ_ENABLE_WAYLAND=1 \
    QT_QPA_PLATFORM=wayland \
    GDK_BACKEND=wayland \
    "$@" </dev/null >"$logfile" 2>&1 &
disown
echo "PID: $!"
