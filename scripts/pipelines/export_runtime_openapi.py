"""Export the deterministic implemented runtime OpenAPI contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from axcalib import AXCalib
from axcalib.api import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/api/openapi.runtime.v1alpha1.json"),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("output/openapi-export"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    schema = create_app(AXCalib(args.workspace)).openapi()
    content = json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
