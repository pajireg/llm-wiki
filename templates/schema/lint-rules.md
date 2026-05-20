# Lint Rules

9 checks performed by `/llm-wiki:lint`. Output to `lint-reports/<YYYY-MM-DD>-lint.md`.
Findings only — no auto-fixes.

## Checks

1. **Unprocessed source backlog**
   Find all `sources/**/*.md` with frontmatter `processed: false`.
   Report count + oldest 10.

2. **Duplicate candidates** (topics/entities)
   For each pair of topics in same namespace:
   - Exact-title or alias-overlap → high confidence.
   - Body similarity > 0.7 → low confidence.
   Report pairs.

3. **Orphan pages**
   Pages with zero inbound references (no other page wikilinks to it AND no frontmatter relations point to it).
   Sources are not subject to this check.

4. **Broken wikilinks**
   `[[X]]` references to a page that doesn't exist.
   Both body and frontmatter relations checked.

5. **Contradiction markers**
   All pages with non-empty `contradicts:`. Lists pairs for user decision.

6. **Stale open questions**
   `question` pages with `status: open` and `updated:` older than 30 days.

7. **Frontmatter violations**
   Missing required fields (`type`, `namespace`, `created`, `updated`).
   Invalid `type` (not in 5). Invalid `namespace` (not in 5).

8. **Missing sources**
   wiki pages (any type except `source`) with empty `sources:`.

9. **Missing summary**
   wiki pages (any type except `source`) with empty or missing `summary:` frontmatter.
   The auto-context-injection hook relies on summary for previews; missing summary
   forces body-prefix fallback which is less accurate.

## Report format

```markdown
# Lint Report YYYY-MM-DD

## Summary
| Check | Count |
|---|---|
| Unprocessed sources | N |
...

## Details
<each section with wikilinks to offending pages>
```

## What lint does NOT do

- Auto-fix anything.
- Modify any page.
- Decide between duplicate candidates.
