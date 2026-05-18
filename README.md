# llm-wiki

> Memex realized with LLMs.

A Claude Code plugin that turns your knowledge into a wiki the model maintains.
Inspired by [Karpathy's LLM wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Three layers (Karpathy)

- **Sources** — immutable originals (Claude sessions, manual notes, articles)
- **Wiki** — synthesized pages by namespace; the LLM keeps them current
- **Schema** — the rules the LLM follows (you own these files)

## Install

```
/plugin marketplace add pajireg/llm-wiki
/plugin install llm-wiki@llm-wiki
```

## Update

```
/plugin marketplace update llm-wiki
```

## Uninstall

```
/plugin marketplace remove llm-wiki
```

Removing the marketplace also uninstalls the plugin. Your vault files are not touched.

## Bootstrap a vault

```bash
mkdir -p ~/Vaults/<your-wiki>
cd ~/Vaults/<your-wiki>
claude
> /wiki-init
```

`/wiki-init` creates the directory structure, copies the schema templates, and prints next-step guidance.

Session auto-capture activates automatically after `/wiki-init`. No env vars or settings.json edits needed.

## Commands

| Command | What it does |
|---|---|
| `/wiki-init` | Bootstrap current dir as a vault |
| `/wiki-ingest [path \| --recent]` | Synthesize sources into the wiki |
| `/wiki-ask <question>` | Answer from the wiki with citations |
| `/wiki-lint` | Run 8 health checks; write report |
| `/wiki-upgrade-schema` | Diff and merge updated schema templates |

## Page types

5 types — `topic`, `entity`, `note`, `source`, `question`. See `templates/schema/page-types.md`.

## Relations

5 typed relations — `related`, `part_of`, `contradicts`, `supersedes`, `derived_from`. See `templates/schema/relations.md`.

## Hard invariants (day-1)

1. Sources are immutable.
2. Every wiki page has non-empty `sources:`.
3. Frontmatter is the source of truth.
4. Schema is user-owned; the plugin never auto-overwrites it.
5. Git auto-commit only if the vault is a git repo.

## Evolution path

```
Phase 1 (day-1 ~ 500 pages):     Markdown + frontmatter + grep + Obsidian search
Phase 2 (500 ~ 2000 pages):      Obsidian Bases views by type/namespace
Phase 3 (2000+ pages):           SQLite index over frontmatter
Phase 4 (when graph analysis):   Neo4j or vector DB
```

Markdown + frontmatter remains the source of truth. All higher-phase indexes are derived.

## License

MIT
