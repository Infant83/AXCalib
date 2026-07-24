"""Provider-independent structured text and vision capability probes."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import struct
import zlib
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from axcalib.models.openai_compatible import (
    ModelEndpointConfig,
    ModelGatewayError,
    ModelGatewayResult,
    OpenAICompatibleClient,
)
from axcalib.schemas import FrozenModel

DEFAULT_QWEN35_CHECKPOINT = "Qwen3.5-397B-A17B"
QWEN35_REQUIRED_ENVIRONMENT = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")


class CapabilityProbeScope(StrEnum):
    """Identity assurance expected from a probe run."""

    DEPLOYMENT = "deployment"
    PROVIDER_PROXY = "provider_proxy"


class CapabilityProbeStatus(StrEnum):
    """Outcome of one independently validated capability."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CapabilityProbeCheck(FrozenModel):
    """Safe metadata for one capability check; raw model output is excluded."""

    capability: Literal["structured_text", "structured_vision"]
    status: CapabilityProbeStatus
    response_model: str | None = None
    model_reported_by_endpoint: bool = False
    request_sha256: str | None = None
    response_sha256: str | None = None
    latency_ms: int | None = None
    failure_kind: Literal["gateway_error", "structured_output_validation_error"] | None = None


class ModelCapabilityProbeReport(FrozenModel):
    """Secret-free result separating route capabilities from checkpoint identity."""

    schema_version: Literal["axcalib.model-capability-probe/v1alpha1"] = (
        "axcalib.model-capability-probe/v1alpha1"
    )
    probe_id: str
    validation_scope: CapabilityProbeScope
    profile_id: str
    endpoint_sha256: str
    api_key_env: str
    api_mode: str
    structured_output_mode: str
    max_output_tokens: int | None
    requested_model: str
    expected_checkpoint: str
    observed_models: tuple[str, ...]
    route_identity_confirmed: bool
    checkpoint_identity_confirmed: bool
    structured_text_passed: bool
    structured_vision_passed: bool
    capabilities_passed: bool
    scope_passed: bool
    deployment_ready: bool
    live: bool
    hidden_reasoning_retained: Literal[False] = False
    checks: tuple[CapabilityProbeCheck, ...]
    limitations: tuple[str, ...]


class _MultimodalTextProbeOutput(FrozenModel):
    probe_token: Literal["AXCALIB_MULTIMODAL_TEXT_OK"]
    structured_output: Literal[True]


class _VisionProbeOutput(FrozenModel):
    left_panel: Literal["red"]
    right_panel: Literal["blue"]
    two_equal_panels: Literal[True]


class StructuredGenerationGateway(Protocol):
    """Small gateway surface required by the capability probe."""

    config: ModelEndpointConfig

    def generate_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        json_schema: dict[str, Any],
        image_data_urls: tuple[str, ...] = (),
    ) -> ModelGatewayResult: ...


def normalize_model_identifier(value: str) -> str:
    """Normalize case and an optional registry/vendor prefix without guessing aliases."""

    return value.strip().replace("\\", "/").rsplit("/", 1)[-1].casefold()


def model_identifiers_match(left: str, right: str) -> bool:
    """Compare explicit identifiers; marketing aliases are intentionally not expanded."""

    return bool(left.strip() and right.strip()) and (
        normalize_model_identifier(left) == normalize_model_identifier(right)
    )


def synthetic_two_panel_png_data_url(*, width: int = 96, height: int = 64) -> str:
    """Return a deterministic red-left/blue-right PNG without an imaging dependency."""

    if width < 2 or height < 1 or width % 2:
        raise ValueError("synthetic probe image width must be even and >= 2; height must be >= 1")
    red = bytes((255, 0, 0)) * (width // 2)
    blue = bytes((0, 0, 255)) * (width // 2)
    scanline = b"\x00" + red + blue
    pixels = scanline * height

    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(pixels, level=9))
    png += chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


class MultimodalCapabilityProbe:
    """Probe any OpenAI-compatible multimodal route without provider coupling."""

    def __init__(
        self,
        gateway: StructuredGenerationGateway,
        *,
        expected_checkpoint: str,
        validation_scope: CapabilityProbeScope = CapabilityProbeScope.DEPLOYMENT,
    ) -> None:
        if not expected_checkpoint.strip():
            raise ValueError("expected_checkpoint must be explicit")
        self.gateway = gateway
        self.expected_checkpoint = expected_checkpoint
        self.validation_scope = validation_scope

    def run(self, *, include_vision: bool = True) -> ModelCapabilityProbeReport:
        """Run deterministic probes and retain hashes/status rather than raw responses."""

        text_check = self._run_text_check()
        vision_check = (
            self._run_vision_check()
            if include_vision
            else CapabilityProbeCheck(
                capability="structured_vision",
                status=CapabilityProbeStatus.SKIPPED,
            )
        )
        checks = (text_check, vision_check)
        passed = tuple(item for item in checks if item.status is CapabilityProbeStatus.PASSED)
        observed_models = tuple(
            dict.fromkeys(item.response_model for item in passed if item.response_model)
        )
        route_identity_confirmed = bool(passed) and all(
            item.model_reported_by_endpoint
            and item.response_model is not None
            and model_identifiers_match(item.response_model, self.gateway.config.model)
            for item in passed
        )
        checkpoint_identity_confirmed = (
            route_identity_confirmed
            and model_identifiers_match(self.gateway.config.model, self.expected_checkpoint)
            and all(
                item.response_model is not None
                and model_identifiers_match(item.response_model, self.expected_checkpoint)
                for item in passed
            )
        )
        text_passed = text_check.status is CapabilityProbeStatus.PASSED
        vision_passed = vision_check.status is CapabilityProbeStatus.PASSED
        capabilities_passed = text_passed and (vision_passed if include_vision else True)
        deployment_ready = (
            self.validation_scope is CapabilityProbeScope.DEPLOYMENT
            and capabilities_passed
            and include_vision
            and checkpoint_identity_confirmed
        )
        scope_passed = (
            capabilities_passed
            and route_identity_confirmed
            and (
                checkpoint_identity_confirmed
                if self.validation_scope is CapabilityProbeScope.DEPLOYMENT
                else True
            )
        )
        limitations = [
            (
                "This probe checks transport and constrained output only; "
                "it does not establish task quality."
            ),
            "Raw prompts, images, outputs, and hidden reasoning are not retained in this report.",
        ]
        if self.validation_scope is CapabilityProbeScope.PROVIDER_PROXY:
            limitations.append(
                "A provider proxy result does not establish the exact deployment checkpoint."
            )
        if not checkpoint_identity_confirmed:
            limitations.append(
                "The requested route and endpoint metadata did not confirm the expected checkpoint."
            )
        if not include_vision:
            limitations.append(
                "Vision capability was not tested, so deployment readiness is false."
            )
        probe_seed = {
            "scope": self.validation_scope.value,
            "requested": self.gateway.config.model,
            "expected": self.expected_checkpoint,
            "checks": [
                {
                    "capability": item.capability,
                    "status": item.status.value,
                    "request_sha256": item.request_sha256,
                    "response_sha256": item.response_sha256,
                }
                for item in checks
            ],
        }
        probe_id = (
            "mcp-"
            + hashlib.sha256(
                json.dumps(probe_seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:20]
        )
        endpoint_sha256 = hashlib.sha256(
            self.gateway.config.base_url.rstrip("/").encode("utf-8")
        ).hexdigest()
        return ModelCapabilityProbeReport(
            probe_id=probe_id,
            validation_scope=self.validation_scope,
            profile_id=self.gateway.config.profile_id,
            endpoint_sha256=endpoint_sha256,
            api_key_env=self.gateway.config.api_key_env,
            api_mode=self.gateway.config.api_mode.value,
            structured_output_mode=self.gateway.config.structured_output_mode.value,
            max_output_tokens=self.gateway.config.max_output_tokens,
            requested_model=self.gateway.config.model,
            expected_checkpoint=self.expected_checkpoint,
            observed_models=observed_models,
            route_identity_confirmed=route_identity_confirmed,
            checkpoint_identity_confirmed=checkpoint_identity_confirmed,
            structured_text_passed=text_passed,
            structured_vision_passed=vision_passed,
            capabilities_passed=capabilities_passed,
            scope_passed=scope_passed,
            deployment_ready=deployment_ready,
            live=self.gateway.config.live,
            checks=checks,
            limitations=tuple(limitations),
        )

    def _run_text_check(self) -> CapabilityProbeCheck:
        return self._run_check(
            capability="structured_text",
            instructions=(
                "Return only the requested JSON. Do not reveal or include hidden reasoning."
            ),
            input_text=(
                'Return {"probe_token":"AXCALIB_MULTIMODAL_TEXT_OK",'
                '"structured_output":true} exactly.'
            ),
            schema_name="axcalib_multimodal_text_probe",
            json_schema=_MultimodalTextProbeOutput.model_json_schema(),
            output_model=_MultimodalTextProbeOutput,
        )

    def _run_vision_check(self) -> CapabilityProbeCheck:
        return self._run_check(
            capability="structured_vision",
            instructions=(
                "Inspect only the supplied synthetic image and return JSON matching the schema. "
                "Do not reveal or include hidden reasoning."
            ),
            input_text=(
                "Identify the left and right panel colors and whether the panels have equal width."
            ),
            schema_name="axcalib_multimodal_vision_probe",
            json_schema=_VisionProbeOutput.model_json_schema(),
            output_model=_VisionProbeOutput,
            image_data_urls=(synthetic_two_panel_png_data_url(),),
        )

    def _run_check(
        self,
        *,
        capability: Literal["structured_text", "structured_vision"],
        instructions: str,
        input_text: str,
        schema_name: str,
        json_schema: dict[str, Any],
        output_model: type[FrozenModel],
        image_data_urls: tuple[str, ...] = (),
    ) -> CapabilityProbeCheck:
        try:
            result = self.gateway.generate_structured(
                instructions=instructions,
                input_text=input_text,
                schema_name=schema_name,
                json_schema=json_schema,
                image_data_urls=image_data_urls,
            )
        except ModelGatewayError:
            return CapabilityProbeCheck(
                capability=capability,
                status=CapabilityProbeStatus.FAILED,
                failure_kind="gateway_error",
            )
        try:
            output_model.model_validate_json(result.output_text)
        except (ValidationError, ValueError):
            return CapabilityProbeCheck(
                capability=capability,
                status=CapabilityProbeStatus.FAILED,
                response_model=result.model,
                model_reported_by_endpoint=result.model_reported_by_endpoint,
                request_sha256=result.request_sha256,
                response_sha256=result.response_sha256,
                latency_ms=result.latency_ms,
                failure_kind="structured_output_validation_error",
            )
        return CapabilityProbeCheck(
            capability=capability,
            status=CapabilityProbeStatus.PASSED,
            response_model=result.model,
            model_reported_by_endpoint=result.model_reported_by_endpoint,
            request_sha256=result.request_sha256,
            response_sha256=result.response_sha256,
            latency_ms=result.latency_ms,
        )


class Qwen35CapabilityProbe(MultimodalCapabilityProbe):
    """Compatibility name for the Qwen3.5 deployment-specific probe entrypoint."""


def probe_qwen35_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    expected_checkpoint: str = DEFAULT_QWEN35_CHECKPOINT,
    validation_scope: CapabilityProbeScope = CapabilityProbeScope.DEPLOYMENT,
    include_vision: bool = True,
) -> ModelCapabilityProbeReport:
    """Run the canonical Qwen3.5 probe without exposing provider or secret details."""

    values = os.environ if environ is None else environ
    missing = [name for name in QWEN35_REQUIRED_ENVIRONMENT if not values.get(name)]
    if missing:
        names = ", ".join(missing)
        raise ValueError(f"live Qwen probe requires explicit environment variables: {names}")
    if "qwen3.5" not in normalize_model_identifier(values["OPENAI_MODEL"]):
        raise ValueError("OPENAI_MODEL must explicitly identify a Qwen3.5 route")
    config = ModelEndpointConfig.from_env(values, live=True)
    client = OpenAICompatibleClient(config, api_key=values["OPENAI_API_KEY"])
    return Qwen35CapabilityProbe(
        client,
        expected_checkpoint=expected_checkpoint,
        validation_scope=validation_scope,
    ).run(include_vision=include_vision)


__all__ = [
    "CapabilityProbeCheck",
    "CapabilityProbeScope",
    "CapabilityProbeStatus",
    "DEFAULT_QWEN35_CHECKPOINT",
    "ModelCapabilityProbeReport",
    "MultimodalCapabilityProbe",
    "QWEN35_REQUIRED_ENVIRONMENT",
    "Qwen35CapabilityProbe",
    "StructuredGenerationGateway",
    "model_identifiers_match",
    "normalize_model_identifier",
    "probe_qwen35_from_env",
    "synthetic_two_panel_png_data_url",
]
