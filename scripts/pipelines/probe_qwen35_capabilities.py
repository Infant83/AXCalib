"""Run a live, provider-independent Qwen3.5 text/vision capability probe."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from axcalib.dossier import atomic_write_text  # noqa: E402
from axcalib.models import (  # noqa: E402
    DEFAULT_QWEN35_CHECKPOINT,
    CapabilityProbeScope,
    probe_qwen35_from_env,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe an OpenAI-compatible Qwen3.5 route using only canonical OPENAI_* "
            "environment variables."
        )
    )
    parser.add_argument(
        "--expected-checkpoint",
        default=DEFAULT_QWEN35_CHECKPOINT,
        help="Exact deployment checkpoint expected in endpoint model metadata.",
    )
    parser.add_argument(
        "--scope",
        choices=tuple(item.value for item in CapabilityProbeScope),
        default=CapabilityProbeScope.DEPLOYMENT.value,
        help="provider_proxy validates capabilities but can never establish deployment readiness.",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Skip the synthetic vision probe; deployment readiness remains false.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optionally atomically write the secret-free JSON report.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = probe_qwen35_from_env(
            os.environ,
            expected_checkpoint=args.expected_checkpoint,
            validation_scope=CapabilityProbeScope(args.scope),
            include_vision=not args.text_only,
        )
    except ValueError as error:
        print(f"qwen capability probe configuration error: {error}", file=sys.stderr)
        return 2
    content = report.model_dump_json(indent=2) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        atomic_write_text(output, content)
    print(content, end="")
    return 0 if report.scope_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
