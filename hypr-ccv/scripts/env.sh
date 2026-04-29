# Source this file:
#   source ~/.claude/skills/hypr-ccv/scripts/env.sh
#
# Reads the current sandbox state and exports:
#   WAYLAND_DISPLAY              — the headless Hyprland's wayland socket
#   HYPRLAND_INSTANCE_SIGNATURE  — used by hyprctl to target the sandbox
#   DISPLAY is unset so X11 apps don't fall back to the user's :0/:1.

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/cc-vdisplay"
PIDFILE="$RUNTIME_DIR/state.pid"

if [[ ! -f "$PIDFILE" ]]; then
    echo "Sandbox not running. Start it first:" >&2
    echo "  ~/.claude/skills/hypr-ccv/scripts/start.sh" >&2
    return 1 2>/dev/null || exit 1
fi

while IFS='=' read -r k v; do
    case "$k" in
        wayland_display)              [[ -n "$v" ]] && export WAYLAND_DISPLAY="$v" ;;
        hyprland_instance_signature)  [[ -n "$v" ]] && export HYPRLAND_INSTANCE_SIGNATURE="$v" ;;
    esac
done < "$PIDFILE"

unset DISPLAY
