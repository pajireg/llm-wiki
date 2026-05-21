#!/usr/bin/env python3
"""UserPromptSubmit hook — auto-inject relevant wiki pages into Claude context.

Reads the user's prompt from stdin, searches the vault's FTS5 index for
related pages, and prints a <wiki_context> block to stdout. Claude consumes
stdout as additional context for the turn.

Safe-by-default: any error → silent exit 0. Never blocks the user's prompt.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sqlite3
import sys

_HOOKS_DIR = pathlib.Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _wiki_common import (  # noqa: E402
    get_vault_path,
    infer_namespace,
    log_event,
)

MAX_QUERY_CHARS = 200
MAX_TOKENS = 12
MIN_TOKEN_LEN = 2
TOP_K = 5

# BM25 column weights, in pages_fts column order:
# id(UNINDEXED), title, summary, body, aliases, keywords.
# Higher = the column contributes more to relevance. aliases is the strongest
# signal (exact alternate-name hit); body is the baseline.
BM25_WEIGHTS = (0.0, 3.0, 2.0, 1.0, 5.0, 2.0)


def sanitize_fts5_query(prompt: str) -> str:
    """Convert a free-form prompt into a safe FTS5 OR query.

    Extracts unicode word tokens, dedupes, caps at MAX_TOKENS, and joins with
    OR so even partial overlap still ranks. BM25 handles relevance ordering.
    """
    text = prompt.strip()[:MAX_QUERY_CHARS]
    tokens = re.findall(r"[\w가-힣][\w가-힣\-]*", text, flags=re.UNICODE)
    seen: set = set()
    filtered: list[str] = []
    for t in tokens:
        if len(t) < MIN_TOKEN_LEN:
            continue
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        filtered.append(t)
        if len(filtered) >= MAX_TOKENS:
            break
    if not filtered:
        return ""
    return " OR ".join(f'"{t}"' for t in filtered)


def search_index(
    db_path: pathlib.Path,
    query: str,
    namespace: str | None,
    limit: int,
) -> list[dict]:
    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return []
    try:
        weights = ", ".join(str(w) for w in BM25_WEIGHTS)
        if namespace:
            sql = f"""
                SELECT p.id, p.path, p.namespace, p.type, p.title, p.summary
                FROM pages_fts f
                JOIN pages p ON p.id = f.id
                WHERE f.pages_fts MATCH ? AND p.namespace = ?
                ORDER BY bm25(pages_fts, {weights})
                LIMIT ?
            """
            params: tuple = (query, namespace, limit)
        else:
            sql = f"""
                SELECT p.id, p.path, p.namespace, p.type, p.title, p.summary
                FROM pages_fts f
                JOIN pages p ON p.id = f.id
                WHERE f.pages_fts MATCH ?
                ORDER BY bm25(pages_fts, {weights})
                LIMIT ?
            """
            params = (query, limit)
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [
        {
            "id": r[0],
            "path": r[1],
            "namespace": r[2],
            "type": r[3],
            "title": r[4],
            "summary": r[5],
        }
        for r in rows
    ]


def format_context_block(rows: list[dict], namespace: str, scope: str) -> str:
    lines = [
        f'<wiki_context namespace="{namespace}" matched="{len(rows)}" scope="{scope}">',
        "The following wiki pages may be relevant to the user's question.",
        "Use the Read tool to fetch full content if you need it.",
        "",
    ]
    for r in rows:
        summary = (r["summary"] or "").strip().replace("\n", " ")
        lines.append(f'- [[{r["id"]}]] ({r["type"]}) — {summary}')
        lines.append(f'  → {r["path"]}')
    lines.append("</wiki_context>")
    return "\n".join(lines)


def is_disabled(vault: pathlib.Path) -> bool:
    if os.environ.get("LLM_WIKI_AUTO_INJECT", "").strip() == "0":
        return True
    return (vault / ".llm-wiki" / "disabled").is_file()


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, OSError, ValueError):
        log_event("user-prompt-inject", reason="bad_payload")
        return 0

    try:
        vault = get_vault_path()
        if vault is None:
            log_event("user-prompt-inject", reason="no_vault")
            return 0

        if is_disabled(vault):
            log_event("user-prompt-inject", reason="disabled")
            return 0

        db_path = vault / ".llm-wiki" / "index.db"
        if not db_path.is_file():
            log_event("user-prompt-inject", reason="no_index")
            return 0

        prompt = payload.get("prompt", "") or ""
        query = sanitize_fts5_query(prompt)
        if not query:
            log_event("user-prompt-inject", reason="empty_query")
            return 0

        cwd = payload.get("cwd", "") or ""
        try:
            namespace = infer_namespace(cwd, vault)
        except Exception:
            namespace = "personal"

        rows = search_index(db_path, query, namespace, TOP_K)
        scope = namespace
        if not rows:
            rows = search_index(db_path, query, None, TOP_K)
            scope = "all"

        if not rows:
            log_event("user-prompt-inject", reason="no_match", ns=namespace)
            return 0

        sys.stdout.write(format_context_block(rows, namespace, scope) + "\n")
        log_event(
            "user-prompt-inject",
            matched=len(rows),
            ns=namespace,
            scope=scope,
            tokens=len(query.split(" OR ")),
        )
        return 0
    except Exception as exc:  # pragma: no cover — defensive blanket
        log_event("user-prompt-inject", reason="error", error=type(exc).__name__)
        return 0


if __name__ == "__main__":
    sys.exit(main())
