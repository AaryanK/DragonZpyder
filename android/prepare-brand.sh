#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
dest=app/src/main/res/drawable-nodpi
mkdir -p "$dest"
temp=$(mktemp)
trap 'rm -f "$temp"' EXIT
curl --fail --silent --show-error --location --retry 3 'https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/76009b2b88c46ae2e9e1d0cb543345a19f2ef71c/favicon.png' -o "$temp"
test "$(git hash-object "$temp")" = 0c0c18b561ea8ed2dcfc57328d62e6bba69d247d
cp "$temp" "$dest/brand_icon.png"
