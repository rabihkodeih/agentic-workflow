#!/usr/bin/env bash
# clone-ws.sh <src-workspace> <new-workspace>: copy a workspace without its git history, then start a fresh repo.
# Honours <src>/.cloneignore (rsync filter rules) and overlays <src>/.clone/* stubs ({{NAME}}, {{SOURCE}}, {{DATE}} filled in).
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: clone-ws.sh <src-workspace> <new-workspace>" >&2
  exit 1
fi

src="${1%/}"
dst="${2%/}"

[ -d "$src" ] || { echo "clone-ws: '$src' is not a directory" >&2; exit 1; }
[ -e "$dst" ] && { echo "clone-ws: '$dst' already exists" >&2; exit 1; }

src_abs="$(cd "$src" && pwd)"
filters=(--exclude='/.git')
[ -f "$src_abs/.cloneignore" ] && filters=(--filter="merge $src_abs/.cloneignore" "${filters[@]}")

rsync -a "${filters[@]}" "$src_abs/" "$dst/"

if [ -d "$src_abs/.clone" ]; then
  name="$(basename "$dst")"
  today="$(date +%F)"
  (cd "$src_abs/.clone" && find . -type f) | while read -r f; do
    mkdir -p "$dst/$(dirname "$f")"
    sed -e "s|{{NAME}}|$name|g" -e "s|{{SOURCE}}|$src_abs|g" -e "s|{{DATE}}|$today|g" \
      "$src_abs/.clone/$f" > "$dst/$f"
  done
fi

cd "$dst"
git init -q
git add -A
git commit -q -m "initial commit"
echo "clone-ws: $src -> $dst ($(git rev-parse --short HEAD))"
