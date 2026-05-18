---
description: Ask a question, answered from the wiki with citations.
---

# /llm-wiki:ask <question>

Use the `llm-wiki` skill from this plugin first.

## Procedure

1. **Search** — locate relevant pages:
   - Grep keywords across `wiki/`.
   - Match aliases in topic/entity frontmatter.
   - Prefer `topic` and `entity` pages over `note` and `source`.

2. **Load** — read top 5-10 candidate pages (full content + frontmatter).

3. **Answer** — generate the response with these constraints:
   - Cite every non-trivial claim with a wikilink `[[<page>]]`.
   - If the wiki has no info, say so explicitly. Do NOT hallucinate.
   - If pages contradict each other, mention the conflict and cite both.
   - Distinguish "wiki says" from "I infer" — only the former gets wikilinks.

4. **Offer to save** — if the answer involved synthesizing new insight:
   - Ask: "This answer combined info from N pages into something new. Save as `note` page?"
   - On user yes: create a `note` page in the appropriate namespace, with `sources:` pointing to the queried pages and `topics:` linking to relevant topics.
   - On no/silence: do nothing.

## Report format

```
<the answer in prose, with [[wikilinks]] inline as citations>

---
Sources consulted:
  - [[page-1]]
  - [[page-2]]

Coverage:
  - <if any aspect of question wasn't in wiki, list here>
```

## Forbidden

- Inventing facts not present in the wiki.
- Auto-saving the answer as a new page without explicit user approval.
- Modifying source pages.
