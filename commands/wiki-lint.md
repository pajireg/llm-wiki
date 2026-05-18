---
description: Run 8 health checks on the wiki. Findings-only, no auto-fixes.
---

# /wiki-lint

Use the `llm-wiki` skill from this plugin first.
Follow `schema/lint-rules.md` precisely.

## Checks (in order)

For each, gather findings. Do NOT fix anything.

### 1. Unprocessed source backlog
- `find sources/ -name "*.md"` → for each, check frontmatter `processed: false`.
- Count total. Sort by `ingested_at` ascending. Report oldest 10.

### 2. Duplicate candidates
- For each pair of `topic` pages in same namespace:
  - **High confidence**: identical title OR alias overlap (intersect of aliases sets non-empty).
  - **Low confidence**: cosine TF-IDF similarity of body > 0.7.
- For `entity`, same logic.
- Report pairs.

### 3. Orphan pages
- For each non-source page: count inbound refs (any `[[X]]` in another page's body OR frontmatter relation pointing to it).
- 0 inbound → orphan.
- Report list.

### 4. Broken wikilinks
- For every `[[X]]` (body + frontmatter relations), check that `X.md` exists in `wiki/**` or `sources/**`.
- Missing → broken.
- Report `<source-page>`: `[[broken-target]]`.

### 5. Contradiction markers
- Pages with non-empty `contradicts:` frontmatter.
- Report as pairs.

### 6. Stale open questions
- `wiki/**/q-*.md` with `status: open` and `updated:` more than 30 days ago.
- Report list with age.

### 7. Frontmatter violations
- Missing required fields: `type`, `namespace`, `created`, `updated`.
- Invalid `type` (not in {topic, entity, note, source, question}).
- Invalid `namespace` (not in 5 defined).
- Type-specific violations per `page-types.md`.

### 8. Missing sources
- Any non-`source` page with empty/missing `sources:` frontmatter.
- Sources are exempt.

## Output

Write report to `lint-reports/<YYYY-MM-DD>-lint.md`:

```markdown
---
type: lint-report
created: <today>
---

# Lint Report <YYYY-MM-DD>

## Summary

| Check | Count |
|---|---|
| Unprocessed sources | N |
| Duplicate candidates (high conf) | N |
| Duplicate candidates (low conf) | N |
| Orphan pages | N |
| Broken wikilinks | N |
| Contradiction pairs | N |
| Stale open questions | N |
| Frontmatter violations | N |
| Missing-sources pages | N |

## Unprocessed source backlog
- [[<source-1>]] (ingested 2026-05-10)
- ...

## Duplicate candidates (high confidence)
- [[topic-a]] ↔ [[topic-b]] (alias overlap: "X")
- ...

<...remaining sections per check...>
```

After writing, print path to the report and a one-line summary count.

## Forbidden

- Auto-fixing anything.
- Modifying any wiki page (except writing the new lint report).
- Modifying sources.
