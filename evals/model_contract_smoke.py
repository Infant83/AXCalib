"""Validate external and on-prem model configuration contracts without a live call."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axcalib.models import ModelApiMode, ModelEndpointConfig  # noqa: E402


def main() -> int:
    external = ModelEndpointConfig.from_env(
        {"OPENAI_API_KEY": "present-but-not-used"},
        live=False,
    )
    onprem = ModelEndpointConfig.from_env(
        {
            "OPENAI_API_KEY": "present-but-not-used",
            "OPENAI_BASE_URL": "http://qwen.internal.example/v1",
            "OPENAI_MODEL": "Qwen3.5-397B-A17B",
            "OPENAI_STRUCTURED_OUTPUT_MODE": "json_object",
            "OPENAI_MAX_OUTPUT_TOKENS": "8192",
        },
        live=False,
    )
    checks = {
        "external_default_model": external.model == "gpt-5.5",
        "external_responses_mode": external.api_mode is ModelApiMode.RESPONSES,
        "onprem_model_injected": onprem.model == "Qwen3.5-397B-A17B",
        "onprem_chat_completions_mode": (
            onprem.api_mode is ModelApiMode.CHAT_COMPLETIONS
        ),
        "onprem_explicit_json_object_mode": (
            onprem.structured_output_mode.value == "json_object"
        ),
        "onprem_explicit_output_limit": onprem.max_output_tokens == 8192,
        "declared_multimodal_structured_capabilities": set(onprem.capabilities)
        == {"text", "image", "structured_output"},
    }
    output = {
        "mode": "configuration_and_mock_transport_contract",
        "live_model_used": False,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "quality_claim": (
            "environment routing and declared-capability smoke only; no endpoint, "
            "Qwen behavior, latency, cost, or model-quality claim"
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if output["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
