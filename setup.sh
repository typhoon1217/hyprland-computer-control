#!/bin/bash
# Link canonical checkout skills; dependency installation is explicit.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mode=${1:-all}
case "$mode" in all|--sandbox-only) ;; *) echo 'Usage: setup.sh [--sandbox-only]' >&2; exit 2 ;; esac
link() {
  local target=$1 destination=$2
  mkdir -p "$(dirname -- "$destination")"
  if [[ -L $destination ]]; then
    if [[ $(readlink -f -- "$destination") == "$target" ]]; then return; fi
    echo "Existing link preserved: $destination" >&2
    return 1
  elif [[ -e $destination ]]; then
    echo "Existing file/directory preserved: $destination" >&2
    return 1
  fi
  ln -s -- "$target" "$destination"
}
skills=(hypr-ccv)
[[ $mode == 'all' ]] && skills+=(hypr-cc)
for skill in "${skills[@]}"; do
  for registry in "$HOME/.agents/skills" "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.claude/skills"; do
    link "$repo/$skill" "$registry/$skill"
  done
  script="$repo/$skill/scripts/$skill"
  [[ $skill == 'hypr-cc' ]] && script="$repo/hypr-cc/bin/hypr-cc"
  link "$script" "$HOME/.local/bin/$skill"
done
echo 'Skills linked to this checkout. New sessions discover updated skills.'
echo 'For sandbox dependencies: hypr-ccv/scripts/install.sh (explicit package installation).'
