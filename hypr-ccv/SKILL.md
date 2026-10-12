---
name: hypr-ccv
description: >
  Test native Wayland GUI flows and Hyprland configuration in an isolated
  desktop with private profiles, IPC, clipboard and D-Bus. Use for nested
  Hyprland, virtual outputs, risky display changes, GUI regression evidence
  and sandbox input. Includes verified-lesson updates after testing.
---

# Isolated GUI testing

Use the existing `hypr-ccv` controller rather than rebuilding a nested compositor, pointer client or frame recorder for each task. Requires Hyprland 0.56+ with Lua configuration. Read [verified lessons](references/lessons.md) before a test involving input, output geometry or shell lifecycle.

## Scope

This isolates GUI sessions and app profiles, not OS permissions or the filesystem. Commands still run as the user. Apps needing the real user's logins, D-Bus services or systemd user manager need a separately authorized integration design. Ordinary website work follows the installed browser policy, not this skill.

A nested Wayland window may briefly map during bootstrap. After readiness, only headless outputs remain; no host window rules, monitor config changes or host reload are used. Never describe startup as guaranteed invisible. All input uses the private Wayland socket or a private Unix VNC socket; `ydotool` is system-wide and outside this workflow.

## Run

```bash
export CC_SESSION=display-test       # optional independent session name
hypr-ccv start 1920x1080 2           # resolution, 1–4 outputs; default 1
hypr-ccv status                     # verifies PID/start time/signature/socket
hypr-ccv run quickshell -p /path/to/test-shell
hypr-ccv hypr -j clients
hypr-ccv shot /tmp/before.png
hypr-ccv click 640 400               # pixels in captured HEADLESS-1 output
hypr-ccv type 'test data'
hypr-ccv key Return
hypr-ccv keys -M ctrl -k a -m ctrl   # shortcut keys, not literal text under Ctrl
hypr-ccv shot /tmp/after.png
hypr-ccv snapshot /tmp/runtime.json
hypr-ccv record /tmp/flow.mp4 25     # 2 fps, 1–60 seconds; inspect recording
hypr-ccv stop                       # owned processes only; retains artifacts
```

Resolve paths relative to this skill's installed location when the CLI is unavailable: `scripts/hypr-ccv`. To install discoverable links without packages or privileged desktop setup, run the repository's `setup.sh --sandbox-only`.

`run` detaches and prints the app PID; `exec` waits and returns its status. Both use disposable HOME/XDG roots and a private D-Bus. Prefer `hypr-ccv exec COMMAND` over exporting its environment into your main shell. `env` remains available for a scoped subshell. `CC_VNC=0` starts keyboard/capture-only mode; pointer commands require the default `CC_VNC=1`.

## Observe → act → verify

1. Establish the target from `status` and `snapshot`. The controller discovers the compositor by its launched PID, preserves the returned `wl_socket` string and rejects missing/stale state. Its short `runtimeAlias` points only to the private runtime so Qt can reach both Unix IPC sockets; use the exported environment rather than reconstructing a long runtime path. With multiple possible parents, set `CC_PARENT_SIG` explicitly. A successful process launch is not readiness.
2. Inspect a fresh screenshot. For an app, wait for its mapped PID in `clients`; for a layer-shell popup, inspect `hypr -j layers` and the actual rendered controls. Click the observed target, then verify focus/text before typing. Choose pointer selection when tab order is unsettled.
3. After a change, wait for the specific expected UI/runtime condition within a deadline, then capture again. Recompute monitor geometry after Preview, rotation or scaling. VNC coordinates are output-local; arbitrary virtual-desktop coordinates are not interchangeable. The pointer helper rejects out-of-bounds coordinates.
4. On a failed action, stop the chain, inspect focus/geometry/logs, and change the hypothesis. After two failures of the same action, use a different verified route or report the blocker. Distinguish a CLI-driven check from a GUI-driven interaction.
5. For timed confirmation, capture before/pending/expired states and a short video; compare pending token, runtime geometry and config checksum. For Keep, verify the saved file and an explicit reload. Run real production widgets when checking bindings; fixtures must track actual dispatch state. Keep VM, physical hardware and isolated-compositor results separate.
6. Stop only the named session. `doctor` uses the same owned-session cleanup, not a global process-name scan. Keep useful artifacts and report their paths. Publish only the evidence the user requested, after inspecting it for private content.

## Maintain the skill

At completion of a nontrivial test or after an unexpected error, follow [the learning procedure](references/learning.md). The user's standing request authorizes narrow local improvements supported by verified outcomes. Keep hypotheses separate from rules. Remote publication, dependency installs and host-system changes retain their own task authorization.
