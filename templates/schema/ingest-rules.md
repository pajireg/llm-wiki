# Ingest Rules

Procedure the LLM follows on `/wiki-ingest`.

## Steps (in order)

1. **Load schema** — read all files in `schema/`.
2. **Read source** — read target source file. Note its `namespace`.
3. **Identify related pages** — search wiki:
   - Filename + aliases match
   - frontmatter `topics:` references
   - body text grep
   - Same namespace first, then cross-namespace
4. **Synthesize**:
   - Update existing `topic`/`entity` if the source adds info.
   - Create new `topic` if a coherent new concept emerged.
   - Create `note` if the insight is too raw to synthesize yet.
   - Create `question` if the source raises an unresolved question.
5. **Maintain relations**:
   - All touched pages get `sources: [[<this-source>]]` appended (deduplicated).
   - Significant connections → frontmatter relations, not just body wikilinks.
   - Detected contradiction → add `contradicts:` on both sides.
6. **Mark source** — set `processed: true`, update `updated:`.
7. **Commit** (if vault is git repo) — meaningful message: `wiki: ingest <source-name>`.
8. **Report** — list touched pages with one-line change summary.

## Page creation rules

- Slug from filename. Korean slugs allowed.
- New pages MUST have full common frontmatter + type-specific fields.
- New pages MUST have non-empty `sources:`.

## When not to ingest

- Source has `processed: true` already.
- Source body is empty/trivial (< 50 chars) — skip silently, do not mark `processed`.

## Forbidden

- Editing files under `sources/`.
- Editing files under `schema/`.
- Removing existing `sources:` entries on a page.
