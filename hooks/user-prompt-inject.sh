#!/usr/bin/env bash
# Thin wrapper that delegates to the Python implementation.
# UserPromptSubmit hook — never blocks the user. Any failure → exit 0.

set +e
python3 "$(dirname "$0")/user-prompt-inject.py" || exit 0
exit 0
