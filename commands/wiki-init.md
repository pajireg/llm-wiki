---
description: Bootstrap the current directory as an llm-wiki vault.
---

# /wiki-init

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

## Post-bootstrap output

Print:

```
Vault initialized at <cwd>.

Next steps (optional, recommended):

  1. Customize schema:
     - Edit schema/namespaces.md to fill in your cwd→namespace mapping.

  2. Enable Claude session auto-capture:
     - Run: bash <plugin>/scripts/install-hook.sh
     - This will guide you to register the SessionEnd hook globally.

  3. Track with git:
     - git init && git add . && git commit -m "init"
     - Add a private remote and push.

  4. Start using:
     - /wiki-ingest sources/manual/<some-note>.md
     - /wiki-ask "<your question>"
     - /wiki-lint
```

## Do not

- Initialize a non-empty directory (unless only `.git`, `.obsidian`, `.claude` exist).
- Touch existing `.git/`, `.obsidian/`, `.claude/`.
- Run `git init` automatically — user's choice.
- Register the SessionEnd hook automatically — user's choice.
