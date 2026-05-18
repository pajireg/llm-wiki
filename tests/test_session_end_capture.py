"""Tests for session-end-capture.py."""
import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOK_SCRIPT = PLUGIN_ROOT / "hooks" / "session-end-capture.py"


def make_vault(tmp_path: Path, namespaces_content: str = None) -> Path:
    """Create a minimal vault structure under tmp_path/vault."""
    vault = tmp_path / "vault"
    (vault / "sources" / "claude-sessions").mkdir(parents=True)
    (vault / "schema").mkdir(parents=True)
    if namespaces_content is None:
        namespaces_content = (
            "cwd_to_namespace:\n"
            '  "/test/projects/**": tech\n'
            "  default: personal\n"
        )
    (vault / "schema" / "namespaces.md").write_text(namespaces_content)
    return vault


def write_vault_config(tmp_path: Path, vault: Path) -> Path:
    """Write a temporary HOME with vault-path config pointing to vault."""
    fake_home = tmp_path / "home"
    config_dir = fake_home / ".config" / "llm-wiki"
    config_dir.mkdir(parents=True)
    (config_dir / "vault-path").write_text(str(vault))
    return fake_home


def run_hook(vault: Path, payload: dict, tmp_path: Path = None, configure_vault: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    # Strip any inherited LLM_WIKI_VAULT to ensure tests don't accidentally use it
    env.pop("LLM_WIKI_VAULT", None)
    if configure_vault and tmp_path is not None:
        fake_home = write_vault_config(tmp_path, vault)
        env["HOME"] = str(fake_home)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def list_captured(vault: Path) -> list[Path]:
    return sorted((vault / "sources" / "claude-sessions").glob("*.md"))


def test_writes_file_with_required_frontmatter(tmp_path):
    vault = make_vault(tmp_path)
    payload = {
        "session_id": "test-session-123abc",
        "cwd": "/test/projects/foo",
        "transcript": "user: hello\nassistant: hi there, this is enough text to pass the trivial filter",
    }
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0, result.stderr

    files = list_captured(vault)
    assert len(files) == 1
    content = files[0].read_text()
    assert "type: source" in content
    assert "source_type: claude_session" in content
    assert "namespace: tech" in content  # matched /test/projects/**
    assert "processed: false" in content
    assert 'session_id: "test-session-123abc"' in content
    assert 'cwd: "/test/projects/foo"' in content


def test_default_namespace_when_no_match(tmp_path):
    vault = make_vault(tmp_path)
    payload = {
        "session_id": "abc456def",
        "cwd": "/random/elsewhere",
        "transcript": "long enough transcript content to pass the trivial-session filter without issue",
    }
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0, result.stderr

    files = list_captured(vault)
    assert len(files) == 1
    assert "namespace: personal" in files[0].read_text()


def test_skips_when_vault_path_not_configured(tmp_path):
    vault = make_vault(tmp_path)
    # Do not configure vault (no HOME config file)
    result = run_hook(vault, {"session_id": "x", "cwd": "/x", "transcript": "x" * 100}, tmp_path, configure_vault=False)
    assert result.returncode == 0
    assert list_captured(vault) == []


def test_skips_trivial_transcript(tmp_path):
    vault = make_vault(tmp_path)
    payload = {
        "session_id": "x",
        "cwd": "/test/projects/foo",
        "transcript": "ls",  # < 50 chars
    }
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0
    assert list_captured(vault) == []


def test_skips_when_sessions_dir_missing(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    # No sources/claude-sessions/, no schema/
    payload = {"session_id": "x", "cwd": "/y", "transcript": "x" * 100}
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0


def test_filename_uses_date_and_slug(tmp_path):
    vault = make_vault(tmp_path)
    payload = {
        "session_id": "1234567890abcdef",
        "cwd": "/test/projects/my-cool-project",
        "transcript": "x" * 100,
    }
    run_hook(vault, payload, tmp_path)
    files = list_captured(vault)
    assert len(files) == 1
    name = files[0].name
    assert "my-cool-project" in name
    assert "12345678" in name  # session_id prefix
    assert name.endswith(".md")
