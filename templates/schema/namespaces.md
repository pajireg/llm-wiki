# Namespaces

5 namespaces. Every page has exactly one in frontmatter.

| Namespace | Use for |
|---|---|
| `personal` | Personal knowledge, goals, habits |
| `work` | Work projects, decisions, meetings |
| `tech` | Tech learning: languages, tools, patterns |
| `projects` | Active projects (personal or work) |
| `people` | Person entities (cross-cutting) |

## Link policy

```yaml
namespaces:
  personal: { allow_links_to: [all] }
  work:     { allow_links_to: [all] }
  tech:     { allow_links_to: [all] }
  projects: { allow_links_to: [all] }
  people:   { allow_links_to: [all] }
```

If you have stricter requirements (e.g., work isolation), edit the `allow_links_to` arrays.

## Source-to-namespace mapping (cwd-based)

When the SessionEnd hook captures a Claude Code session, it determines the source's namespace from the session's working directory using this table.

**Fill in your actual directory structure below.** Patterns are matched in order; first match wins.

```yaml
cwd_to_namespace:
  # Example (replace with yours):
  # "/Users/<you>/Vaults/wiki/**": personal
  # "/Users/<you>/projects/**":     tech
  # "/Users/<you>/work/**":         work
  default: personal
```

Patterns use shell glob with `**` for recursive match.
