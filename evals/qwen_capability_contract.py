"""Evaluate Qwen capability identity boundaries without network access."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axcalib.models import (  # noqa: E402
    CapabilityProbeScope,
    ModelApiMode,
    ModelEndpointConfig,
    ModelGatewayResult,
    MultimodalCapabilityProbe,
    Qwen35CapabilityProbe,
)


class _DeterministicGateway:
    def __init__(self, requested_model: str, response_model: str) -> None:
        self.config = ModelEndpointConfig(
            profile_id="eval/qwen35-contract",
            base_url="http://qwen.internal.invalid/v1",
            model=requested_model,
            api_mode=ModelApiMode.CHAT_COMPLETIONS,
            live=False,
        )
        self.response_model = response_model

    def generate_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        json_schema: dict[str, Any],
        image_data_urls: tuple[str, ...] = (),
    ) -> ModelGatewayResult:
        del instructions, input_text, json_schema
        if schema_name.endswith("text_probe"):
            output = {
                "probe_token": "AXCALIB_MULTIMODAL_TEXT_OK",
                "structured_output": True,
            }
        else:
            assert image_data_urls and image_data_urls[0].startswith("data:image/png;base64,")
            output = {
                "left_panel": "red",
                "right_panel": "blue",
                "two_equal_panels": True,
            }
        return ModelGatewayResult(
            response_id="offline-eval",
            model=self.response_model,
            model_reported_by_endpoint=True,
            output_text=json.dumps(output),
            request_sha256="1" * 64,
            response_sha256="2" * 64,
            latency_ms=0,
        )


def main() -> int:
    exact = Qwen35CapabilityProbe(
        _DeterministicGateway("Qwen3.5-397B-A17B", "Qwen/Qwen3.5-397B-A17B"),
        expected_checkpoint="Qwen3.5-397B-A17B",
    ).run()
    proxy = Qwen35CapabilityProbe(
        _DeterministicGateway("bailian/qwen3.5-plus", "qwen3.5-plus"),
        expected_checkpoint="Qwen3.5-397B-A17B",
        validation_scope=CapabilityProbeScope.PROVIDER_PROXY,
    ).run()
    alternate = MultimodalCapabilityProbe(
        _DeterministicGateway("glm/glm-4.5v", "glm-4.5v"),
        expected_checkpoint="glm/glm-4.5v",
        validation_scope=CapabilityProbeScope.PROVIDER_PROXY,
    ).run()
    checks = {
        "exact_capabilities_pass": exact.capabilities_passed,
        "exact_checkpoint_confirmed": exact.checkpoint_identity_confirmed,
        "exact_deployment_ready": exact.deployment_ready,
        "proxy_capabilities_pass": proxy.capabilities_passed,
        "proxy_scope_passes": proxy.scope_passed,
        "proxy_checkpoint_not_confirmed": not proxy.checkpoint_identity_confirmed,
        "proxy_not_deployment_ready": not proxy.deployment_ready,
        "alternate_proxy_capabilities_pass": alternate.capabilities_passed,
        "alternate_proxy_scope_passes": alternate.scope_passed,
        "alternate_proxy_not_deployment_ready": not alternate.deployment_ready,
        "hidden_reasoning_never_retained": (
            not exact.hidden_reasoning_retained
            and not proxy.hidden_reasoning_retained
            and not alternate.hidden_reasoning_retained
        ),
    }
    output = {
        "mode": "offline_multimodal_capability_and_qwen_identity_contract",
        "live_model_used": False,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "quality_claim": (
            "fake transport and identity semantics only; no Qwen checkpoint behavior, "
            "document quality, latency, or cost claim"
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if output["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
