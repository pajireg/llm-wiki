"""Tests for hooks/user-prompt-inject.py — safety / error paths.

Core invariant: every failure mode must exit 0 with empty stdout so the
user's prompt is never blocked.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOK_SCRIPT = PLUGIN_ROOT / "hooks" / "user-prompt-inject.py"
REBUILD_SCRIPT = PLUGIN_ROOT / "scripts" / "rebuild-index.py"


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki" / "personal").mkdir(parents=True)
    (vault / "schema").mkdir(parents=True)
    (vault / "schema" / "namespaces.md").write_text(
        "git_owner_to_namespace:\n\ncwd_to_namespace:\n\ndefault: personal\n"
    )
    return vault


def write_page(vault: Path, rel: str, fm: dict, body: str) -> Path:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    lines.append("---")
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n\n" + body)
    return path


def build_index(vault: Path) -> None:
    subprocess.run(
        [sys.executable, str(REBUILD_SCRIPT), str(vault)],
        capture_output=True, text=True, check=True,
    )


def configure_home(tmp_path: Path, vault: Path | None) -> Path:
    home = tmp_path / "home"
    config = home / ".config" / "llm-wiki"
    config.mkdir(parents=True)
    if vault is not None:
        (config / "vault-path").write_text(str(vault))
    return home


def run_hook(home: Path, payload, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("LLM_WIKI_AUTO_INJECT", None)
    if extra_env:
        env.update(extra_env)
    input_text = json.dumps(payload) if not isinstance(payload, str) else payload
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=input_text, capture_output=True, text=True, env=env,
    )


def test_no_vault_configured_exits_silently(tmp_path):
    home = configure_home(tmp_path, vault=None)
    result = run_hook(home, {"session_id": "s", "cwd": "/tmp", "prompt": "hello"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_disabled_file_skips_injection(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/p.md", {
        "type": "note", "namespace": "personal",
        "summary": "matching summary about ssh keys.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    (vault / ".llm-wiki" / "disabled").write_text("")
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {"session_id": "s", "cwd": str(tmp_path), "prompt": "ssh keys"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_env_var_disables_injection(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/p.md", {
        "type": "note", "namespace": "personal",
        "summary": "matching summary about ssh keys.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {"session_id": "s", "cwd": str(tmp_path), "prompt": "ssh keys"},
                      extra_env={"LLM_WIKI_AUTO_INJECT": "0"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_index_skips_injection(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/p.md", {
        "type": "note", "namespace": "personal",
        "summary": "S.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    # NOTE: do not build index
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {"session_id": "s", "cwd": str(tmp_path), "prompt": "anything"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_corrupt_index_exits_silently(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/p.md", {
        "type": "note", "namespace": "personal",
        "summary": "S.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    (vault / ".llm-wiki" / "index.db").write_bytes(b"corrupt junk")
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {"session_id": "s", "cwd": str(tmp_path), "prompt": "anything"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_bad_payload_exits_silently(tmp_path):
    home = configure_home(tmp_path, vault=None)
    result = run_hook(home, "not valid json {{{")
    assert result.returncode == 0
    assert result.stdout == ""


def test_empty_stdin_exits_silently(tmp_path):
    home = configure_home(tmp_path, vault=None)
    result = run_hook(home, "")
    assert result.returncode == 0
    assert result.stdout == ""


def test_empty_prompt_skips(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/p.md", {
        "type": "note", "namespace": "personal",
        "summary": "S.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {"session_id": "s", "cwd": str(tmp_path), "prompt": ""})
    assert result.returncode == 0
    assert result.stdout == ""


def test_missing_fields_in_payload(tmp_path):
    """Hook should tolerate missing cwd/session_id/prompt."""
    vault = make_vault(tmp_path)
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {})
    assert result.returncode == 0
    assert result.stdout == ""
