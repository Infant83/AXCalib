import json
from typing import Any

from axcalib.models import (
    CapabilityProbeScope,
    CapabilityProbeStatus,
    ModelApiMode,
    ModelEndpointConfig,
    ModelGatewayResult,
    MultimodalCapabilityProbe,
    Qwen35CapabilityProbe,
    model_identifiers_match,
    synthetic_two_panel_png_data_url,
)


class _StubGateway:
    def __init__(
        self,
        *,
        requested_model: str,
        response_model: str,
        model_reported_by_endpoint: bool = True,
        invalid_text: str | None = None,
    ) -> None:
        self.config = ModelEndpointConfig(
            profile_id="test/qwen35",
            base_url="http://qwen.internal.invalid/v1",
            model=requested_model,
            api_mode=ModelApiMode.CHAT_COMPLETIONS,
            live=False,
        )
        self.response_model = response_model
        self.model_reported_by_endpoint = model_reported_by_endpoint
        self.invalid_text = invalid_text

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
            output_text = self.invalid_text or json.dumps(
                {
                    "probe_token": "AXCALIB_MULTIMODAL_TEXT_OK",
                    "structured_output": True,
                }
            )
        else:
            assert image_data_urls[0].startswith("data:image/png;base64,")
            output_text = json.dumps(
                {
                    "left_panel": "red",
                    "right_panel": "blue",
                    "two_equal_panels": True,
                }
            )
        return ModelGatewayResult(
            response_id="stub-response",
            model=self.response_model,
            model_reported_by_endpoint=self.model_reported_by_endpoint,
            output_text=output_text,
            request_sha256="a" * 64,
            response_sha256="b" * 64,
            latency_ms=3,
        )


def test_exact_qwen_checkpoint_and_capabilities_are_deployment_ready() -> None:
    report = Qwen35CapabilityProbe(
        _StubGateway(
            requested_model="Qwen3.5-397B-A17B",
            response_model="Qwen/Qwen3.5-397B-A17B",
        ),
        expected_checkpoint="Qwen3.5-397B-A17B",
    ).run()

    assert report.route_identity_confirmed is True
    assert report.checkpoint_identity_confirmed is True
    assert report.capabilities_passed is True
    assert report.scope_passed is True
    assert report.deployment_ready is True
    assert report.hidden_reasoning_retained is False


def test_provider_alias_can_pass_proxy_scope_without_claiming_exact_checkpoint() -> None:
    report = Qwen35CapabilityProbe(
        _StubGateway(
            requested_model="bailian/qwen3.5-plus",
            response_model="qwen3.5-plus",
        ),
        expected_checkpoint="Qwen3.5-397B-A17B",
        validation_scope=CapabilityProbeScope.PROVIDER_PROXY,
    ).run()

    assert report.route_identity_confirmed is True
    assert report.capabilities_passed is True
    assert report.scope_passed is True
    assert report.checkpoint_identity_confirmed is False
    assert report.deployment_ready is False


def test_generic_provider_proxy_never_claims_deployment_readiness() -> None:
    report = MultimodalCapabilityProbe(
        _StubGateway(
            requested_model="glm/glm-4.5v",
            response_model="glm-4.5v",
        ),
        expected_checkpoint="glm/glm-4.5v",
        validation_scope=CapabilityProbeScope.PROVIDER_PROXY,
    ).run()

    assert report.route_identity_confirmed is True
    assert report.checkpoint_identity_confirmed is True
    assert report.scope_passed is True
    assert report.deployment_ready is False


def test_endpoint_must_report_model_for_identity_confirmation() -> None:
    report = Qwen35CapabilityProbe(
        _StubGateway(
            requested_model="Qwen3.5-397B-A17B",
            response_model="Qwen3.5-397B-A17B",
            model_reported_by_endpoint=False,
        ),
        expected_checkpoint="Qwen3.5-397B-A17B",
    ).run()

    assert report.capabilities_passed is True
    assert report.route_identity_confirmed is False
    assert report.checkpoint_identity_confirmed is False
    assert report.deployment_ready is False

    proxy_report = Qwen35CapabilityProbe(
        _StubGateway(
            requested_model="bailian/qwen3.5-plus",
            response_model="bailian/qwen3.5-plus",
            model_reported_by_endpoint=False,
        ),
        expected_checkpoint="Qwen3.5-397B-A17B",
        validation_scope=CapabilityProbeScope.PROVIDER_PROXY,
    ).run()
    assert proxy_report.scope_passed is False


def test_invalid_raw_output_is_not_retained_in_probe_report() -> None:
    raw_marker = "PRIVATE_REASONING_AND_INVALID_OUTPUT_MUST_NOT_PERSIST"
    report = Qwen35CapabilityProbe(
        _StubGateway(
            requested_model="Qwen3.5-397B-A17B",
            response_model="Qwen3.5-397B-A17B",
            invalid_text=raw_marker,
        ),
        expected_checkpoint="Qwen3.5-397B-A17B",
    ).run()

    assert report.structured_text_passed is False
    assert report.checks[0].status is CapabilityProbeStatus.FAILED
    assert report.checks[0].failure_kind == "structured_output_validation_error"
    assert raw_marker not in report.model_dump_json()


def test_synthetic_vision_fixture_is_deterministic_png() -> None:
    first = synthetic_two_panel_png_data_url()
    second = synthetic_two_panel_png_data_url()

    assert first == second
    assert first.startswith("data:image/png;base64,iVBORw0KGgo")
    assert model_identifiers_match(
        "Qwen/Qwen3.5-397B-A17B", "qwen3.5-397b-a17b"
    )
    assert not model_identifiers_match("qwen3.5-plus", "Qwen3.5-397B-A17B")
