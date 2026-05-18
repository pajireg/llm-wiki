#!/usr/bin/env bash
# Thin wrapper that delegates to the Python implementation.
# Allows the SessionEnd hook to be registered as a shell command in settings.json.

set -euo pipefail
exec python3 "$(dirname "$0")/session-end-capture.py"
