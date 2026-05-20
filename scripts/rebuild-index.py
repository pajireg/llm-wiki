#!/usr/bin/env python3
"""Rebuild (or incrementally update) the FTS5 search index for an llm-wiki vault.

The index lives at <vault>/.llm-wiki/index.db and is git-ignored.
It is a derived artifact rebuilt from the .md files anytime — losing it is harmless.

Usage:
  rebuild-index.py [<vault>]              Full rebuild
  rebuild-index.py [<vault>] --upsert <path...>
                                          Upsert specific pages (relative to vault)

If <vault> is omitted, reads ~/.config/llm-wiki/vault-path.
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys

# Allow running as a standalone script from anywhere by adding the
# sibling hooks/ directory to sys.path so we can import _wiki_common.
_HOOKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _wiki_common import (  # noqa: E402
    derive_summary_fallback,
    get_vault_path,
    log_event,
    parse_frontmatter,
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pages (
  id        TEXT PRIMARY KEY,
  path      TEXT NOT NULL,
  namespace TEXT NOT NULL,
  type      TEXT NOT NULL,
  title     TEXT,
  summary   TEXT,
  updated   TEXT,
  mtime     REAL
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
  id UNINDEXED,
  title, summary, body,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE INDEX IF NOT EXISTS pages_namespace_idx ON pages(namespace);
"""


def ensure_db_dir(vault: pathlib.Path) -> pathlib.Path:
    db_dir = vault / ".llm-wiki"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "index.db"


def open_db(vault: pathlib.Path) -> sqlite3.Connection:
    """Open the index DB, creating schema if needed. Heals on corruption."""
    db_path = ensure_db_dir(vault)
    try:
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


def page_id_from_path(path: pathlib.Path) -> str:
    """Stable id derived from filename stem."""
    return path.stem


def extract_title(body: str, fallback: str) -> str:
    """First H1 in body, or fallback (page id)."""
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip() or fallback
        if s and not s.startswith("---"):
            break
    return fallback


def iter_wiki_pages(vault: pathlib.Path):
    """Yield .md files under wiki/."""
    wiki_dir = vault / "wiki"
    if not wiki_dir.is_dir():
        return
    for path in wiki_dir.rglob("*.md"):
        if not path.is_file():
            continue
        # Skip _index.md stubs
        if path.name.startswith("_"):
            continue
        yield path


def upsert_page(conn: sqlite3.Connection, vault: pathlib.Path, md_path: pathlib.Path) -> bool:
    """Upsert a single page into the index. Returns True on success."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return False

    fm, body = parse_frontmatter(text)
    page_id = page_id_from_path(md_path)
    rel_path = str(md_path.relative_to(vault))
    namespace = fm.get("namespace", "") if isinstance(fm.get("namespace", ""), str) else ""
    page_type = fm.get("type", "") if isinstance(fm.get("type", ""), str) else ""
    summary = fm.get("summary", "") if isinstance(fm.get("summary", ""), str) else ""
    if not summary:
        summary = derive_summary_fallback(body)
    updated = fm.get("updated", "") if isinstance(fm.get("updated", ""), str) else ""
    title = extract_title(body, page_id)
    try:
        mtime = md_path.stat().st_mtime
    except OSError:
        mtime = 0.0

    conn.execute(
        """
        INSERT INTO pages (id, path, namespace, type, title, summary, updated, mtime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            path=excluded.path,
            namespace=excluded.namespace,
            type=excluded.type,
            title=excluded.title,
            summary=excluded.summary,
            updated=excluded.updated,
            mtime=excluded.mtime
        """,
        (page_id, rel_path, namespace, page_type, title, summary, updated, mtime),
    )
    conn.execute("DELETE FROM pages_fts WHERE id = ?", (page_id,))
    conn.execute(
        "INSERT INTO pages_fts (id, title, summary, body) VALUES (?, ?, ?, ?)",
        (page_id, title, summary, body),
    )
    return True


def delete_page(conn: sqlite3.Connection, page_id: str) -> None:
    conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    conn.execute("DELETE FROM pages_fts WHERE id = ?", (page_id,))


def full_rebuild(vault: pathlib.Path) -> tuple[int, int]:
    """Wipe and rebuild the index from all wiki/ pages.

    Returns (indexed_count, error_count).
    """
    db_path = ensure_db_dir(vault)
    db_path.unlink(missing_ok=True)
    conn = open_db(vault)
    indexed = 0
    errors = 0
    try:
        for md_path in iter_wiki_pages(vault):
            ok = upsert_page(conn, vault, md_path)
            if ok:
                indexed += 1
            else:
                errors += 1
        conn.commit()
    finally:
        conn.close()
    return indexed, errors


def upsert_paths(vault: pathlib.Path, paths: list[pathlib.Path]) -> tuple[int, int, int]:
    """Upsert (or remove if missing) specific paths.

    Returns (upserted, removed, errors).
    """
    conn = open_db(vault)
    upserted = 0
    removed = 0
    errors = 0
    try:
        for p in paths:
            abs_p = p if p.is_absolute() else vault / p
            if abs_p.is_file():
                if upsert_page(conn, vault, abs_p):
                    upserted += 1
                else:
                    errors += 1
            else:
                # Removal
                page_id = abs_p.stem
                delete_page(conn, page_id)
                removed += 1
        conn.commit()
    finally:
        conn.close()
    return upserted, removed, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", nargs="?", help="vault path (defaults to registered)")
    parser.add_argument(
        "--upsert",
        nargs="+",
        metavar="PATH",
        help="upsert specific page(s) instead of full rebuild",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress stdout output")
    args = parser.parse_args()

    if args.vault:
        vault = pathlib.Path(args.vault)
        if not vault.is_dir():
            print(f"error: not a directory: {vault}", file=sys.stderr)
            return 1
    else:
        vault = get_vault_path()
        if vault is None:
            print(
                "error: no vault path given and ~/.config/llm-wiki/vault-path not set",
                file=sys.stderr,
            )
            return 1

    if args.upsert:
        paths = [pathlib.Path(p) for p in args.upsert]
        up, rm, errs = upsert_paths(vault, paths)
        log_event("index-upsert", vault=str(vault), up=up, rm=rm, errs=errs)
        if not args.quiet:
            print(f"upserted={up} removed={rm} errors={errs}")
        return 0 if errs == 0 else 1

    indexed, errors = full_rebuild(vault)
    log_event("index-rebuild", vault=str(vault), indexed=indexed, errors=errors)
    if not args.quiet:
        print(f"indexed={indexed} errors={errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
