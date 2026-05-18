#!/usr/bin/env python3
"""Validate that a schema/ directory has the 6 required files and basic structure."""
import sys
from pathlib import Path

REQUIRED = {
    "README.md", "page-types.md", "relations.md",
    "namespaces.md", "ingest-rules.md", "lint-rules.md",
}

def main():
    if len(sys.argv) < 2:
        print("usage: validate-schema.py <schema-dir> [--list]", file=sys.stderr)
        return 2

    schema_dir = Path(sys.argv[1])
    list_mode = "--list" in sys.argv[2:]

    if not schema_dir.is_dir():
        print(f"not a directory: {schema_dir}", file=sys.stderr)
        return 1

    found = {p.name for p in schema_dir.iterdir() if p.is_file() and p.suffix == ".md"}

    if list_mode:
        for name in sorted(found):
            print(name)
        return 0

    missing = REQUIRED - found
    if missing:
        for m in sorted(missing):
            print(f"missing: {m}", file=sys.stderr)
        return 1

    for name in REQUIRED:
        if (schema_dir / name).stat().st_size == 0:
            print(f"empty: {name}", file=sys.stderr)
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
