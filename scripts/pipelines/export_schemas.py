"""Export or check AXCalib JSON Schema artifacts through the library helper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib.schemas.export import export_schema_artifacts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    errors = export_schema_artifacts(ROOT / "docs" / "schemas", check=args.check)
    for error in errors:
        print(f"ERROR: {error}")
    if not errors:
        print("schema artifacts: OK" if args.check else "schema artifacts: exported")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
