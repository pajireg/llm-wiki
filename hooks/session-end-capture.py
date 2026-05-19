#!/usr/bin/env python3
"""SessionEnd hook for llm-wiki.

Reads JSON from stdin: {session_id, cwd, transcript_path, hook_event_name}
Writes a source markdown file into <vault>/sources/claude-sessions/.
Vault path is read from ~/.config/llm-wiki/vault-path (written by /llm-wiki:init).
No-op if not configured or the vault is not initialized.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
import subprocess
import sys


def get_git_info(cwd: str) -> tuple[str | None, str | None]:
    """Return (remote_url, owner) for the given cwd, or (None, None) if not a git repo or no remote."""
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

    owner = parse_git_owner(url)
    return url, owner


def parse_git_owner(url: str) -> str | None:
    """Extract the owner part from a git remote URL.

    Supports:
      git@github.com:OWNER/repo.git
      git@github.com:OWNER/repo
      https://github.com/OWNER/repo.git
      https://github.com/OWNER/repo
      ssh://git@host/OWNER/repo.git
      https://gitlab.example.com/OWNER/repo.git
    """
    if not url:
        return None
    # SSH form: git@host:OWNER/repo(.git)?
    m = re.match(r"^[^@]+@[^:]+:([^/]+)/", url)
    if m:
        return m.group(1)
    # HTTPS or ssh:// form: <scheme>://[user@]host/OWNER/repo(.git)?
    m = re.match(r"^[a-z]+://(?:[^@/]+@)?[^/]+/([^/]+)/", url)
    if m:
        return m.group(1)
    return None


def parse_namespaces_md(namespaces_md: pathlib.Path) -> tuple[dict[str, str], list[tuple[str, str]], str]:
    """Parse namespaces.md.

    Returns:
      (owner_map, cwd_patterns, default)
        owner_map: {git_owner: namespace}
        cwd_patterns: [(glob_pattern, namespace)]
        default: namespace string
    """
    owner_map: dict[str, str] = {}
    cwd_patterns: list[tuple[str, str]] = []
    default = "personal"

    if not namespaces_md.is_file():
        return owner_map, cwd_patterns, default

    current_block: str | None = None  # "owner" | "cwd" | None

    for line in namespaces_md.read_text().splitlines():
        stripped = line.strip()

        # Top-level keys
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

        # End of block: top-level non-indented line that's a markdown header etc.
        if line and not line[0].isspace() and stripped and not stripped.startswith("#"):
            current_block = None
            continue
        if not stripped or stripped.startswith("#"):
            continue

        # Parse entry
        if current_block == "owner":
            # owner_name: namespace
            m = re.match(r"^([a-zA-Z0-9_.-]+)\s*:\s*([a-zA-Z_]+)\s*$", stripped)
            if m:
                owner_map[m.group(1)] = m.group(2)
        elif current_block == "cwd":
            # "pattern": namespace
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
    # 1. git owner
    if git_owner and git_owner in owner_map:
        return owner_map[git_owner]

    # 2. cwd pattern
    for pattern, ns in cwd_patterns:
        prefix = pattern
        if prefix.endswith("/**"):
            prefix = prefix[:-3]
        elif prefix.endswith("**"):
            prefix = prefix[:-2]
        if cwd == prefix or cwd.startswith(prefix.rstrip("/") + "/"):
            return ns

    # 3. default
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


def _short_input(input_obj: dict, max_len: int = 100) -> str:
    """Compact one-line representation of tool_use input."""
    s = json.dumps(input_obj, ensure_ascii=False, separators=(",", ":"))
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _format_user_content(content) -> str:
    """Convert a user message's content to compact markdown."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text", "").strip()
            if text:
                parts.append(text)
        elif btype == "tool_result":
            raw = block.get("content", "")
            if isinstance(raw, list):
                raw = " ".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in raw
                )
            text = str(raw).strip()
            if len(text) <= 200:
                parts.append(f"[tool result: {text}]")
            else:
                parts.append(f"[tool result: {len(text)} chars omitted]")
    return "\n".join(parts).strip()


def _format_assistant_content(content) -> str:
    """Convert an assistant message's content to compact markdown."""
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text", "").strip()
            if text:
                parts.append(text)
        elif btype == "tool_use":
            name = block.get("name", "?")
            short = _short_input(block.get("input", {}))
            parts.append(f"[tool: {name}({short})]")
        # thinking: skip for token savings
    return "\n".join(parts).strip()


def transcript_from_jsonl(jsonl_path: pathlib.Path, max_chars: int = 80_000) -> str:
    """Read a transcript JSONL file and produce compact markdown.

    Returns empty string if the file is missing or unreadable.
    """
    if not jsonl_path.is_file():
        return ""

    blocks: list[tuple[str, str]] = []  # (role, text)
    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = obj.get("type")
                if t not in ("user", "assistant"):
                    continue
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    text = _format_user_content(content)
                elif role == "assistant":
                    text = _format_assistant_content(content)
                else:
                    continue
                if text:
                    blocks.append((role, text))
    except OSError:
        return ""

    # Coalesce: combine same-role consecutive blocks
    out_lines: list[str] = []
    last_role: str | None = None
    for role, text in blocks:
        if role != last_role:
            header = "## User" if role == "user" else "## Assistant"
            out_lines.append(f"\n{header}\n")
            last_role = role
        out_lines.append(text)
        out_lines.append("")

    md = "\n".join(out_lines).strip()

    # Truncate if too long
    if len(md) > max_chars:
        half = max_chars // 2
        md = md[:half] + "\n\n[... middle truncated ...]\n\n" + md[-half:]
    return md


def log_invocation(payload: dict, result: str, transcript_stat: str = "") -> None:
    """Append a one-line diagnostic record to ~/.cache/llm-wiki/hook.log.

    Never raises — logging failure must not break the hook itself.
    """
    try:
        log_dir = pathlib.Path.home() / ".cache" / "llm-wiki"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        keys = sorted(payload.keys()) if isinstance(payload, dict) else []
        keys_str = ",".join(keys) if keys else "<none>"
        event = payload.get("hook_event_name", "?") if isinstance(payload, dict) else "?"
        reason = payload.get("reason", "?") if isinstance(payload, dict) else "?"
        agent_type = payload.get("agent_type", "-") if isinstance(payload, dict) else "-"
        source = payload.get("source", "-") if isinstance(payload, dict) else "-"
        sid_raw = payload.get("session_id", "") if isinstance(payload, dict) else ""
        sid = sid_raw[:8] if isinstance(sid_raw, str) else "?"
        fields = (
            f"event={event} reason={reason} source={source} agent_type={agent_type} sid={sid} "
            f"keys=[{keys_str}]"
        )
        if transcript_stat:
            fields += f" {transcript_stat}"
        with (log_dir / "hook.log").open("a", encoding="utf-8") as f:
            f.write(f"{ts} {fields} → {result}\n")
    except OSError:
        pass


def stat_transcript(path_str: str) -> str:
    """Return a one-token summary of the transcript file at path_str.

    Format: file=missing | file=size=<N>,lines=<L>,types=<t1:n1+t2:n2>,mtime=<iso>
    Safe on any path — never raises.
    """
    if not path_str:
        return "file=none"
    try:
        p = pathlib.Path(path_str)
        if not p.is_file():
            return "file=missing"
        size = p.stat().st_size
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
        lines = 0
        type_counts: dict[str, int] = {}
        with p.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                lines += 1
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(obj, dict):
                    t = obj.get("type", "?")
                    type_counts[t] = type_counts.get(t, 0) + 1
        types_str = "+".join(f"{k}:{v}" for k, v in sorted(type_counts.items())) or "none"
        return f"file=size={size},lines={lines},types={types_str},mtime={mtime}"
    except OSError:
        return "file=stat-error"


def main() -> int:
    # Read stdin first so we can log payload shape on every code path
    raw = sys.stdin.read()
    payload: dict = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = parsed
        except (json.JSONDecodeError, ValueError):
            log_invocation({}, f"skip:malformed-json size={len(raw)}")
            return 0

    vault = get_vault_path()
    if vault is None:
        log_invocation(payload, "skip:no-vault-configured")
        return 0

    sessions_dir = vault / "sources" / "claude-sessions"
    if not sessions_dir.is_dir():
        log_invocation(payload, f"skip:no-sessions-dir vault={vault}")
        return 0

    session_id = payload.get("session_id", "unknown")
    cwd = payload.get("cwd", "")

    # Primary: read transcript from transcript_path (Claude Code's actual input format)
    transcript_path = payload.get("transcript_path", "")
    transcript = ""
    if transcript_path:
        transcript = transcript_from_jsonl(pathlib.Path(transcript_path))
    # Fallback: direct transcript field (used by tests)
    if not transcript:
        transcript = payload.get("transcript", "")

    if len(transcript.strip()) < 50:
        log_invocation(
            payload,
            f"skip:trivial-transcript transcript_len={len(transcript.strip())}",
            transcript_stat=stat_transcript(transcript_path),
        )
        return 0

    # Extract git info from cwd
    git_remote, git_owner = get_git_info(cwd)

    # Parse namespaces.md and decide
    owner_map, cwd_patterns, default = parse_namespaces_md(vault / "schema" / "namespaces.md")
    namespace = determine_namespace(cwd, git_owner, owner_map, cwd_patterns, default)

    today = datetime.date.today().isoformat()
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    cwd_basename = pathlib.Path(cwd).name if cwd else "session"
    slug = slugify(cwd_basename)
    session_prefix = session_id[:8] if session_id else "unknown"
    filename = f"{today}-{slug}-{session_prefix}.md"

    # Optional git frontmatter lines
    git_lines = ""
    if git_remote:
        git_lines += f"git_remote: {yaml_quote(git_remote)}\n"
    if git_owner:
        git_lines += f"git_owner: {yaml_quote(git_owner)}\n"

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
{git_lines}---

# Claude session: {cwd_basename}

{transcript}
"""

    out_path = sessions_dir / filename
    out_path.write_text(content)
    try:
        rel = out_path.relative_to(vault)
    except ValueError:
        rel = out_path
    log_invocation(payload, f"wrote:{rel} ns={namespace} transcript_len={len(transcript)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
