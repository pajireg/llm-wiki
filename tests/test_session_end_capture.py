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
            "git_owner_to_namespace:\n"
            "  pajireg: personal\n"
            "  acme-corp: work\n"
            "\n"
            "cwd_to_namespace:\n"
            '  "/test/projects/**": tech\n'
            "\n"
            "default: personal\n"
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


def make_jsonl_transcript(tmp_path: Path, messages: list) -> Path:
    """Create a JSONL transcript file from a list of (role, text) tuples.

    Also includes some metadata lines that should be filtered out.
    """
    path = tmp_path / "transcript.jsonl"
    lines = [
        json.dumps({"type": "last-prompt", "leafUuid": "x", "sessionId": "s"}),
        json.dumps({"type": "permission-mode", "permissionMode": "default", "sessionId": "s"}),
        json.dumps({"type": "file-history-snapshot", "messageId": "x", "snapshot": {}, "isSnapshotUpdate": False}),
    ]
    for role, text in messages:
        if role == "user":
            lines.append(json.dumps({
                "type": "user",
                "message": {"role": "user", "content": text},
            }))
        elif role == "assistant":
            lines.append(json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": text}],
                },
            }))
        elif role == "tool_use":
            # text is "tool_name|json_input"
            name, _, inp = text.partition("|")
            lines.append(json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{
                        "type": "tool_use",
                        "name": name,
                        "input": json.loads(inp) if inp else {},
                        "id": "id1",
                    }],
                },
            }))
    path.write_text("\n".join(lines) + "\n")
    return path


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


def test_namespace_from_git_owner(tmp_path):
    """Cwd is a git repo with remote pointing to pajireg/llm-wiki → personal."""
    vault = make_vault(tmp_path)

    # Set up a fake git repo at a controlled path
    repo = tmp_path / "fakerepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:pajireg/llm-wiki.git"],
        cwd=repo, check=True,
    )

    payload = {
        "session_id": "test-git-owner",
        "cwd": str(repo),
        "transcript": "x" * 100,
    }
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0, result.stderr

    files = list_captured(vault)
    assert len(files) == 1
    content = files[0].read_text()
    assert "namespace: personal" in content   # matched git_owner: pajireg
    assert "git_owner:" in content
    assert "pajireg" in content
    assert "git_remote:" in content


def test_namespace_git_owner_unmapped_falls_back_to_default(tmp_path):
    """Git remote owner not in mapping → default namespace, but git info still recorded."""
    vault = make_vault(tmp_path)

    repo = tmp_path / "fakerepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/someother-org/somerepo"],
        cwd=repo, check=True,
    )

    payload = {
        "session_id": "test-unmapped",
        "cwd": str(repo),
        "transcript": "x" * 100,
    }
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0, result.stderr

    files = list_captured(vault)
    content = files[0].read_text()
    assert "namespace: personal" in content   # fell to default
    assert "git_owner:" in content
    assert "someother-org" in content


def test_parse_git_owner_handles_ssh_and_https():
    """Unit test for parse_git_owner helper via import."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "session_end_capture",
        str(PLUGIN_ROOT / "hooks" / "session-end-capture.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.parse_git_owner("git@github.com:pajireg/llm-wiki.git") == "pajireg"
    assert mod.parse_git_owner("git@github.com:acme-corp/repo") == "acme-corp"
    assert mod.parse_git_owner("https://github.com/pajireg/llm-wiki.git") == "pajireg"
    assert mod.parse_git_owner("https://github.com/pajireg/llm-wiki") == "pajireg"
    assert mod.parse_git_owner("https://gitlab.example.com/team-a/repo.git") == "team-a"
    assert mod.parse_git_owner("ssh://git@github.com/pajireg/llm-wiki.git") == "pajireg"
    assert mod.parse_git_owner("") is None
    assert mod.parse_git_owner("not-a-url") is None


# ── New tests: transcript_path / JSONL parsing ──────────────────────────────


def test_reads_transcript_from_transcript_path(tmp_path):
    """transcript_path가 JSONL 파일을 가리키고, 그 내용이 압축 마크다운으로 변환되어 캡처됨."""
    vault = make_vault(tmp_path)
    jsonl = make_jsonl_transcript(tmp_path, [
        ("user", "Hello there, please help me with X."),
        ("assistant", "Sure, let me look into that for you."),
        ("user", "Thanks!"),
    ])
    payload = {
        "session_id": "tp-test",
        "cwd": "/test/projects/foo",
        "transcript_path": str(jsonl),
        "hook_event_name": "SessionEnd",
    }
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0, result.stderr

    files = list_captured(vault)
    assert len(files) == 1
    body = files[0].read_text()
    # Compressed markdown markers
    assert "## User" in body
    assert "## Assistant" in body
    assert "Hello there" in body
    assert "Sure, let me look" in body


def test_tool_use_compressed_to_one_line(tmp_path):
    """assistant의 tool_use 블록은 한 줄 요약으로 변환되어야 함."""
    vault = make_vault(tmp_path)
    jsonl = make_jsonl_transcript(tmp_path, [
        ("user", "Read foo.txt please. This is enough text to pass the trivial filter."),
        ("tool_use", "Read|{\"file_path\": \"/tmp/foo.txt\"}"),
        ("assistant", "Here are the contents."),
    ])
    payload = {
        "session_id": "tu-test",
        "cwd": "/test/projects/foo",
        "transcript_path": str(jsonl),
        "hook_event_name": "SessionEnd",
    }
    result = run_hook(vault, payload, tmp_path)
    assert result.returncode == 0, result.stderr

    body = list_captured(vault)[0].read_text()
    assert "[tool: Read(" in body
    assert "/tmp/foo.txt" in body


def test_metadata_lines_filtered_out(tmp_path):
    """last-prompt, permission-mode 등 메타 라인은 결과에 포함되지 않음."""
    vault = make_vault(tmp_path)
    jsonl = make_jsonl_transcript(tmp_path, [
        ("user", "real message that should appear in output, long enough for trivial filter"),
    ])
    payload = {
        "session_id": "meta-test",
        "cwd": "/test/projects/foo",
        "transcript_path": str(jsonl),
        "hook_event_name": "SessionEnd",
    }
    result = run_hook(vault, payload, tmp_path)
    body = list_captured(vault)[0].read_text()
    assert "last-prompt" not in body
    assert "permission-mode" not in body
    assert "file-history-snapshot" not in body
    assert "real message" in body


def test_truncation_for_huge_transcript(tmp_path):
    """80k자 초과면 head + 'middle truncated' + tail."""
    vault = make_vault(tmp_path)
    big_text = "X" * 50_000
    jsonl = make_jsonl_transcript(tmp_path, [
        ("user", big_text),
        ("assistant", big_text),
    ])
    payload = {
        "session_id": "trunc-test",
        "cwd": "/test/projects/foo",
        "transcript_path": str(jsonl),
        "hook_event_name": "SessionEnd",
    }
    result = run_hook(vault, payload, tmp_path)
    body = list_captured(vault)[0].read_text()
    assert "middle truncated" in body
