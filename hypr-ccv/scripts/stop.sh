#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/cc-vdisplay"
PIDFILE="$RUNTIME_DIR/state.pid"

if [[ ! -f "$PIDFILE" ]]; then
    echo "Not running."
    exit 0
fi

declare -A pids
INSTANCE_SIG=""
SANDBOX_WL=""
while IFS='=' read -r k v; do
    [[ -z "$k" ]] && continue
    case "$k" in
        hyprland|wayvnc) pids["$k"]="$v" ;;
        hyprland_instance_signature) INSTANCE_SIG="$v" ;;
        wayland_display) SANDBOX_WL="$v" ;;
    esac
done < "$PIDFILE"

# Polite shutdown via Hyprland IPC if available
if [[ -n "$INSTANCE_SIG" ]] && command -v hyprctl >/dev/null 2>&1; then
    hyprctl -i "$INSTANCE_SIG" dispatch exit >/dev/null 2>&1 || true
fi

for key in wayvnc hyprland; do
    pid="${pids[$key]:-}"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "Stopping $key (PID $pid)..."
        kill "$pid" 2>/dev/null || true
    fi
done

sleep 0.5
for key in wayvnc hyprland; do
    pid="${pids[$key]:-}"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
done

# Capture-tool processes (slurp / hyprpicker / grim / satty) launched
# inside the sandbox don't always exit when their compositor dies — they
# reparent to PID 1 and keep waiting for input on a now-dead socket.
# This matters for the parent compositor: tools like Omarchy's
# `omarchy-cmd-screenshot` use `pkill slurp && exit 0` as a toggle gate,
# so a stale sandbox-scoped `slurp` silently swallows every screenshot
# keypress in the user's main session.
#
# Surgical cleanup: only kill processes whose WAYLAND_DISPLAY env
# matches the sandbox socket recorded in state.pid. Parent-session
# tools (which have a different WAYLAND_DISPLAY) are never touched.
if [[ -n "$SANDBOX_WL" ]]; then
    for proc_dir in /proc/[0-9]*; do
        [[ -r "$proc_dir/environ" ]] || continue
        comm="$(< "$proc_dir/comm" 2>/dev/null || true)"
        case "$comm" in
            slurp|hyprpicker|grim|satty) ;;
            *) continue ;;
        esac
        env_data="$(tr '\0' '\n' < "$proc_dir/environ" 2>/dev/null || true)"
        if [[ "$env_data" == *"WAYLAND_DISPLAY=$SANDBOX_WL"* ]]; then
            pid="${proc_dir##*/}"
            echo "Cleaning up sandbox-scoped $comm (PID $pid)"
            kill "$pid" 2>/dev/null || true
        fi
    done
fi

if [[ -n "$INSTANCE_SIG" ]]; then
    rm -rf "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypr/$INSTANCE_SIG"
fi

rm -f "$PIDFILE"

# Reload the parent's hyprland.conf so any windowrules the dynamic
# `keyword windowrule` calls in start.sh accumulated are dropped. Without
# this, every start/stop cycle leaves stale match:class ^(aquamarine)$
# rules in the parent compositor's runtime config (harmless, but
# accumulates). Reload is cheap — just re-parses the user's config file.
if command -v hyprctl >/dev/null 2>&1 && [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
    hyprctl reload >/dev/null 2>&1 || true
fi

echo "Stopped."
