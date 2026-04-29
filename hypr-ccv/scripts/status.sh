#!/usr/bin/env bash
set -uo pipefail

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/cc-vdisplay"
PIDFILE="$RUNTIME_DIR/state.pid"

if [[ ! -f "$PIDFILE" ]]; then
    echo "Status: NOT RUNNING"
    exit 1
fi

echo "Status: RUNNING"
echo
while IFS='=' read -r key value; do
    [[ -z "$key" ]] && continue
    case "$key" in
        hyprland|wayvnc)
            if kill -0 "$value" 2>/dev/null; then
                printf "  %-30s %s (alive)\n" "$key" "$value"
            else
                printf "  %-30s %s (DEAD)\n" "$key" "$value"
            fi
            ;;
        wayland_display|hyprland_instance_signature|vnc_port|resolution)
            printf "  %-30s %s\n" "$key" "$value"
            ;;
    esac
done < "$PIDFILE"

# Confirm IPC reachability
INSTANCE_SIG="$(awk -F= '/^hyprland_instance_signature=/{print $2}' "$PIDFILE")"
if [[ -n "$INSTANCE_SIG" ]] && command -v hyprctl >/dev/null 2>&1; then
    echo
    if hyprctl -i "$INSTANCE_SIG" version >/dev/null 2>&1; then
        echo "  IPC                            reachable"
    else
        echo "  IPC                            UNREACHABLE"
    fi
fi
