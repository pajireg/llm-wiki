"""Tests for scripts/rebuild-index.py — full rebuild path."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REBUILD_SCRIPT = PLUGIN_ROOT / "scripts" / "rebuild-index.py"


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki" / "tech").mkdir(parents=True)
    (vault / "wiki" / "personal").mkdir(parents=True)
    (vault / "schema").mkdir(parents=True)
    (vault / "sources").mkdir(parents=True)
    return vault


def write_page(vault: Path, rel_path: str, frontmatter: dict, body: str) -> Path:
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}:")
            for item in v:
                fm_lines.append(f'  - "{item}"')
        else:
            fm_lines.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    fm_lines.append("---")
    content = "\n".join(fm_lines) + "\n\n" + body
    path = vault / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def run_rebuild(vault: Path, *extra_args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REBUILD_SCRIPT), str(vault), *extra_args],
        capture_output=True,
        text=True,
    )


def db_rows(vault: Path, sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(str(vault / ".llm-wiki" / "index.db"))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_full_rebuild_indexes_all_wiki_pages(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/ssh.md", {
        "type": "topic", "namespace": "tech",
        "summary": "SSH 키 로테이션과 ed25519 마이그레이션 절차.",
        "created": "2026-05-01", "updated": "2026-05-15",
    }, "# SSH Keys\n\nUse ed25519 for new keys.")
    write_page(vault, "wiki/personal/yubikey.md", {
        "type": "note", "namespace": "personal",
        "summary": "YubiKey 5C 셋업 메모. PIV slot 설정 완료.",
        "created": "2026-05-10", "updated": "2026-05-10",
    }, "# YubiKey\n\nSlot 9a/9c configured.")

    result = run_rebuild(vault)
    assert result.returncode == 0, result.stderr
    assert "indexed=2 errors=0" in result.stdout

    rows = db_rows(vault, "SELECT id, namespace, type FROM pages ORDER BY id")
    assert rows == [("ssh", "tech", "topic"), ("yubikey", "personal", "note")]


def test_summary_field_indexed_when_present(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/gpg.md", {
        "type": "topic", "namespace": "tech",
        "summary": "GPG 키 관리와 YubiKey 연동.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# GPG\n\nbody here")

    run_rebuild(vault)
    rows = db_rows(vault, "SELECT summary FROM pages WHERE id='gpg'")
    assert rows[0][0] == "GPG 키 관리와 YubiKey 연동."


def test_summary_falls_back_to_body_when_missing(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/no-summary.md", {
        "type": "topic", "namespace": "tech",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# No Summary\n\nThis page intentionally omits the summary field.")

    run_rebuild(vault)
    rows = db_rows(vault, "SELECT summary FROM pages WHERE id='no-summary'")
    assert "intentionally omits" in rows[0][0]


def test_fts_query_finds_pages_by_summary_keyword(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/ssh.md", {
        "type": "topic", "namespace": "tech",
        "summary": "SSH key rotation policy.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# SSH\n\nbody")
    write_page(vault, "wiki/personal/diet.md", {
        "type": "note", "namespace": "personal",
        "summary": "Daily nutrition tracking habit.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Diet\n\nbody")

    run_rebuild(vault)
    rows = db_rows(
        vault,
        "SELECT id FROM pages_fts WHERE pages_fts MATCH ? ORDER BY rank",
        ("rotation",),
    )
    assert rows == [("ssh",)]


def test_korean_text_matches(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/keys.md", {
        "type": "topic", "namespace": "tech",
        "summary": "암호화 키 로테이션 90일 주기 권장.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Keys\n\n암호화 키 관리.")

    run_rebuild(vault)
    rows = db_rows(
        vault,
        "SELECT id FROM pages_fts WHERE pages_fts MATCH ?",
        ("로테이션",),
    )
    assert rows == [("keys",)]


def test_namespace_filter_via_pages_table(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/a.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Topic A about backups.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# A\n\nbody")
    write_page(vault, "wiki/personal/b.md", {
        "type": "note", "namespace": "personal",
        "summary": "Note B about backups.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# B\n\nbody")

    run_rebuild(vault)
    rows = db_rows(
        vault,
        """
        SELECT p.id FROM pages p
        JOIN pages_fts f ON f.id = p.id
        WHERE f.pages_fts MATCH ? AND p.namespace = ?
        ORDER BY f.rank
        """,
        ("backups", "tech"),
    )
    assert rows == [("a",)]


def test_index_skips_underscore_files(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/tech/_index.md", {
        "type": "topic", "namespace": "tech",
        "summary": "stub",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "stub body")
    write_page(vault, "wiki/tech/real.md", {
        "type": "topic", "namespace": "tech",
        "summary": "real page",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "real body")

    run_rebuild(vault)
    rows = db_rows(vault, "SELECT id FROM pages")
    assert rows == [("real",)]


def test_empty_wiki_dir_produces_empty_index(tmp_path):
    vault = make_vault(tmp_path)
    result = run_rebuild(vault)
    assert result.returncode == 0
    assert "indexed=0 errors=0" in result.stdout
    rows = db_rows(vault, "SELECT COUNT(*) FROM pages")
    assert rows[0][0] == 0
