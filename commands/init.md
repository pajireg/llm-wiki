---
description: Bootstrap the current directory as an llm-wiki vault.
---

# /llm-wiki:init

Use the `llm-wiki` skill from this plugin first (load operating principles).

## Pre-flight

1. Check cwd is empty or only contains `.git/`, `.obsidian/`, `.claude/`.
   - If it contains other files, abort: "Directory is not empty. Choose an empty directory or move existing files first."
2. Confirm with the user: "Initialize current directory `<cwd>` as a vault?"

## Bootstrap

Create directory structure (use mkdir -p):

```
sources/claude-sessions/
sources/manual/
sources/conversations/
wiki/personal/
wiki/work/
wiki/tech/
wiki/projects/
wiki/people/
lint-reports/
schema/   (populated by copy below)
```

Copy plugin templates into vault:

- Copy every file in `<plugin>/templates/schema/` → `<vault>/schema/`
- Copy `<plugin>/templates/README.template.md` → `<vault>/README.md`, replacing `{{VAULT_NAME}}` with the cwd basename.
- Copy `<plugin>/templates/gitignore.template` → `<vault>/.gitignore`

Add `_index.md` stubs:

- `<vault>/sources/_index.md` — heading only: `# Sources`
- `<vault>/wiki/_index.md` — heading only: `# Wiki`

Run validate-schema.py to verify schema/ was copied correctly:

```bash
python3 <plugin>/scripts/validate-schema.py <vault>/schema/
```

If exit code is non-zero, abort and report the issue.

Record vault path for session auto-capture:

- Create `~/.config/llm-wiki/` directory if not exists.
- Write the vault's absolute path to `~/.config/llm-wiki/vault-path`.

## Post-bootstrap output

Print:

```
Vault initialized at <cwd>.

Next steps (optional, recommended):

  1. Customize schema:
     - Edit schema/namespaces.md to fill in your cwd→namespace mapping.

  2. Track with git (optional):
     - git init && git add . && git commit -m "init"

  3. Start using:
     - /llm-wiki:ingest sources/manual/<some-note>.md
     - /llm-wiki:ask "<your question>"
     - /llm-wiki:lint

Session auto-capture is already active. Every Claude Code session will be saved to sources/claude-sessions/.
```

## Do not

- Initialize a non-empty directory (unless only `.git`, `.obsidian`, `.claude` exist).
- Touch existing `.git/`, `.obsidian/`, `.claude/`.
- Run `git init` automatically — user's choice.
