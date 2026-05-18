---
description: Compare plugin's schema templates with vault's schema and selectively merge.
---

# /wiki-upgrade-schema

Use the `llm-wiki` skill from this plugin first.

## Procedure

1. **Locate plugin templates**:
   - Plugin templates live at `<plugin-path>/templates/schema/`.
   - Resolve `<plugin-path>` from the current Claude Code plugin install (the location of this command file's parent's parent).

2. **For each of the 6 schema files** (`README.md`, `page-types.md`, `relations.md`, `namespaces.md`, `ingest-rules.md`, `lint-rules.md`):
   - Run `diff <plugin-template-file> <vault-schema-file>`.
   - If identical, skip silently.
   - If different, present diff to user.

3. **For each diff, ask user**:
   - "Apply this change to your `schema/<file>`?"
   - Options: `yes`, `no`, `show full`, `partial — let me describe what to keep`.
   - User-provided partial instructions are honored verbatim.

4. **Apply approved changes** — modify vault `schema/<file>` exactly as user approved.

5. **Commit (if git)**: `wiki: upgrade schema (<files-changed>)`.

## Output

Print a summary:
```
Schema upgrade complete.
Changed: <files>
Unchanged: <files>
Skipped (no diff): <files>
```

## Forbidden

- Auto-applying any change without user approval per file.
- Overwriting `schema/namespaces.md`'s `cwd_to_namespace` block — that's user-specific. Always ask, never silently merge.
- Modifying any wiki content.
