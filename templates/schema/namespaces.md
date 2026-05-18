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

## Source-to-namespace inference (automatic)

The SessionEnd hook determines a source's namespace from the session's working directory using this priority:

1. **`git_owner_to_namespace`** — match the owner of the cwd's git remote URL
2. **`cwd_to_namespace`** — fallback: match cwd against path patterns
3. **`default`** — final fallback

The mapping starts empty. As you use the wiki, frontmatter records the `git_owner` so unmapped owners can be classified later (by `/wiki-lint` or manual edit).

### `git_owner_to_namespace`

Maps the `owner` portion of a git remote URL (e.g., `github.com:OWNER/repo` or `https://github.com/OWNER/repo`).

```yaml
git_owner_to_namespace:
  # Examples (uncomment and edit):
  # pajireg: personal       # your own GitHub handle
  # acme-corp: work         # company organization
```

### `cwd_to_namespace`

Fallback when the cwd has no git remote or owner is unmapped. Patterns use shell glob with `**` for recursive match. Patterns are tried in order; first match wins.

```yaml
cwd_to_namespace:
  # Examples (uncomment and edit):
  # "/Users/<you>/Vaults/wiki/**": personal
```

### `default`

```yaml
default: personal
```
