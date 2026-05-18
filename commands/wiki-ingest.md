---
description: Synthesize a source (or batch of recent sources) into the wiki.
---

# /wiki-ingest [source-path | --recent <duration>]

Use the `llm-wiki` skill from this plugin first (load schema and invariants).

## Argument parsing

- No args → ingest all `sources/**/*.md` with `processed: false`.
- A single file path → ingest just that file.
- `--recent 1d` / `--recent 7d` → ingest unprocessed sources whose `ingested_at` is within the duration.

## Per-source procedure (follow `schema/ingest-rules.md`)

For each target source:

1. **Read source** — full content + frontmatter. Note `namespace`.

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

5. **Mark source processed**:
   - Update source frontmatter: `processed: true`, `updated: <today>`.

6. **Commit (if git)**: see `llm-wiki` skill section on commit behavior.

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
- Schema missing/invalid → ask user to run `/wiki-init` or fix schema.

## Forbidden

- Never modify `sources/` content (only `processed:` and `updated:` flags).
- Never modify `schema/`.
- Never remove existing `sources:` or relation entries — only append.
