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
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "[[<source-page>]]"   # wiki pages: at least one required
tags: []
---
```

If unsure on classification, use the nearest type and set `confidence: low` (note) or note in body.
