# {{VAULT_NAME}}

A personal LLM-maintained wiki built with [llm-wiki](https://github.com/pajireg/llm-wiki).

## Layout

- `sources/` — immutable originals (Claude sessions, manual notes, articles)
- `wiki/` — synthesized pages by namespace
- `schema/` — the rules the LLM follows (your file, your edits)
- `lint-reports/` — periodic health reports

## Common commands

- `/llm-wiki:ingest <source>` — synthesize a source into the wiki
- `/llm-wiki:ask <question>` — query the wiki
- `/llm-wiki:lint` — run the 8 health checks

## Git (optional)

```bash
git init
git remote add origin <your-private-repo-url>
git add . && git commit -m "init"
git push -u origin main
```

The plugin will auto-commit after ingest/lint if `.git/` exists.
