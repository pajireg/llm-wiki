# llm-wiki

**Public Claude Code plugin** that turns Claude sessions and manual notes into an LLM-maintained personal wiki. Inspired by [Karpathy's LLM wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Repo: `pajireg/llm-wiki` (public). Author: sumin.

## What this plugin does

- `/llm-wiki:init` — bootstrap any directory as a vault
- `/llm-wiki:ingest` — synthesize sources into wiki pages
- `/llm-wiki:ask` — query the wiki with citations
- `/llm-wiki:lint` — 8 health checks (findings-only)
- `/llm-wiki:upgrade-schema` — diff/merge schema template changes
- `hooks/hooks.json` — auto-registers a SessionEnd hook that captures every Claude session

A user's vault lives separately (private), in any directory of their choosing. This plugin repo is the public code; user vaults are content.

## Core design (do not change without reading the spec)

See `docs/superpowers/specs/2026-05-18-llm-wiki-design.md` and `docs/superpowers/plans/2026-05-18-llm-wiki.md` for full rationale.

**Three layers (Karpathy)**:
- `sources/` — immutable originals (claude-sessions/manual)
- `wiki/<namespace>/` — synthesized pages
- `schema/` — rules the LLM loads every command (user owns these)

**5 page types**: `topic`, `entity`, `note`, `source`, `question`.
**5 relations**: `related`, `part_of`, `contradicts`, `supersedes`, `derived_from`.
**5 namespaces**: `personal`, `work`, `tech`, `projects`, `people`.

**Day-1 hard rules**:
1. Sources are immutable — only `processed:` and `updated:` flags can be touched.
2. Every wiki page MUST have non-empty `sources:`.
3. Every wiki page (except `source` type) MUST have a `summary` field (1-2 sentences, used by auto-injection).
4. Frontmatter is the source of truth.
5. Schema is user-owned; the plugin NEVER auto-overwrites it.
6. Git auto-commit only if the vault is a git repo.
7. `/llm-wiki:ingest` is a sync operation when the vault has a git remote — pull before, push after. Opt-out: `LLM_WIKI_NO_SYNC=1` or `<vault>/.llm-wiki/no-sync`.

## Repository layout

```
.claude-plugin/{plugin.json, marketplace.json}   # plugin + marketplace metadata
commands/                                         # 5 slash commands (markdown)
skills/llm-wiki/SKILL.md                          # loaded by every /llm-wiki:* command
hooks/
  hooks.json                                      # SessionEnd + SubagentStop + UserPromptSubmit registration
  session-end-capture.{sh,py}                     # transcript → sources/claude-sessions/
  user-prompt-inject.{sh,py}                      # per-prompt wiki context auto-injection (v0.6.0+)
  _wiki_common.py                                 # shared utils (vault-path, namespace, frontmatter)
templates/                                        # copied into vault by /llm-wiki:init
  schema/                                         # 6-file constitution
  manual/welcome.md                               # onboarding source (user's first ingest)
  README.template.md, gitignore.template
scripts/                                          # validate-schema.py, install-hook.sh, rebuild-index.py
tests/                                            # pytest + JSONL fixtures
docs/superpowers/{specs, plans}/                  # design doc + implementation plan
```

## Critical gotchas (learned the hard way)

- **`SessionEnd` hook stdin** has `transcript_path` (path to JSONL), NOT `transcript`. Read and parse the JSONL yourself.
- **SessionEnd matcher** is ignored — don't set `matcher: "*"` in hooks.json.
- **Hook diagnostic log** — every hook invocation appends one line to `~/.cache/llm-wiki/hook.log` (timestamp, payload keys, result/skip reason). Useful when a session doesn't capture as expected, especially for non-standard launchers like `claude agents`.
- **macOS system Python is 3.9** — use `from __future__ import annotations` to keep `X | None` syntax working.
- **Plugin namespace** — slash commands invoke as `/llm-wiki:init`, `/llm-wiki:ingest`, etc. The plugin name from `plugin.json` is the mandatory prefix; command files in `commands/` use short names (no redundant `wiki-` prefix).
- **Version bump** — bump in `.claude-plugin/plugin.json` AND `.claude-plugin/marketplace.json` together. Without bumping, `/plugin marketplace update` won't replace the cache.

## Vault auto-discovery

After `/llm-wiki:init`, the active vault's absolute path is recorded at `~/.config/llm-wiki/vault-path`. The SessionEnd hook reads this on every session end. No env vars, no settings.json edits — install → init → it works.

## Search index (v0.5.0+)

Each vault has a SQLite FTS5 index at `<vault>/.llm-wiki/index.db` (git-ignored):
- Built by `scripts/rebuild-index.py <vault>` for a full rebuild.
- Updated by `scripts/rebuild-index.py <vault> --upsert <path...>` from `/llm-wiki:ingest`.
- Self-healing: corrupt DB is wiped and rebuilt on next open.
- Schema: `pages(id, path, namespace, type, title, summary, updated, mtime)` + FTS5 virtual table `pages_fts(id UNINDEXED, title, summary, body)` with `unicode61` tokenizer (handles Korean + English).
- Consumed by the UserPromptSubmit auto-injection hook (v0.6.0+).

## Auto-injection hook (v0.6.0+)

`hooks/user-prompt-inject.py` runs on every UserPromptSubmit:

1. Reads `~/.config/llm-wiki/vault-path` — silent skip if absent.
2. Checks `<vault>/.llm-wiki/disabled` and `$LLM_WIKI_AUTO_INJECT=0` (opt-out).
3. Tokenizes the prompt → FTS5 OR query (alphanumeric + 한글, dedup, max 12 tokens).
4. Searches namespace-filtered top-5; falls back to whole-vault top-5 if 0 matches.
5. Prints a `<wiki_context>` block to stdout for Claude.

**Hard invariant**: every error path exits 0 with empty stdout. The hook must never block the user's prompt. Diagnostics go to `~/.cache/llm-wiki/hook.log`.

## Namespace inference

The hook auto-extracts the `git_owner` from the cwd's `git remote origin url` (e.g. `pajireg/llm-wiki` → owner `pajireg`). Priority for namespace decision:

1. `git_owner_to_namespace` map in vault's `schema/namespaces.md`
2. `cwd_to_namespace` fallback patterns
3. `default` (typically `personal`)

The mapping starts empty so users don't need to configure anything upfront; git metadata is always recorded in frontmatter so unmapped owners can be classified later.

## Development workflow

**Tests** (pytest):
```bash
python3 -m pytest tests/ -v
```
Expected: 15 passing. Tests use brew python's pytest but the hook itself must run on Python 3.9 (system).

**Validate plugin/marketplace JSON**:
```bash
claude plugin validate .
```

**Release a new version**:
1. Bump `version` in `.claude-plugin/plugin.json` AND `.claude-plugin/marketplace.json` (semver: patch/minor/major).
2. Commit + push to `pajireg/llm-wiki` on GitHub.
3. User runs `/plugin marketplace update llm-wiki` then `/reload-plugins`.

**Semver rules**:
- patch: bugfix only
- minor: new feature, backwards-compatible
- major: breaking change to vault structure or schema

## Current version state

See `.claude-plugin/plugin.json` for the latest. Version history is in git log (search for `release:` or `feat:` commits).

## Git sync (v0.7.0+)

`/llm-wiki:ingest` runs `git pull --no-rebase` before synthesizing, then `git push` after committing. This keeps the vault in sync across machines without manual pull/push.

**Conflict resolution** (when pull has conflicts): wiki pages are merged additively (both sides); source frontmatter takes `processed: true` if either side has it; ambiguous/destructive conflicts are reported to the user without auto-resolving.

**Opt-out**: `LLM_WIKI_NO_SYNC=1` env or `<vault>/.llm-wiki/no-sync` file → local commit only, no pull/push.

**Wiki-operation sessions**: sessions where the user ran `/llm-wiki:` commands are marked `processed: true` by ingest without synthesizing. This prevents self-referential noise (e.g., an ingest session being re-ingested). Explicitly specified paths always process.

## Open items (Phase 2+ work)

- New `git_owner` discovery → interactive classification via `/llm-wiki:lint` ("this owner is unmapped — work? tech?")
- `_index.md` stubs should be schema-excepted so they don't trip lint frontmatter checks
- `<local-command-caveat>` noise filtering in transcript capture (currently preserved as command hint info)
- Pre-built binary distribution if Rust rewrite is ever considered (probably not — Python 3.9 stdlib is fine for this scale)

## When working on this repo

- Read the spec + plan in `docs/superpowers/` before changing schema, page types, or hook input/output contracts.
- Don't change the version in `plugin.json` casually — every change requires a `marketplace.json` bump too.
- The user vault lives elsewhere, in any directory of their choosing. Never reference user-specific paths here. The plugin must work regardless of vault location.
