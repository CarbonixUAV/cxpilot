#!/usr/bin/env bash
#
# apply-list.sh - Interactive cherry-pick of a commit list onto cxpilot-core
#
# This script applies a list of git commits (from commits.txt) to the
# cxpilot-core repository, one by one, in reverse order (oldest first), with
# interactive conflict resolution and commit review.
#
# Usage:
#   ./apply-list.sh
#
# Requirements:
#   - commits.txt: A file in the same directory as this script, listing commit
#     hashes (and optional descriptions).
#   - cxpilot-core: The target git repository, located at ../../cxpilot-core
#     relative to this script.
#
# Features:
#   - Applies each commit from commits.txt using 'git cherry-pick -n' (no commit).
#   - On conflict, prompts user to resolve, skip, or abort.
#   - After applying, allows user to diff, edit & commit, commit with original
#     message/author, keep staged, or skip.
#   - Restores cxpilot-core to its original state on error or abort.
#
# Interactive Prompts:
#   - On conflict: [r]esume | [s]kip | [a]bort
#   - After applying: [d]iff | [e]dit & commit | [c]ommit (reuse msg/author) | [k]eep staged | [s]kip
#
# Notes:
#   - Requires a TTY for interactive prompts.
#   - Leaves cxpilot-core unchanged if aborted or on error.
#
# Author: Bob Long
# Date: 2025-08-08
#
# ---------------------------------------------------------------------------
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIST="$SCRIPT_DIR/commits.txt"
CORE_DIR="$SCRIPT_DIR/../../cxpilot-core"
START_REF=$(git -C "$CORE_DIR" rev-parse HEAD)

cleanup() {
    echo
    echo "Restoring $CORE_DIR to $START_REF"
    echo "HEAD was at $(git -C "$CORE_DIR" rev-parse HEAD)"
    git -C "$CORE_DIR" cherry-pick --abort || true
    git -C "$CORE_DIR" reset --hard "$START_REF"
    exit 1
}

# Catch Ctrl+C, termination, or any script error
trap cleanup INT TERM ERR

# open TTY for interactive prompts (fd 3)
exec 3</dev/tty || { echo "No TTY for prompts"; exit 1; }

if [ ! -f "$LIST" ]; then
  echo "Missing $LIST in $(pwd)" >&2
  exit 1
fi

if ! git -C "$CORE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "$CORE_DIR is not a git work tree" >&2
  exit 1
fi

tac "$LIST" | while IFS= read -r line || [ -n "$line" ]; do
  hash="${line%% *}"
  [ -z "$hash" ] && continue

  echo "===== $hash $(git -C "$CORE_DIR" show -s --format=%s "$hash") ====="
  git -C "$CORE_DIR" show -s --format='%H%n%an <%ae>%n%ad%n%n%B' "$hash"

  # apply without committing
  if ! git -C "$CORE_DIR" cherry-pick -n "$hash"; then
    echo "Conflict during $hash."
    while :; do
      echo "[r]esume after resolving | [s]kip (discard) | [a]bort all"
      read -u 3 -r ans
      case "$ans" in
        r|R)
          git -C "$CORE_DIR" diff --name-only --diff-filter=U | grep -q . && \
            { echo "Still unresolved."; continue; } || break
          ;;
        s|S)
          git -C "$CORE_DIR" cherry-pick --abort || git -C "$CORE_DIR" reset --hard
          continue 2
          ;;
        a|A)
          git -C "$CORE_DIR" cherry-pick --abort || true
          exit 1
          ;;
      esac
    done
  fi

  # review loop before committing
  while :; do
    echo "[d]iff | [e]dit & commit | [c]ommit (reuse msg/author) | [k]eep staged | [s]kip"
    read -u 3 -r action
    case "$action" in
      d|D) git -C "$CORE_DIR" diff --cached | ${PAGER:-less} ;;
      e|E) git -C "$CORE_DIR" commit -e ; break ;;
      c|C) git -C "$CORE_DIR" commit -C "$hash" ; break ;;
      k|K) echo "Left applied without commit."; break ;;
      s|S) git -C "$CORE_DIR" reset --hard ; break ;;
    esac
  done

done
