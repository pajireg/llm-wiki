---
type: source
source_type: manual
namespace: personal
processed: false
---

# Welcome to your llm-wiki vault

This note is the first source bootstrapped into your vault. Ingest it to experience your first synthesis:

```
/llm-wiki:ingest
```

With no arguments, ingest processes every unprocessed source. On a fresh vault that's just this welcome doc. When ingest finishes, `wiki/personal/` will contain pages synthesized from this document. Then ask the wiki something like `/llm-wiki:ask "what is the curation loop"` and watch the answer come back from your own wiki with citations.

## The curation loop

llm-wiki runs in three steps:

1. **Auto-capture** — every Claude Code session is saved to `sources/claude-sessions/` as markdown when the session ends. No configuration needed.
2. **Manual synthesis** — accumulated sources are folded into wiki pages (`wiki/<namespace>/`) via `/llm-wiki:ingest`. The model updates existing pages or creates new ones, and maintains relations and citations automatically.
3. **Query and lint** — ask the wiki with `/llm-wiki:ask` and periodically run `/llm-wiki:lint` to surface broken links, orphans, duplicates, and unprocessed sources.

## Five page types

- **topic** — an evolving concept or theme (e.g. "retrieval-augmented generation", "decision journal practice")
- **entity** — a person, tool, or organization (e.g. "Claude Code", "Anthropic")
- **note** — a raw observation or summary; the stage before something becomes a topic
- **source** — an immutable original. This file is a source.
- **question** — an open question; can be promoted to a topic once enough answers accumulate

## Five relations

Stored as wikilink arrays in frontmatter:

- `related` — loose association
- `part_of` — containment (child → parent)
- `contradicts` — conflicting claim
- `supersedes` — replaces an older page
- `derived_from` — synthesized from another page

## Five namespaces

Pages are partitioned under `wiki/<namespace>/`:

- `personal` — personal notes
- `work` — work context
- `tech` — general technical knowledge
- `projects` — specific projects
- `people` — people pages

Auto-classification rules live in `schema/namespaces.md` (`git_owner_to_namespace` and `cwd_to_namespace`). The mapping starts empty and works fine that way — fill it in as you learn your own patterns.

## Day-1 invariants

1. `sources/` is immutable — only the `processed:` and `updated:` flags get touched
2. Every wiki page has a non-empty `sources:` frontmatter list (no claims without provenance)
3. Frontmatter is the source of truth
4. `schema/` is user-owned — the plugin never overwrites it automatically
5. Git auto-commit only fires if the vault is a git repo

## What to do next

- Open `schema/namespaces.md` and add your own git owner → namespace mappings
- Drop ad-hoc notes into `sources/manual/` as markdown files; the next ingest will absorb them
- Once you have ~30 pages, open the vault in Obsidian — the graph view visualizes the wiki structure

Inspired by Karpathy's LLM wiki pattern: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
