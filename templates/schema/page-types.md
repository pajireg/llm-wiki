# Page Types

5 types. Every page is exactly one. Ingest MUST classify.

## `topic`
Evolving concept page. The wiki's main product.
- Filename: `<slug>.md` (Korean slug allowed)
- Frontmatter additions:
  - `aliases: [...]` — duplicate prevention
  - `related: ["[[other-topic]]"]`
  - `contradicts: ["[[other-topic]]"]`
  - `part_of: ["[[parent-topic]]"]`
  - `supersedes: ["[[old-topic]]"]`

## `entity`
Person, tool, company, project. Stable.
- Filename: `<name-slug>.md`
- Additions:
  - `kind: person | tool | company | project | other`
  - `aliases: [...]`
  - `related: [...]`

## `note`
Raw observation/insight. Pre-synthesis.
- Filename: `<YYYY-MM-DD>-<slug>.md`
- Additions:
  - `topics: ["[[topic-this-belongs-to]]"]`
  - `related: [...]`
  - `confidence: high | medium | low`

## `source`
Original meta (in `sources/`). Read-only.
- Filename: `<YYYY-MM-DD>-<slug>.md`
- Additions:
  - `source_type: claude_session | article | book | conversation | other`
  - `ingested_at: <ISO datetime>`
  - `url: "https://..."` (if applicable)
  - `processed: false` (true after /llm-wiki:ingest)
  - `session_id`, `cwd` (claude_session only)

## `question`
Unanswered, follow-up target.
- Filename: `q-<slug>.md`
- Additions:
  - `topics: ["[[related-topic]]"]`
  - `status: open | investigating | answered | abandoned`
  - `answered_by: ["[[topic-or-note]]"]` (status=answered)

## Common frontmatter (all types)

```yaml
---
type: topic | entity | note | source | question
namespace: personal | work | tech | projects | people
summary: "1-2 line TL;DR of this page (~200 chars max). Used by auto-injection."
keywords: []   # related concept/topic terms (user language + English); feeds search
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "[[<source-page>]]"   # wiki pages: at least one required
tags: []
---
```

### `summary` field

Every wiki page (everything except `source` type) must have a `summary`. It is what
the auto-context-injection hook surfaces in every Claude conversation, so make it
self-contained and informative on its own.

- 1-2 sentences, ~200 chars max
- Plain prose, no markdown decoration
- Written/refreshed by `/llm-wiki:ingest`, not by hand
- Missing `summary` → linter warns; the search hook falls back to the first body paragraph

### `aliases` & `keywords` (search expansion)

Both are LLM-generated to widen what queries can find a page — they are indexed
but never shown to the reader.

- `aliases` — alternate names / abbreviations for the page subject (already used by
  `topic`/`entity` for duplicate prevention; now also indexed for search).
- `keywords` — 5-15 related concept/topic terms.
- Write both in the user's primary language **and** English variants.
- Optional: a missing field is fine; the page still indexes on title/summary/body.

If unsure on classification, use the nearest type and set `confidence: low` (note) or note in body.
