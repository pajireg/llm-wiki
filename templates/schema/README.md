# Wiki Schema — Constitution

This directory is the authoritative ruleset that the LLM loads on every wiki operation.
You own these files. Edit them to change wiki behavior.

## Three layers (Karpathy)

- `sources/` — immutable originals. Never modify. Correct via new source + `supersedes`.
- `wiki/<namespace>/` — synthesized pages. The LLM maintains these.
- `schema/` — this directory. The rules.

## Hard rules (day-1 strict)

1. Every wiki page MUST have a non-empty `sources:` frontmatter array.
2. Every page MUST have `type:` (one of 5) and `namespace:` (defined in namespaces.md).
3. Sources are read-only. New facts → new source + relation update.
4. Frontmatter is the source of truth. Body wikilinks are mentions; frontmatter relations are semantics.
5. LLM never auto-edits this `schema/` directory.

## How LLM uses this directory

On every `/wiki-*` command, load all files in this directory into context BEFORE acting.

## See also

- `page-types.md` — 5 page types
- `relations.md` — 5 relation types
- `namespaces.md` — domain isolation + cwd mapping
- `ingest-rules.md` — ingest procedure
- `lint-rules.md` — 8 lint checks
