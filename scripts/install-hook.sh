#!/usr/bin/env bash
# Guide the user to register the SessionEnd hook globally.
# Does NOT modify ~/.claude/settings.json automatically.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_PATH="$PLUGIN_DIR/hooks/session-end-capture.sh"

cat <<EOF
=== llm-wiki: SessionEnd hook installation ===

This hook captures every Claude Code session into your vault's
sources/claude-sessions/ directory.

To enable, add the following to ~/.claude/settings.json under "hooks":

{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$HOOK_PATH"
          }
        ]
      }
    ]
  }
}

Also set this environment variable in your shell rc (e.g., ~/.zshrc):

  export LLM_WIKI_VAULT="\$HOME/Vaults/<your-vault-name>"

If LLM_WIKI_VAULT is unset, the hook does nothing — safe default.

Verify after installation:
  echo '{"session_id":"test","cwd":"'"\$(pwd)"'","transcript":"this is a smoke test transcript long enough to pass the trivial-session filter."}' | bash "$HOOK_PATH"
  ls "\$LLM_WIKI_VAULT/sources/claude-sessions/"

EOF
