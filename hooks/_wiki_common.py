"""Shared utilities for llm-wiki hooks and scripts.

Pure stdlib (Python 3.9+). No third-party deps. Keep this file small and import-light
so hooks that load it have minimal cold-start overhead.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
import subprocess


def get_vault_path() -> pathlib.Path | None:
    """Read vault path from ~/.config/llm-wiki/vault-path.

    Returns None if not configured or path is not a directory.
    """
    config = pathlib.Path.home() / ".config" / "llm-wiki" / "vault-path"
    if not config.is_file():
        return None
    path_str = config.read_text().strip()
    if not path_str:
        return None
    vault = pathlib.Path(path_str)
    if not vault.is_dir():
        return None
    return vault


def get_git_info(cwd: str) -> tuple[str | None, str | None]:
    """Return (remote_url, owner) for the given cwd, or (None, None) if not a git repo."""
    if not cwd:
        return None, None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return None, None
        url = result.stdout.strip()
        if not url:
            return None, None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None

    return url, parse_git_owner(url)


def parse_git_owner(url: str) -> str | None:
    """Extract the owner part from a git remote URL.

    Supports SSH (`git@host:OWNER/repo`) and HTTP(S)/ssh:// forms.
    """
    if not url:
        return None
    m = re.match(r"^[^@]+@[^:]+:([^/]+)/", url)
    if m:
        return m.group(1)
    m = re.match(r"^[a-z]+://(?:[^@/]+@)?[^/]+/([^/]+)/", url)
    if m:
        return m.group(1)
    return None


def parse_namespaces_md(
    namespaces_md: pathlib.Path,
) -> tuple[dict[str, str], list[tuple[str, str]], str]:
    """Parse a vault's schema/namespaces.md.

    Returns (owner_map, cwd_patterns, default).
    """
    owner_map: dict[str, str] = {}
    cwd_patterns: list[tuple[str, str]] = []
    default = "personal"

    if not namespaces_md.is_file():
        return owner_map, cwd_patterns, default

    current_block: str | None = None

    for line in namespaces_md.read_text().splitlines():
        stripped = line.strip()

        if stripped.startswith("git_owner_to_namespace:"):
            current_block = "owner"
            continue
        if stripped.startswith("cwd_to_namespace:"):
            current_block = "cwd"
            continue
        m_default = re.match(r"^default\s*:\s*([a-zA-Z_]+)\s*$", stripped)
        if m_default and (not line or not line[0].isspace()):
            default = m_default.group(1)
            current_block = None
            continue

        if current_block is None:
            continue

        if line and not line[0].isspace() and stripped and not stripped.startswith("#"):
            current_block = None
            continue
        if not stripped or stripped.startswith("#"):
            continue

        if current_block == "owner":
            m = re.match(r"^([a-zA-Z0-9_.-]+)\s*:\s*([a-zA-Z_]+)\s*$", stripped)
            if m:
                owner_map[m.group(1)] = m.group(2)
        elif current_block == "cwd":
            m = re.match(r'^"([^"]+)"\s*:\s*([a-zA-Z_]+)\s*$', stripped)
            if m:
                cwd_patterns.append((m.group(1), m.group(2)))

    return owner_map, cwd_patterns, default


def determine_namespace(
    cwd: str,
    git_owner: str | None,
    owner_map: dict[str, str],
    cwd_patterns: list[tuple[str, str]],
    default: str,
) -> str:
    """Decide namespace via priority: git_owner → cwd pattern → default."""
    if git_owner and git_owner in owner_map:
        return owner_map[git_owner]

    for pattern, ns in cwd_patterns:
        prefix = pattern
        if prefix.endswith("/**"):
            prefix = prefix[:-3]
        elif prefix.endswith("**"):
            prefix = prefix[:-2]
        if cwd == prefix or cwd.startswith(prefix.rstrip("/") + "/"):
            return ns

    return default


def infer_namespace(cwd: str, vault: pathlib.Path) -> str:
    """High-level helper: full namespace inference from cwd against a vault."""
    _, git_owner = get_git_info(cwd)
    owner_map, cwd_patterns, default = parse_namespaces_md(vault / "schema" / "namespaces.md")
    return determine_namespace(cwd, git_owner, owner_map, cwd_patterns, default)


def yaml_quote(value: str) -> str:
    """Quote a string value for safe YAML output."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def slugify(text: str, max_len: int = 40) -> str:
    """ASCII/Hangul slug, lowercased, hyphen-separated."""
    s = re.sub(r"[^a-zA-Z0-9가-힣\-]", "-", text).lower()
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len] or "session"


def log_event(event: str, **fields) -> None:
    """Append a one-line diagnostic record to ~/.cache/llm-wiki/hook.log.

    Never raises — logging failure must not break the caller.
    """
    try:
        log_dir = pathlib.Path.home() / ".cache" / "llm-wiki"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        parts = [f"event={event}"]
        for k, v in fields.items():
            parts.append(f"{k}={v}")
        line = " ".join(parts)
        with (log_dir / "hook.log").open("a", encoding="utf-8") as f:
            f.write(f"{ts} {line}\n")
    except OSError:
        pass


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML-ish frontmatter from a markdown string.

    Lightweight parser — handles flat key: value pairs, list syntax, and quoted strings.
    Returns (frontmatter_dict, body). Frontmatter values are kept as strings; lists
    of strings; or raw text when the parser can't determine the shape.

    Not a full YAML parser. Sufficient for our schema's flat frontmatter.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    raw_fm = m.group(1)
    body = text[m.end():]

    fm: dict = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in raw_fm.splitlines():
        if not line.strip():
            continue
        # List item under current_key
        if line.lstrip().startswith("- ") and current_key is not None:
            value = line.lstrip()[2:].strip()
            value = _strip_quotes(value)
            if current_list is None:
                current_list = []
                fm[current_key] = current_list
            current_list.append(value)
            continue

        # New key
        m_kv = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$", line)
        if m_kv:
            key = m_kv.group(1)
            value = m_kv.group(2).strip()
            if value == "" or value == "[]":
                # Could be empty list or block-style list starting next line
                fm[key] = [] if value == "[]" else ""
                current_key = key
                current_list = None
                continue
            # Inline list: [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                items = [_strip_quotes(s.strip()) for s in _split_inline_list(inner)] if inner else []
                fm[key] = items
                current_key = key
                current_list = None
                continue
            fm[key] = _strip_quotes(value)
            current_key = key
            current_list = None

    return fm, body


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        inner = s[1:-1]
        if s[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return s


def _split_inline_list(s: str) -> list[str]:
    """Split an inline list contents by comma, respecting quoted strings."""
    out: list[str] = []
    buf: list[str] = []
    in_quote: str | None = None
    for ch in s:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            buf.append(ch)
            in_quote = ch
        elif ch == ",":
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def derive_summary_fallback(body: str, max_chars: int = 150) -> str:
    """When a page has no `summary` field, derive one from the first chunk of body.

    Strip markdown headings and code fences, take the first non-empty prose chunk.
    """
    cleaned_lines: list[str] = []
    in_code = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not stripped:
            if cleaned_lines:
                # Found a paragraph; stop after first
                break
            continue
        if stripped.startswith("#"):
            continue
        cleaned_lines.append(stripped)
        if sum(len(l) for l in cleaned_lines) >= max_chars:
            break
    text = " ".join(cleaned_lines)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text
