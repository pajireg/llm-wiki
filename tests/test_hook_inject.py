"""Tests for hooks/user-prompt-inject.py — successful injection paths."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOK_SCRIPT = PLUGIN_ROOT / "hooks" / "user-prompt-inject.py"
REBUILD_SCRIPT = PLUGIN_ROOT / "scripts" / "rebuild-index.py"


def make_vault(tmp_path: Path, namespaces_md: str | None = None) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki" / "tech").mkdir(parents=True)
    (vault / "wiki" / "personal").mkdir(parents=True)
    (vault / "schema").mkdir(parents=True)
    if namespaces_md is None:
        namespaces_md = (
            "git_owner_to_namespace:\n"
            "  acme-corp: work\n"
            "\n"
            "cwd_to_namespace:\n"
            "\n"
            "default: personal\n"
        )
    (vault / "schema" / "namespaces.md").write_text(namespaces_md)
    return vault


def write_page(vault: Path, rel: str, fm: dict, body: str) -> Path:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
    lines.append("---")
    content = "\n".join(lines) + "\n\n" + body
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def build_index(vault: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(REBUILD_SCRIPT), str(vault)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def configure_home(tmp_path: Path, vault: Path) -> Path:
    home = tmp_path / "home"
    config = home / ".config" / "llm-wiki"
    config.mkdir(parents=True)
    (config / "vault-path").write_text(str(vault))
    return home


def run_hook(home: Path, payload: dict, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("LLM_WIKI_AUTO_INJECT", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )


def test_emits_wiki_context_block_for_matching_prompt(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/ssh.md", {
        "type": "topic", "namespace": "personal",
        "summary": "SSH key rotation policy and ed25519 migration.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# SSH\n\nbody")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {
        "session_id": "s",
        "cwd": str(tmp_path),
        "prompt": "remind me how I set up SSH key rotation",
    })
    assert result.returncode == 0, result.stderr
    assert "<wiki_context" in result.stdout
    assert "[[ssh]]" in result.stdout
    assert "ed25519" in result.stdout
    assert "wiki/personal/ssh.md" in result.stdout


def test_korean_prompt_matches_korean_summary(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/keys.md", {
        "type": "topic", "namespace": "personal",
        "summary": "암호화 키 로테이션 90일 주기 권장.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Keys\n\n키 관리 정책.")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {
        "session_id": "s",
        "cwd": str(tmp_path),
        "prompt": "키 로테이션 주기가 어떻게 되지?",
    })
    assert result.returncode == 0, result.stderr
    assert "[[keys]]" in result.stdout
    assert "로테이션" in result.stdout


def test_namespace_filter_prefers_current_namespace(tmp_path):
    vault = make_vault(tmp_path, namespaces_md=(
        "git_owner_to_namespace:\n"
        "  acme-corp: work\n"
        "\n"
        "cwd_to_namespace:\n"
        f'  "{tmp_path}/work-area/**": work\n'
        "\n"
        "default: personal\n"
    ))
    (vault / "wiki" / "work").mkdir(parents=True)
    write_page(vault, "wiki/work/sprint.md", {
        "type": "topic", "namespace": "work",
        "summary": "Sprint planning rituals for the team.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    write_page(vault, "wiki/personal/sprint.md", {
        "type": "note", "namespace": "personal",
        "summary": "Personal note about running sprints.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    cwd_work = tmp_path / "work-area"
    cwd_work.mkdir()
    result = run_hook(home, {
        "session_id": "s",
        "cwd": str(cwd_work),
        "prompt": "sprint planning",
    })
    assert result.returncode == 0
    assert 'namespace="work"' in result.stdout
    assert 'scope="work"' in result.stdout
    # personal page should NOT leak in when work matches
    assert "wiki/personal/sprint.md" not in result.stdout


def test_falls_back_to_full_vault_when_namespace_empty(tmp_path):
    vault = make_vault(tmp_path, namespaces_md=(
        "git_owner_to_namespace:\n"
        "\n"
        "cwd_to_namespace:\n"
        f'  "{tmp_path}/work-area/**": work\n'
        "\n"
        "default: personal\n"
    ))
    write_page(vault, "wiki/personal/ssh.md", {
        "type": "topic", "namespace": "personal",
        "summary": "SSH key rotation.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    cwd_work = tmp_path / "work-area"
    cwd_work.mkdir()
    result = run_hook(home, {
        "session_id": "s",
        "cwd": str(cwd_work),
        "prompt": "ssh rotation",
    })
    assert result.returncode == 0
    assert 'namespace="work"' in result.stdout
    assert 'scope="all"' in result.stdout
    assert "[[ssh]]" in result.stdout


def test_no_match_produces_no_output(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/diet.md", {
        "type": "note", "namespace": "personal",
        "summary": "Daily nutrition tracking.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {
        "session_id": "s",
        "cwd": str(tmp_path),
        "prompt": "kubernetes pod autoscaling",
    })
    assert result.returncode == 0
    assert result.stdout == ""


def test_special_chars_in_prompt_are_sanitized(tmp_path):
    vault = make_vault(tmp_path)
    write_page(vault, "wiki/personal/ssh.md", {
        "type": "topic", "namespace": "personal",
        "summary": "SSH key rotation.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "body")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    # FTS5 reserved chars: ", *, :, (, ), ^
    result = run_hook(home, {
        "session_id": "s",
        "cwd": str(tmp_path),
        "prompt": 'SSH rotation: how does it work? "ed25519" * (key) ^command',
    })
    assert result.returncode == 0, result.stderr
    assert "[[ssh]]" in result.stdout


def test_alias_match_outranks_body_only_match(tmp_path):
    vault = make_vault(tmp_path)
    # Page A: the query term "쿠버네티스" lives only in aliases.
    write_page(vault, "wiki/tech/k8s.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Orchestration platform overview.",
        "aliases": ["쿠버네티스"],
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Kubernetes\n\nGeneric platform notes.")
    # Page B: the query term appears once, buried in the body.
    write_page(vault, "wiki/tech/notes.md", {
        "type": "topic", "namespace": "tech",
        "summary": "Assorted infra notes.",
        "created": "2026-05-01", "updated": "2026-05-01",
    }, "# Notes\n\nWe also mention 쿠버네티스 once here in passing.")
    build_index(vault)
    home = configure_home(tmp_path, vault)

    result = run_hook(home, {"prompt": "쿠버네티스 설정 방법", "cwd": str(vault)})

    assert result.returncode == 0
    out = result.stdout
    assert "[[k8s]]" in out and "[[notes]]" in out
    # The alias-weighted page must be listed before the body-only page.
    assert out.index("[[k8s]]") < out.index("[[notes]]")
