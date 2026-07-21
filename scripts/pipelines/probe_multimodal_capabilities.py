"""Probe any approved OpenAI-compatible multimodal model route."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from axcalib.dossier import atomic_write_text  # noqa: E402
from axcalib.models import (  # noqa: E402
    CapabilityProbeScope,
    ModelEndpointConfig,
    MultimodalCapabilityProbe,
    OpenAICompatibleClient,
)

REQUIRED_ENVIRONMENT = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")


def _build_client(environ: Mapping[str, str]) -> OpenAICompatibleClient:
    missing = [name for name in REQUIRED_ENVIRONMENT if not environ.get(name)]
    if missing:
        names = ", ".join(missing)
        raise ValueError(
            f"live multimodal probe requires explicit environment variables: {names}"
        )
    config = ModelEndpointConfig.from_env(environ, live=True)
    return OpenAICompatibleClient(config, api_key=environ["OPENAI_API_KEY"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe structured text and synthetic vision through canonical OPENAI_* "
            "environment variables without binding AXCalib to a provider."
        )
    )
    parser.add_argument(
        "--expected-model",
        help=(
            "Exact deployment model expected in endpoint metadata. Required when "
            "--scope deployment is selected."
        ),
    )
    parser.add_argument(
        "--scope",
        choices=tuple(item.value for item in CapabilityProbeScope),
        default=CapabilityProbeScope.PROVIDER_PROXY.value,
        help="provider_proxy is the safe default and never establishes deployment readiness.",
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
        client = _build_client(os.environ)
        scope = CapabilityProbeScope(args.scope)
        if scope is CapabilityProbeScope.DEPLOYMENT and not args.expected_model:
            raise ValueError("--expected-model is required for deployment scope")
        probe = MultimodalCapabilityProbe(
            client,
            expected_checkpoint=args.expected_model or client.config.model,
            validation_scope=scope,
        )
        report = probe.run(include_vision=not args.text_only)
    except ValueError as error:
        print(f"multimodal capability probe configuration error: {error}", file=sys.stderr)
        return 2
    content = report.model_dump_json(indent=2) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        atomic_write_text(output, content)
    print(content, end="")
    return 0 if report.scope_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
