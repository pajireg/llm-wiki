---
description: Bootstrap the current directory as an llm-wiki vault (or register a cloned vault as the active one).
---

# /llm-wiki:init

Use the `llm-wiki` skill from this plugin first (load operating principles).

## Pre-flight: classify the cwd

Inspect the current working directory and pick exactly one branch:

- **Existing vault** — cwd contains all three: `schema/`, `sources/`, `wiki/` directories. Treat as a cloned or pre-existing vault. Go to **Register**.
- **Empty** — cwd is empty or contains only `.git/`, `.obsidian/`, `.claude/`. Go to **Bootstrap**.
- **Non-empty, non-vault** — anything else. Abort: "Directory is not empty and is not an existing vault (missing one of: schema/, sources/, wiki/). Choose an empty directory, move existing files first, or restore the missing vault subdirectories."

## Register (existing vault)

1. Run `python3 <plugin>/scripts/validate-schema.py <vault>/schema/` to verify the vault's schema is intact. If non-zero, report which files are missing and offer to copy from `<plugin>/templates/schema/` to repair.
2. Confirm with the user: "Register existing vault at `<cwd>` as the active vault? (This switches session auto-capture to write here.)"
3. On yes:
   - Create `~/.config/llm-wiki/` directory if not exists.
   - Write the vault's absolute path to `~/.config/llm-wiki/vault-path`.
4. Print:
   ```
   Registered existing vault at <cwd>.
   Session auto-capture now targets this vault.

   Previous vault-path (if any) is overwritten. Sources already in this vault are preserved.
   ```
5. Done. Do NOT run the Bootstrap steps.

## Bootstrap (empty directory)

1. Confirm with the user: "Initialize current directory `<cwd>` as a new vault?"

2. Create directory structure (use mkdir -p):

   ```
   sources/claude-sessions/
   sources/manual/
   wiki/personal/
   wiki/work/
   wiki/tech/
   wiki/projects/
   wiki/people/
   lint-reports/
   schema/   (populated by copy below)
   ```

3. Copy plugin templates into vault:

   - Copy every file in `<plugin>/templates/schema/` → `<vault>/schema/`
   - Copy `<plugin>/templates/README.template.md` → `<vault>/README.md`, replacing `{{VAULT_NAME}}` with the cwd basename.
   - Copy `<plugin>/templates/gitignore.template` → `<vault>/.gitignore`
   - Copy `<plugin>/templates/manual/welcome.md` → `<vault>/sources/manual/welcome.md` (the onboarding source; user will ingest this first to experience the curation loop).

4. Add `_index.md` stubs:

   - `<vault>/sources/_index.md` — heading only: `# Sources`
   - `<vault>/wiki/_index.md` — heading only: `# Wiki`

5. Run validate-schema.py:

   ```bash
   python3 <plugin>/scripts/validate-schema.py <vault>/schema/
   ```

   If exit code is non-zero, abort and report the issue.

6. Record vault path for session auto-capture:

   - Create `~/.config/llm-wiki/` directory if not exists.
   - Write the vault's absolute path to `~/.config/llm-wiki/vault-path`.

7. Print:

   ```
   Vault initialized at <cwd>.

   ▶ Try this first:
       /llm-wiki:ingest

     (With no args, ingest processes every unprocessed source. On a fresh
      vault that's just the welcome doc — a one-command tour of the loop.)

   Optional:
     - Edit schema/namespaces.md to add your git_owner / cwd → namespace mappings.
     - git init && git add . && git commit -m "init"

   Session auto-capture is already active. Every Claude Code session will be saved to sources/claude-sessions/.
   ```

## Do not

- Bootstrap a non-empty directory that isn't an existing vault.
- Touch existing `.git/`, `.obsidian/`, `.claude/`.
- Run `git init` automatically — user's choice.
- Modify any file inside an existing vault during Register (only write `~/.config/llm-wiki/vault-path`).
