---
name: llm-wiki
description: Operating principles and checklists for maintaining an LLM-curated wiki. Loaded by all /wiki-* commands.
---

# llm-wiki: Operating Principles

Use this skill when invoked from `/wiki-init`, `/wiki-ingest`, `/wiki-ask`, `/wiki-lint`, or `/wiki-upgrade-schema`.

## Always load first

Before any wiki action, read these from the current vault:

1. `schema/README.md` — constitution
2. `schema/page-types.md`
3. `schema/relations.md`
4. `schema/namespaces.md`
5. `schema/ingest-rules.md`
6. `schema/lint-rules.md`

If any are missing, abort and tell the user to run `/wiki-init`.

## Hard invariants (NEVER violate)

1. Never modify files under `sources/`.
2. Never modify files under `schema/` unless this is `/wiki-upgrade-schema` and the user explicitly approved a specific diff.
3. Every new wiki page MUST have non-empty `sources:` frontmatter.
4. Every page MUST have valid `type` and `namespace` per schema.
5. When making changes, preserve existing `sources:` and relation entries — append, never replace.

## Commit behavior

If the vault is a git repo (i.e., `.git/` exists at vault root):
- After ingest: commit with message `wiki: ingest <source-name> (N pages)`
- After lint with fixes (only if user explicitly asked to fix): commit with `wiki: lint fixes`
- Never push automatically. User controls remote.

If the vault is not a git repo: skip silently. No warnings.

## Working directory rule

All wiki operations run with the vault directory as cwd. If the cwd doesn't look like a vault (missing `schema/`, `sources/`, `wiki/`), abort and ask the user to `cd` to the vault.

## Output discipline

After any action, print a structured summary:
- What was touched (list of pages with wikilinks)
- What was created vs updated
- What was skipped and why
- Next suggested action (if any)

Never silently succeed with no output.
