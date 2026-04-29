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
while IFS='=' read -r k v; do
    [[ -z "$k" ]] && continue
    case "$k" in
        hyprland|wayvnc) pids["$k"]="$v" ;;
        hyprland_instance_signature) INSTANCE_SIG="$v" ;;
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

if [[ -n "$INSTANCE_SIG" ]]; then
    rm -rf "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypr/$INSTANCE_SIG"
fi

rm -f "$PIDFILE"
echo "Stopped."
