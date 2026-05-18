import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = PLUGIN_ROOT / "scripts" / "validate-schema.py"
TEMPLATES = PLUGIN_ROOT / "templates" / "schema"

def test_validate_schema_exits_zero_for_template():
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(TEMPLATES)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

def test_validate_schema_lists_all_six_files():
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(TEMPLATES), "--list"],
        capture_output=True, text=True,
    )
    expected = {"README.md", "page-types.md", "relations.md",
                "namespaces.md", "ingest-rules.md", "lint-rules.md"}
    found = set(result.stdout.strip().splitlines())
    assert found == expected, f"missing: {expected - found}"
