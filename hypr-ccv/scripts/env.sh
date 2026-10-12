# Source from Bash; prefer `hypr-ccv exec CMD` for per-command scoping.
_ccv_scripts=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
_ccv_exports=$("$_ccv_scripts/hypr-ccv" env) || { return 1 2>/dev/null || exit 1; }
eval "$_ccv_exports"
unset _ccv_scripts _ccv_exports
