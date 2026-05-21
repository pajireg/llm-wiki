# Write-Time Keyword Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make synonym/abbreviation/concept queries surface the right wiki pages by indexing LLM-generated `aliases`/`keywords` frontmatter — without any new dependency or per-prompt model call.

**Architecture:** `/llm-wiki:ingest` writes `aliases` + `keywords` into each page's frontmatter. `rebuild-index.py` indexes them as two new FTS5 columns. The auto-injection hook ranks results with column-weighted BM25 (aliases highest). Query side stays pure-stdlib OR-of-tokens; the document side is now richer. The FTS5 table can't gain columns in place, so an old index is detected and rebuilt (the index is a safe-to-wipe derived artifact).

**Tech Stack:** Python 3.9 stdlib (`sqlite3` FTS5), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-21-write-time-keyword-expansion-design.md`

---

## File Structure

- `scripts/rebuild-index.py` — add `aliases`/`keywords` FTS5 columns, read+flatten them from frontmatter, migrate stale indexes. (Tasks 1–2)
- `hooks/user-prompt-inject.py` — switch ranking to column-weighted `bm25()`. (Task 3)
- `tests/test_index_build.py` — index/migration tests. (Tasks 1–2)
- `tests/test_hook_inject.py` — ranking test. (Task 3)
- `commands/ingest.md`, `templates/schema/ingest-rules.md`, `templates/schema/page-types.md`, `skills/llm-wiki/SKILL.md` — instruct generation + document the fields. (Task 4)

Note: `aliases` already exists as a topic/entity convention in `page-types.md` but is **not currently indexed**. This work makes it searchable and adds `keywords` for all wiki page types.

---

## Task 1: Index `aliases` and `keywords` as FTS5 columns

**Files:**
- Modify: `scripts/rebuild-index.py` (SCHEMA_SQL ~35-54, `upsert_page` ~110-152)
- Test: `tests/test_index_build.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_index_build.py`:

```python
def test_aliases_and_keywords_are_searchable(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/k8s.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Container orchestration platform notes.",
        "aliases": ["쿠버네티스", "K8s"],
        "keywords": ["오케스트레이션", "orchestration", "container scheduling"],
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Kubernetes\n\nDeployment and service basics.")

    run_rebuild(vault)

    # Matches on an alias that appears nowhere in title/summary/body
    by_alias = db_rows(
        vault, "SELECT id FROM pages_fts WHERE pages_fts MATCH ?", ("쿠버네티스",))
    assert by_alias == [("k8s",)]

    # Matches on a keyword that appears nowhere in title/summary/body
    by_keyword = db_rows(
        vault, "SELECT id FROM pages_fts WHERE pages_fts MATCH ?", ("오케스트레이션",))
    assert by_keyword == [("k8s",)]


def test_page_without_aliases_or_keywords_still_indexes(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/plain.md", {
        "type": "topic", "namespace": "tech",
        "summary": "A page with no aliases or keywords.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Plain\n\nbody text")

    result = run_rebuild(vault)
    assert "indexed=1 errors=0" in result.stdout
    rows = db_rows(
        vault, "SELECT id FROM pages_fts WHERE pages_fts MATCH ?", ("Plain",))
    assert rows == [("plain",)]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_index_build.py::test_aliases_and_keywords_are_searchable tests/test_index_build.py::test_page_without_aliases_or_keywords_still_indexes -v`
Expected: `test_aliases_and_keywords_are_searchable` FAILS — `pages_fts` has no `aliases`/`keywords` columns so the alias/keyword terms aren't indexed and the MATCH returns `[]`. (The "still indexes" test may already pass; that's fine — it guards the no-field path.)

- [ ] **Step 3: Add the FTS5 columns to the schema**

In `scripts/rebuild-index.py`, replace the `pages_fts` definition inside `SCHEMA_SQL`:

```python
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
  id UNINDEXED,
  title, summary, body, aliases, keywords,
  tokenize='unicode61 remove_diacritics 2'
);
```

- [ ] **Step 4: Add a flatten helper and index the new fields in `upsert_page`**

In `scripts/rebuild-index.py`, add a module-level helper above `upsert_page`:

```python
def flatten_terms(value) -> str:
    """Flatten a frontmatter list (or string) of terms into one indexable string."""
    if isinstance(value, list):
        return " ".join(str(x).strip() for x in value if str(x).strip())
    if isinstance(value, str):
        return value.strip()
    return ""
```

In `upsert_page`, after the `title = extract_title(...)` line and before the `mtime` block, add:

```python
    aliases = flatten_terms(fm.get("aliases"))
    keywords = flatten_terms(fm.get("keywords"))
```

Then replace the `pages_fts` INSERT at the end of `upsert_page`:

```python
    conn.execute("DELETE FROM pages_fts WHERE id = ?", (page_id,))
    conn.execute(
        "INSERT INTO pages_fts (id, title, summary, body, aliases, keywords) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (page_id, title, summary, body, aliases, keywords),
    )
    return True
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_index_build.py -v`
Expected: PASS (all tests in the file, including the two new ones).

- [ ] **Step 6: Commit**

```bash
git add scripts/rebuild-index.py tests/test_index_build.py
git commit -m "feat: index aliases and keywords as FTS5 columns

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Migrate stale (pre-aliases) indexes by full rebuild

**Files:**
- Modify: `scripts/rebuild-index.py` (`open_db` ~63-77, `upsert_paths` ~183-208)
- Test: `tests/test_index_build.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_index_build.py` (uses `sqlite3` and `textwrap`, already imported):

```python
def _make_legacy_index(vault: Path) -> None:
    """Create an old-schema index.db: pages_fts WITHOUT aliases/keywords columns."""
    db_dir = vault / ".llm-wiki"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_dir / "index.db"))
    conn.executescript(textwrap.dedent("""
        CREATE TABLE pages (
          id TEXT PRIMARY KEY, path TEXT NOT NULL, namespace TEXT NOT NULL,
          type TEXT NOT NULL, title TEXT, summary TEXT, updated TEXT, mtime REAL
        );
        CREATE VIRTUAL TABLE pages_fts USING fts5(
          id UNINDEXED, title, summary, body,
          tokenize='unicode61 remove_diacritics 2'
        );
    """))
    conn.execute(
        "INSERT INTO pages (id, path, namespace, type, title, summary, updated, mtime) "
        "VALUES ('stale', 'wiki/tech/stale.md', 'tech', 'topic', 'Stale', 's', '2026-01-01', 0.0)")
    conn.execute(
        "INSERT INTO pages_fts (id, title, summary, body) VALUES ('stale','Stale','s','b')")
    conn.commit()
    conn.close()


def test_upsert_on_legacy_index_triggers_full_rebuild(tmp_path):
    vault = make_vault(tmp_path)
    _make_legacy_index(vault)
    page = write_page(vault, "wiki/tech/fresh.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Fresh page with aliases.",
        "aliases": ["신선페이지"],
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Fresh\n\nbody")

    # An --upsert against a legacy index must not crash and must migrate the schema.
    result = run_rebuild(vault, "--upsert", str(page.relative_to(vault)))
    assert result.returncode == 0, result.stderr

    # New FTS5 columns now exist and the alias is searchable.
    cols = [r[1] for r in db_rows(vault, "PRAGMA table_info(pages_fts)")]
    assert "aliases" in cols and "keywords" in cols
    rows = db_rows(
        vault, "SELECT id FROM pages_fts WHERE pages_fts MATCH ?", ("신선페이지",))
    assert rows == [("fresh",)]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_index_build.py::test_upsert_on_legacy_index_triggers_full_rebuild -v`
Expected: FAIL — the `--upsert` INSERT references `aliases`/`keywords` columns the legacy table lacks, so `rebuild-index.py` exits non-zero (or the assertion on columns fails).

- [ ] **Step 3: Add a schema-currency check and migrate in `open_db`**

In `scripts/rebuild-index.py`, add a helper above `open_db`:

```python
def _fts_is_current(conn: sqlite3.Connection) -> bool:
    """True if pages_fts has the aliases+keywords columns (current schema)."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(pages_fts)").fetchall()}
    except sqlite3.Error:
        return False
    return {"aliases", "keywords"}.issubset(cols)
```

Replace the body of `open_db` with:

```python
def open_db(vault: pathlib.Path) -> sqlite3.Connection:
    """Open the index DB, creating schema if needed. Heals corruption and
    migrates a stale (pre-aliases/keywords) FTS5 schema by wiping it."""
    db_path = ensure_db_dir(vault)
    try:
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        if not _fts_is_current(conn):
            conn.close()
            db_path.unlink(missing_ok=True)
            conn = sqlite3.connect(str(db_path))
            conn.executescript(SCHEMA_SQL)
        conn.commit()
        return conn
    except sqlite3.DatabaseError:
        # Corruption — wipe and recreate
        db_path.unlink(missing_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        return conn
```

- [ ] **Step 4: Make `upsert_paths` full-rebuild when the index was stale**

The `open_db` migration wipes a stale index, which would leave an `--upsert` with only the named pages. Guard for completeness. In `scripts/rebuild-index.py`, replace the start of `upsert_paths` (before `conn = open_db(vault)`):

```python
def upsert_paths(vault: pathlib.Path, paths: list[pathlib.Path]) -> tuple[int, int, int]:
    """Upsert (or remove if missing) specific paths.

    If the existing index predates the aliases/keywords schema, a full rebuild is
    required for completeness (the migration wipes the stale index).
    Returns (upserted, removed, errors).
    """
    db_path = ensure_db_dir(vault)
    if db_path.exists():
        probe = sqlite3.connect(str(db_path))
        try:
            stale = not _fts_is_current(probe)
        finally:
            probe.close()
        if stale:
            indexed, errors = full_rebuild(vault)
            return indexed, 0, errors

    conn = open_db(vault)
```

(The rest of `upsert_paths` — the `for p in paths:` loop through `return upserted, removed, errors` — is unchanged.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_index_build.py tests/test_index_incremental.py -v`
Expected: PASS (new migration test plus all existing build/incremental tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/rebuild-index.py tests/test_index_build.py
git commit -m "feat: migrate pre-aliases index by full rebuild

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Column-weighted BM25 ranking in the injection hook

**Files:**
- Modify: `hooks/user-prompt-inject.py` (`search_index` ~60-106)
- Test: `tests/test_hook_inject.py`

- [ ] **Step 1: Write the failing test**

First inspect the existing helpers in `tests/test_hook_inject.py` (`make_vault`, `write_page`, `build_index`, `configure_home`, `run_hook`) and reuse them verbatim. Append this test:

```python
def test_alias_match_outranks_body_only_match(tmp_path):
    vault = make_vault(tmp_path)
    # Page A: the query term "쿠버네티스" lives only in aliases.
    write_page(vault, "wiki/tech/k8s.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Orchestration platform overview.",
        "aliases": ["쿠버네티스"],
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Kubernetes\n\nGeneric platform notes.")
    # Page B: the query term appears once, buried in the body.
    write_page(vault, "wiki/tech/notes.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Assorted infra notes.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Notes\n\nWe also mention 쿠버네티스 once here in passing.")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {"prompt": "쿠버네티스 설정 방법", "cwd": str(vault)})

    assert result.returncode == 0
    out = result.stdout
    assert "[[k8s]]" in out and "[[notes]]" in out
    # The alias-weighted page must be listed before the body-only page.
    assert out.index("[[k8s]]") < out.index("[[notes]]")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_hook_inject.py::test_alias_match_outranks_body_only_match -v`
Expected: FAIL — with uniform `ORDER BY f.rank`, the alias match is not boosted, so ordering is not guaranteed (alias likely loses to the body match). The `out.index` assertion fails.

- [ ] **Step 3: Add weight constants**

In `hooks/user-prompt-inject.py`, after the existing `TOP_K = 5` constant, add:

```python
# BM25 column weights, in pages_fts column order:
# id(UNINDEXED), title, summary, body, aliases, keywords.
# Higher = the column contributes more to relevance. aliases is the strongest
# signal (exact alternate-name hit); body is the baseline.
BM25_WEIGHTS = (0.0, 3.0, 2.0, 1.0, 5.0, 2.0)
```

- [ ] **Step 4: Use weighted bm25() in both queries**

In `hooks/user-prompt-inject.py`, in `search_index`, replace the two `ORDER BY f.rank` clauses with a weighted `bm25()` call. The FTS table is aliased `f`, so reference it as `f` in `bm25()`:

```python
        weights = ", ".join(str(w) for w in BM25_WEIGHTS)
        if namespace:
            sql = f"""
                SELECT p.id, p.path, p.namespace, p.type, p.title, p.summary
                FROM pages_fts f
                JOIN pages p ON p.id = f.id
                WHERE f.pages_fts MATCH ? AND p.namespace = ?
                ORDER BY bm25(f, {weights})
                LIMIT ?
            """
            params: tuple = (query, namespace, limit)
        else:
            sql = f"""
                SELECT p.id, p.path, p.namespace, p.type, p.title, p.summary
                FROM pages_fts f
                JOIN pages p ON p.id = f.id
                WHERE f.pages_fts MATCH ?
                ORDER BY bm25(f, {weights})
                LIMIT ?
            """
            params = (query, limit)
```

Note: `BM25_WEIGHTS` is a fixed module constant (not user input), so interpolating it into the SQL string is safe. The user query stays a bound `?` parameter.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_hook_inject.py tests/test_hook_safety.py -v`
Expected: PASS (new ranking test plus all existing inject/safety tests). If `bm25(f, ...)` raises "no such function" or an arity error, the hook's `except sqlite3.Error` swallows it and returns no rows — the new test would then fail on the missing `[[k8s]]`, signaling the `bm25` call needs fixing (e.g. argument count must match the 6 columns).

- [ ] **Step 6: Commit**

```bash
git add hooks/user-prompt-inject.py tests/test_hook_inject.py
git commit -m "feat: weight aliases/title higher in injection ranking

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Instruct generation and document the fields

**Files:**
- Modify: `commands/ingest.md` (step 4, ~45-50)
- Modify: `templates/schema/ingest-rules.md` (step 6 area)
- Modify: `templates/schema/page-types.md` (common frontmatter ~49-62)
- Modify: `skills/llm-wiki/SKILL.md` (Search index section ~32-39)

This task is documentation/instructions only — no automated test. Verify by re-reading each edited section.

- [ ] **Step 1: Add generation instruction to `commands/ingest.md`**

In `commands/ingest.md`, inside `## Per-source procedure` step 4 (**Apply changes**), add a new bullet immediately after the `**`summary` field**` bullet (line ~50):

```markdown
   - **`aliases` + `keywords`**: on every created/updated wiki page, write search-expansion frontmatter so concept/synonym queries can find it:
     - `aliases:` — alternate names, abbreviations, and the term in the user's primary language **and** English (e.g. `["쿠버네티스", "K8s"]`). High-precision.
     - `keywords:` — 5–15 related concept/topic terms, again in the user's language + English. Recall-oriented.
     These feed the FTS5 index; they are not shown to the reader. Omit only when nothing sensible applies.
```

- [ ] **Step 2: Add the same to `templates/schema/ingest-rules.md`**

In `templates/schema/ingest-rules.md`, under `## Steps (in order)`, insert a new step between the current step 6 (`Refresh summary`) and step 7 (`Mark source`), and renumber the rest (7→8 … 11→12):

```markdown
7. **Write search-expansion fields** on every touched wiki page:
   - `aliases:` — alternate names / abbreviations, in the user's primary language + English. High-precision.
   - `keywords:` — 5-15 related concept/topic terms, user's language + English. Recall-oriented.
   These are indexed by FTS5 so synonym/concept queries surface the page; they are not displayed. Generated by the LLM, not by hand.
```

- [ ] **Step 3: Document `keywords` in `templates/schema/page-types.md`**

In `templates/schema/page-types.md`, in the `## Common frontmatter (all types)` YAML block (~51-62), add a `keywords` line after `summary`:

```yaml
summary: "1-2 line TL;DR of this page (~200 chars max). Used by auto-injection."
keywords: []   # related concept/topic terms (user language + English); feeds search
```

Then add a short subsection after the `### `summary` field` block (after line ~74):

```markdown
### `aliases` & `keywords` (search expansion)

Both are LLM-generated to widen what queries can find a page — they are indexed
but never shown to the reader.

- `aliases` — alternate names / abbreviations for the page subject (already used by
  `topic`/`entity` for duplicate prevention; now also indexed for search).
- `keywords` — 5-15 related concept/topic terms.
- Write both in the user's primary language **and** English variants.
- Optional: a missing field is fine; the page still indexes on title/summary/body.
```

- [ ] **Step 4: Note the new fields in `skills/llm-wiki/SKILL.md`**

In `skills/llm-wiki/SKILL.md`, in the `## Search index` section, add a bullet after the "Ingest must keep the index in sync" bullet (~37):

```markdown
- Ingest writes `aliases` + `keywords` frontmatter (user language + English) on every
  touched wiki page; the index searches them so synonym/concept queries match. Optional
  per page — a page without them still indexes on title/summary/body.
```

- [ ] **Step 5: Verify edits and run the full suite**

Re-read each edited section to confirm the wording is present and consistent. Then:
Run: `python3 -m pytest tests/ -v`
Expected: all tests pass (the prior 15 plus the 4 new ones = 19).

- [ ] **Step 6: Commit**

```bash
git add commands/ingest.md templates/schema/ingest-rules.md templates/schema/page-types.md skills/llm-wiki/SKILL.md
git commit -m "docs: instruct aliases/keywords generation and document fields

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Run `python3 -m pytest tests/ -v` — all pass.
- [ ] Run `claude plugin validate .` — passes (no plugin/marketplace JSON changed, but confirm nothing broke).
- [ ] Confirm no version bump was made (per author preference; the release decision is deferred and handled separately).

## Out of scope (do NOT implement here)

- True vector embeddings / opt-in semantic layer.
- Multi-agent ingest.
- A backfill command — existing pages enrich lazily on next ingest.
- Version bump in `plugin.json` / `marketplace.json`.
