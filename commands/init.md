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
- Copy `<plugin>/templates/manual/welcome.md` → `<vault>/sources/manual/welcome.md` (the onboarding source; user will ingest this first to experience the curation loop).

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

▶ 먼저 이걸 해보세요:
    /llm-wiki:ingest sources/manual/welcome.md

  (이 welcome 문서가 첫 위키 페이지로 합성되며 ingest 흐름을 체험할 수 있습니다.)

Optional:
  - schema/namespaces.md 편집 — git owner/cwd → namespace 매핑 추가
  - git init && git add . && git commit -m "init"

Session auto-capture is already active. Every Claude Code session will be saved to sources/claude-sessions/.
```

## Do not

- Initialize a non-empty directory (unless only `.git`, `.obsidian`, `.claude` exist).
- Touch existing `.git/`, `.obsidian/`, `.claude/`.
- Run `git init` automatically — user's choice.
