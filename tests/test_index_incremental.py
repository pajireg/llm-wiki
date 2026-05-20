"""Tests for scripts/rebuild-index.py — incremental --upsert path."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REBUILD_SCRIPT = PLUGIN_ROOT / "scripts" / "rebuild-index.py"


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki" / "tech").mkdir(parents=True)
    (vault / "schema").mkdir(parents=True)
    return vault


def write_page(vault: Path, rel_path: str, frontmatter: dict, body: str) -> Path:
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        fm_lines.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    fm_lines.append("---")
    content = "\n".join(fm_lines) + "\n\n" + body
    path = vault / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def run_full_rebuild(vault: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REBUILD_SCRIPT), str(vault)],
        capture_output=True, text=True,
    )


def run_upsert(vault: Path, *paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REBUILD_SCRIPT), str(vault), "--upsert", *(str(p) for p in paths)],
        capture_output=True, text=True,
    )


def db_rows(vault: Path, sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(str(vault / ".llm-wiki" / "index.db"))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_upsert_adds_new_page(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/first.md", {
        "type": "topic", "namespace": "tech",
        "summary": "First page.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    run_full_rebuild(vault)
    assert db_rows(vault, "SELECT COUNT(*) FROM pages")[0][0] == 1

    new_page = write_page(vault, "wiki/tech/second.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Second page.",
        "created": "2026-05-02", "updated": "2026-05-02",
    }, "body")
    result = run_upsert(vault, new_page)
    assert result.returncode == 0, result.stderr
    assert "upserted=1" in result.stdout

    rows = db_rows(vault, "SELECT id FROM pages ORDER BY id")
    assert rows == [("first",), ("second",)]


def test_upsert_updates_existing_page(tmp_path):
    vault = make_vault(tmp_path)
    page = write_page(vault, "wiki/tech/topic.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Old summary.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    run_full_rebuild(vault)
    assert db_rows(vault, "SELECT summary FROM pages WHERE id='topic'")[0][0] == "Old summary."

    write_page(vault, "wiki/tech/topic.md", {
        "type": "topic", "namespace": "tech",
        "summary": "New summary after edit.",
        "created": "2026-05-01", "updated": "2026-05-15",
    }, "updated body")
    result = run_upsert(vault, page)
    assert result.returncode == 0

    rows = db_rows(vault, "SELECT summary, updated FROM pages WHERE id='topic'")
    assert rows[0] == ("New summary after edit.", "2026-05-15")


def test_upsert_removes_missing_page(tmp_path):
    vault = make_vault(tmp_path)
    page_a = write_page(vault, "wiki/tech/a.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Page A.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body a")
    page_b = write_page(vault, "wiki/tech/b.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Page B.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body b")
    run_full_rebuild(vault)
    assert db_rows(vault, "SELECT COUNT(*) FROM pages")[0][0] == 2

    page_b.unlink()
    result = run_upsert(vault, page_b)
    assert result.returncode == 0
    assert "removed=1" in result.stdout

    rows = db_rows(vault, "SELECT id FROM pages")
    assert rows == [("a",)]


def test_upsert_accepts_relative_paths(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/topic.md", {
        "type": "topic", "namespace": "tech",
        "summary": "S.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")

    result = run_upsert(vault, Path("wiki/tech/topic.md"))
    assert result.returncode == 0
    assert "upserted=1" in result.stdout
    assert db_rows(vault, "SELECT COUNT(*) FROM pages")[0][0] == 1


def test_corrupt_db_triggers_self_heal_on_open(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/topic.md", {
        "type": "topic", "namespace": "tech",
        "summary": "S.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    run_full_rebuild(vault)

    db_path = vault / ".llm-wiki" / "index.db"
    db_path.write_bytes(b"this is not a sqlite file")

    page = vault / "wiki/tech/topic.md"
    result = run_upsert(vault, page)
    assert result.returncode == 0, result.stderr
    rows = db_rows(vault, "SELECT id FROM pages")
    assert rows == [("topic",)]
