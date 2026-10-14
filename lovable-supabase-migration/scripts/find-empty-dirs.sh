#!/usr/bin/env bash
# Lists empty folders and placeholder-only folders (only .gitkeep/.keep, or files with
# nothing but whitespace, such as an empty index.ts or test file) in a target repository.
#
# Usage: find-empty-dirs.sh <repo-root>
#
# Read-only. Review each result, delete what is not required by a tool, then run again:
# removing a leaf folder can leave its parent empty.

set -euo pipefail

root="${1:?usage: find-empty-dirs.sh <repo-root>}"
skip=(-name .git -o -name node_modules -o -name dist -o -name build -o -name .next -o -name coverage)

find "$root" \( "${skip[@]}" \) -prune -o -type d -empty -print | sed 's/^/empty: /'

find "$root" \( "${skip[@]}" \) -prune -o -type d -print | while IFS= read -r dir; do
  if [ -n "$(find "$dir" -mindepth 1 -maxdepth 1 -type d -print -quit)" ]; then
    continue
  fi
  files="$(find "$dir" -mindepth 1 -maxdepth 1 -type f)"
  if [ -z "$files" ]; then
    continue
  fi
  placeholder=1
  while IFS= read -r file; do
    case "$(basename "$file")" in
      .gitkeep | .keep) continue ;;
    esac
    if grep -q '[^[:space:]]' "$file"; then
      placeholder=0
      break
    fi
  done <<< "$files"
  if [ "$placeholder" = 1 ]; then
    echo "placeholder: $dir"
  fi
done
