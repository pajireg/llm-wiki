---
description: Synthesize a source (or batch of recent sources) into the wiki.
---

# /llm-wiki:ingest [source-path | --recent <duration>]

Use the `llm-wiki` skill from this plugin first (load schema and invariants).

## Argument parsing

- No args → ingest all `sources/**/*.md` with `processed: false`.
- A single file path → ingest just that file.
- `--recent 1d` / `--recent 7d` → ingest unprocessed sources whose `ingested_at` is within the duration.

## Git sync — pull first (if git repo + remote)

Before processing any source, run `git pull --no-rebase`. If pull has conflicts:
- *Wiki pages*: merge both sides (additive), `git add`.
- *Sources*: take `processed: true` if either side has it; body is immutable, pick either. `git add`.
- *Ambiguous/destructive conflicts*: stop and report to the user.
- After resolving: `git commit` to complete the merge.

Skip pull/push if `LLM_WIKI_NO_SYNC=1` env or `<vault>/.llm-wiki/no-sync` file exists.

## Per-source procedure (follow `schema/ingest-rules.md`)

For each target source:

1. **Read source** — full content + frontmatter. Note `namespace`.

   **Wiki-operation check**: if the source is purely a record of running `/llm-wiki:` commands (ingest/lint/init/etc.) with no new substantive knowledge, mark `processed: true` and skip synthesis. If it also contains substantive discussion, synthesize only that part.

2. **Identify candidates** — search the wiki:
   - Grep `wiki/<namespace>/` for keywords from source title + body (top 20 terms by TF).
   - Check aliases in topic/entity frontmatter.
   - Read top 5-10 candidate pages.

3. **Classify what's needed**:
   - Existing topic to update? Which?
   - New topic to create?
   - Note that's too raw to synthesize?
   - Question raised by source?
   - Entity (person/tool/company) first mention?

4. **Apply changes**:
   - **Update existing**: append new section or paragraph. Add `sources: [[<this-source>]]` to frontmatter (deduplicated). Update `updated:`.
   - **Create new**: full frontmatter per `page-types.md`. Filename per type. Non-empty `sources:` with this source.
   - **Relations**: when this change connects two pages meaningfully, add `related:` (or other appropriate relation) on both sides.
   - **Contradictions**: if new info contradicts existing claim, add `contradicts:` on both sides AND leave the older claim with a body marker (do not delete).
   - **`summary` field**: every created/updated page must have a 1-2 sentence `summary` (~200 chars max) in its frontmatter. Rewrite when the page's focus shifted; leave alone otherwise.
   - **`aliases` + `keywords`**: on every created/updated wiki page, write search-expansion frontmatter so concept/synonym queries can find it:
     - `aliases:` — alternate names, abbreviations, and the term in the user's primary language **and** English (e.g. `["쿠버네티스", "K8s"]`). High-precision.
     - `keywords:` — 5–15 related concept/topic terms, again in the user's language + English. Recall-oriented.
     These feed the FTS5 index; they are not shown to the reader. Omit only when nothing sensible applies.

5. **Mark source processed**:
   - Update source frontmatter: `processed: true`, `updated: <today>`.

6. **Update search index**:
   - For each touched page run, from the vault root:
     ```
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rebuild-index.py "$PWD" --upsert <path>
     ```
   - Or, after a large batch: `python3 .../rebuild-index.py "$PWD"` for a full rebuild.
   - The index DB at `.llm-wiki/index.db` is what the auto-context-injection hook reads.

7. **Commit + push (if git)**: see `llm-wiki` skill — "Git sync behavior" section. After all sources processed, commit then `git push`. If push rejected, retry once (pull + push).

## Report

After all sources processed, print:

```
Ingested N sources, touched M pages.

Created:
  - [[<page>]] (<type>, <namespace>)
  ...

Updated:
  - [[<page>]]: <one-line summary of change>
  ...

Skipped:
  - <source>: <reason>
  ...

Questions raised:
  - [[q-<slug>]]
```

## Failure modes

- Source file not found → error, abort.
- Source frontmatter invalid (missing `type` or `namespace`) → error, ask user to fix source.
- Schema missing/invalid → ask user to run `/llm-wiki:init` or fix schema.

## Forbidden

- Never modify `sources/` content (only `processed:` and `updated:` flags).
- Never modify `schema/`.
- Never remove existing `sources:` or relation entries — only append.
