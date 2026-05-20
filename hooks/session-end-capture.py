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
import sys

from _wiki_common import (
    determine_namespace,
    get_git_info,
    get_vault_path,
    parse_namespaces_md,
    slugify,
    yaml_quote,
)


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
    return "\n".join(parts).strip()


def transcript_from_jsonl(jsonl_path: pathlib.Path, max_chars: int = 80_000) -> str:
    """Read a transcript JSONL file and produce compact markdown.

    Returns empty string if the file is missing or unreadable.
    """
    if not jsonl_path.is_file():
        return ""

    blocks: list[tuple[str, str]] = []
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
    """Return a one-token summary of the transcript file at path_str."""
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

    transcript_path = payload.get("transcript_path", "")
    transcript = ""
    if transcript_path:
        transcript = transcript_from_jsonl(pathlib.Path(transcript_path))
    if not transcript:
        transcript = payload.get("transcript", "")

    if len(transcript.strip()) < 50:
        log_invocation(
            payload,
            f"skip:trivial-transcript transcript_len={len(transcript.strip())}",
            transcript_stat=stat_transcript(transcript_path),
        )
        return 0

    git_remote, git_owner = get_git_info(cwd)

    owner_map, cwd_patterns, default = parse_namespaces_md(vault / "schema" / "namespaces.md")
    namespace = determine_namespace(cwd, git_owner, owner_map, cwd_patterns, default)

    today = datetime.date.today().isoformat()
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    cwd_basename = pathlib.Path(cwd).name if cwd else "session"
    slug = slugify(cwd_basename)
    session_prefix = session_id[:8] if session_id else "unknown"
    filename = f"{today}-{slug}-{session_prefix}.md"

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
