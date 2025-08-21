#!/usr/bin/env bash
#
# rebase-todo.sh - Example script to generate a filtered list of commits for rebase
#
# This script is a quick-and-dirty hack used to generate a list of commit hashes
# and messages between two refs (bbf0b066..aef35892) in the cxpilot-core repo,
# excluding commits that only touch certain paths or files. This is how I
# selected which commits from the Carbopilot_V2 repo to bring into cxpilot-core.
#
# Notes:
#   - Not intended as a reusable tool; serves as an example of how the commit list was generated.
#   - Filters out commits that only modify files matching specific patterns (see grep -E regex).
#   - Outputs short commit hashes and messages for further processing.
#
# Author: Bob Long
# Date: 2025-08-08
#
# ---------------------------------------------------------------------------
OLD_DIR=$(pwd)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../../cxpilot-core" || exit 1


git log bbf0b066..aef35892 --pretty=format:"%h %s" --first-parent | while read short_hash message; do
    if git diff-tree --no-commit-id --name-only -r "$short_hash" | grep -Eqv '^(libraries/AP_HAL_ChibiOS/hwdef/|Tools/Carbonix_scripts|.github/workflows/carbonix.*|.github/workflows/cx.*|Tools/autotest/carbonix.py|ArduPlane/ReleaseNotes.txt)'; then
        echo "$short_hash $message"
    fi
done

cd "$OLD_DIR" || exit 1