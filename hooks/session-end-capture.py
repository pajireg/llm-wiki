#!/usr/bin/env python3
"""SessionEnd hook for llm-wiki.

Reads JSON from stdin: {session_id, cwd, transcript}
Writes a source markdown file into <vault>/sources/claude-sessions/.
Vault path is read from ~/.config/llm-wiki/vault-path (written by /wiki-init).
No-op if not configured or the vault is not initialized.
"""
import datetime
import json
import pathlib
import re
import sys


def parse_cwd_to_namespace(namespaces_md: pathlib.Path) -> tuple[list[tuple[str, str]], str]:
    """Parse the cwd_to_namespace block from schema/namespaces.md.

    Returns (patterns, default) where patterns is a list of (glob_pattern, namespace) tuples.
    """
    patterns: list[tuple[str, str]] = []
    default = "personal"
    if not namespaces_md.is_file():
        return patterns, default

    in_block = False
    for line in namespaces_md.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("cwd_to_namespace:"):
            in_block = True
            continue
        if not in_block:
            continue
        # End of block: top-level non-empty line that isn't indented
        if line and not line[0].isspace() and stripped and not stripped.startswith("#"):
            break
        if not stripped or stripped.startswith("#"):
            continue

        # default: <ns>
        m_default = re.match(r"default\s*:\s*([a-zA-Z_]+)\s*$", stripped)
        if m_default:
            default = m_default.group(1)
            continue

        # "pattern": namespace
        m_pat = re.match(r'"([^"]+)"\s*:\s*([a-zA-Z_]+)\s*$', stripped)
        if m_pat:
            patterns.append((m_pat.group(1), m_pat.group(2)))

    return patterns, default


def determine_namespace(cwd: str, patterns: list[tuple[str, str]], default: str) -> str:
    """Match cwd against patterns (first match wins).

    Pattern syntax: a prefix ending with /** matches any descendant.
    Exact prefix match (no **) matches when cwd starts with pattern.
    """
    for pattern, ns in patterns:
        # Strip trailing /** or ** to get the prefix
        prefix = pattern
        if prefix.endswith("/**"):
            prefix = prefix[:-3]
        elif prefix.endswith("**"):
            prefix = prefix[:-2]
        # Match if cwd is the prefix itself or starts with prefix + "/"
        if cwd == prefix or cwd.startswith(prefix.rstrip("/") + "/"):
            return ns
    return default


def yaml_quote(value: str) -> str:
    """Quote a string value for safe YAML output."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def slugify(text: str, max_len: int = 40) -> str:
    """ASCII slug, lowercased, hyphen-separated."""
    s = re.sub(r"[^a-zA-Z0-9가-힣\-]", "-", text).lower()
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len] or "session"


def get_vault_path() -> pathlib.Path | None:
    """Read vault path from ~/.config/llm-wiki/vault-path. Return None if not configured."""
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


def main() -> int:
    vault = get_vault_path()
    if vault is None:
        return 0  # No vault configured (i.e., /wiki-init was not run)

    sessions_dir = vault / "sources" / "claude-sessions"
    if not sessions_dir.is_dir():
        return 0  # Vault structure incomplete

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # Malformed input, fail silently

    session_id = payload.get("session_id", "unknown")
    cwd = payload.get("cwd", "")
    transcript = payload.get("transcript", "")

    if len(transcript.strip()) < 50:
        return 0  # Trivial session, skip

    patterns, default = parse_cwd_to_namespace(vault / "schema" / "namespaces.md")
    namespace = determine_namespace(cwd, patterns, default)

    today = datetime.date.today().isoformat()
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")

    cwd_basename = pathlib.Path(cwd).name if cwd else "session"
    slug = slugify(cwd_basename)
    session_prefix = session_id[:8] if session_id else "unknown"
    filename = f"{today}-{slug}-{session_prefix}.md"

    content = f"""---
type: source
source_type: claude_session
namespace: {namespace}
created: {today}
updated: {today}
ingested_at: {now_iso}
processed: false
session_id: {yaml_quote(session_id)}
cwd: {yaml_quote(cwd)}
---

# Claude session: {cwd_basename}

{transcript}
"""

    out_path = sessions_dir / filename
    out_path.write_text(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
