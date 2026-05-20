---
name: llm-wiki
description: Operating principles and checklists for maintaining an LLM-curated wiki. Loaded by all /llm-wiki:* commands.
---

# llm-wiki: Operating Principles

Use this skill when invoked from `/llm-wiki:init`, `/llm-wiki:ingest`, `/llm-wiki:ask`, `/llm-wiki:lint`, or `/llm-wiki:upgrade-schema`.

## Always load first

Before any wiki action, read these from the current vault:

1. `schema/README.md` — constitution
2. `schema/page-types.md`
3. `schema/relations.md`
4. `schema/namespaces.md`
5. `schema/ingest-rules.md`
6. `schema/lint-rules.md`

If any are missing, abort and tell the user to run `/llm-wiki:init`.

## Hard invariants (NEVER violate)

1. Never modify files under `sources/`.
2. Never modify files under `schema/` unless this is `/llm-wiki:upgrade-schema` and the user explicitly approved a specific diff.
3. Every new wiki page MUST have non-empty `sources:` frontmatter.
4. Every page MUST have valid `type` and `namespace` per schema.
5. When making changes, preserve existing `sources:` and relation entries — append, never replace.
6. Every wiki page (excluding `source` type) MUST have a `summary` field — 1-2 sentences (~200 chars max). This is what the auto-injection hook surfaces.

## Search index

The vault keeps a SQLite FTS5 search index at `.llm-wiki/index.db` (git-ignored, derived from .md files). The auto-context-injection hook queries it on every user prompt.

- Ingest must keep the index in sync: after touching pages, call
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rebuild-index.py "<vault>" --upsert <path...>`.
- For bulk operations or initial setup, run the same script without `--upsert` for a full rebuild.
- The index can always be rebuilt from the .md files — losing it is harmless.

## Commit behavior

If the vault is a git repo (i.e., `.git/` exists at vault root):
- After ingest: commit with message `wiki: ingest <source-name> (N pages)`
- After lint with fixes (only if user explicitly asked to fix): commit with `wiki: lint fixes`
- Never push automatically. User controls remote.

If the vault is not a git repo: skip silently. No warnings.

## Working directory rule

All wiki operations run with the vault directory as cwd. Resolve the vault in this order:

1. **If cwd is a vault** (has `schema/`, `sources/`, `wiki/`) — use it as-is.
2. **Else, fall back to the registered vault** — read `~/.config/llm-wiki/vault-path`. If the file exists and points to a directory that looks like a vault, `cd` into it and continue. Tell the user once: `Using registered vault at <path>.`
3. **Else** — abort. Ask the user to run `/llm-wiki:init` (no vault registered) or `cd` to an existing vault.

This matches the SessionEnd hook: once `/llm-wiki:init` registers a vault, every `/llm-wiki:*` command works from anywhere.

## Output discipline

After any action, print a structured summary:
- What was touched (list of pages with wikilinks)
- What was created vs updated
- What was skipped and why
- Next suggested action (if any)

Never silently succeed with no output.
