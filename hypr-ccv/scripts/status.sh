#!/bin/bash
set -euo pipefail
scripts=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
exec "$scripts/hypr-ccv" status "$@"
