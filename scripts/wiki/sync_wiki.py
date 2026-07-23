"""Validate, export, or explicitly publish the portable AXCalib Wiki."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.wiki import (  # noqa: E402
    DEFAULT_REMOTE_ENV,
    SUPPORTED_TARGETS,
    WikiError,
    WikiTarget,
    export_wiki,
    publish_wiki,
    validate_wiki,
)


def _target(value: str) -> WikiTarget:
    if value not in SUPPORTED_TARGETS:
        raise argparse.ArgumentTypeError(f"target must be one of {', '.join(SUPPORTED_TARGETS)}")
    return value  # type: ignore[return-value]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate the canonical Wiki without writing files")

    export = subparsers.add_parser("export", help="render one target into a local directory")
    export.add_argument("--target", type=_target, required=True)
    export.add_argument("--output", type=Path, required=True)

    publish = subparsers.add_parser(
        "publish", help="clone/fetch a Wiki and prepare a dry-run or explicit push"
    )
    publish.add_argument("--target", type=_target, required=True)
    publish.add_argument(
        "--remote-url-env",
        help="environment variable holding the remote URL; defaults per target",
    )
    publish.add_argument("--checkout", type=Path, required=True)
    publish.add_argument(
        "--push",
        action="store_true",
        help="commit and push; omitted means dry-run only",
    )
    publish.add_argument("--message", help="optional Wiki commit message")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_wiki(ROOT)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}")
                print(f"wiki validate: FAILED ({len(errors)} error(s))")
                return 1
            print("wiki validate: PASSED (0 errors)")
            return 0
        if args.command == "export":
            result = export_wiki(ROOT, args.target, args.output.resolve())
            print(
                f"wiki export: {result.target} {len(result.managed_files)} managed files "
                f"at {result.output_dir}"
            )
            return 0

        remote_env = args.remote_url_env or DEFAULT_REMOTE_ENV[args.target]
        remote_url = os.environ.get(remote_env, "")
        if not remote_url:
            print(f"ERROR: required Wiki remote environment variable is not set: {remote_env}")
            return 2
        result = publish_wiki(
            ROOT,
            args.target,
            remote_url,
            args.checkout.resolve(),
            push=args.push,
            commit_message=args.message,
        )
        mode = "pushed" if result.pushed else "dry-run"
        print(
            f"wiki publish: {result.target} {mode}; changed={result.changed}; "
            f"files={len(result.change_lines)}"
        )
        return 0
    except WikiError as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
