# Relations

5 typed relations. Use frontmatter fields, not just body wikilinks.

| Relation | Meaning | Direction |
|---|---|---|
| `related` | Weak association | Bidirectional (recommended) |
| `part_of` | Hierarchy (A is in B) | Directional (A → B) |
| `contradicts` | Conflict. Lint flags. | Bidirectional |
| `supersedes` | A replaces B. B preserved with marker. | Directional (A → B) |
| `derived_from` | wiki page → source (replaceable by `sources:`) | Directional |

## Body wikilinks vs frontmatter relations

- Body `[[X]]` = "this page mentions X"
- Frontmatter `related: ["[[X]]"]` = "this page is semantically related to X"

Significant connections MUST be in frontmatter. Mentions alone in body are OK for incidental refs.

## Bidirectional integrity

For `related` and `contradicts`, when adding A → B, also add B → A. Lint checks this.
For directional (`part_of`, `supersedes`, `derived_from`), only the source side declares.
