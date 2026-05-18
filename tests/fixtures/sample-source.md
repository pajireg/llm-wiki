---
type: source
source_type: manual
namespace: tech
created: 2026-05-18
updated: 2026-05-18
ingested_at: 2026-05-18T10:00:00
processed: false
---

# Prompt caching basics

Prompt caching reduces the per-request cost of repeated context.
Anthropic exposes it via `cache_control: { type: "ephemeral" }` on a message block.
Cache TTL is 5 minutes; misses recompute fully.

Used with Claude Code's system prompt and stable tool definitions.
