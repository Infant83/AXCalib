"""Small OpenAI-compatible HTTP gateway with no provider SDK dependency."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, model_validator

from axcalib.schemas import FrozenModel

DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class ModelApiMode(StrEnum):
    """Supported OpenAI-compatible request dialects."""

    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"


class StructuredOutputMode(StrEnum):
    """Explicit structured-output dialect; the gateway never retries another mode."""

    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"


class ModelEndpointConfig(FrozenModel):
    """Secret-free endpoint and capability configuration."""

    profile_id: str = "openai-compatible/default"
    provider: str = "openai_compatible"
    base_url: str = DEFAULT_OPENAI_BASE_URL
    api_key_env: str = "OPENAI_API_KEY"
    model: str = DEFAULT_OPENAI_MODEL
    api_mode: ModelApiMode = ModelApiMode.RESPONSES
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.JSON_SCHEMA
    capabilities: tuple[str, ...] = ("text", "image", "structured_output")
    reasoning_effort: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=128, le=131_072)
    timeout_seconds: int = Field(default=120, ge=1, le=900)
    live: bool = True

    @model_validator(mode="after")
    def validate_endpoint(self) -> ModelEndpointConfig:
        """Accept HTTP(S) endpoints only and reject credentials embedded in URLs."""

        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("model base_url must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("model base_url must not embed credentials")
        if "structured_output" not in self.capabilities:
            raise ValueError("AXCalib model evaluator requires structured_output capability")
        return self

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        live: bool = True,
    ) -> ModelEndpointConfig:
        """Resolve standard OPENAI_* names with documented OPENAPI_* aliases."""

        values = os.environ if environ is None else environ
        api_key_env = next(
            (name for name in ("OPENAI_API_KEY", "OPENAPI_API_KEY") if values.get(name)),
            "OPENAI_API_KEY",
        )
        base_url = (
            values.get("OPENAI_BASE_URL")
            or values.get("OPENAPI_BASE_URL")
            or DEFAULT_OPENAI_BASE_URL
        ).rstrip("/")
        model = values.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        configured_mode = values.get("OPENAI_API_MODE") or values.get("AXCALIB_MODEL_API_MODE")
        if configured_mode:
            api_mode = ModelApiMode(configured_mode)
        else:
            host = (urlparse(base_url).hostname or "").casefold()
            api_mode = (
                ModelApiMode.RESPONSES
                if host in {"api.openai.com", "www.api.openai.com"}
                else ModelApiMode.CHAT_COMPLETIONS
            )
        structured_output_mode = StructuredOutputMode(
            values.get("OPENAI_STRUCTURED_OUTPUT_MODE")
            or values.get("AXCALIB_MODEL_STRUCTURED_OUTPUT_MODE")
            or StructuredOutputMode.JSON_SCHEMA
        )
        return cls(
            profile_id=(
                "openai/gpt-default"
                if api_mode is ModelApiMode.RESPONSES
                else "onprem/openai-compatible"
            ),
            base_url=base_url,
            api_key_env=api_key_env,
            model=model,
            api_mode=api_mode,
            structured_output_mode=structured_output_mode,
            reasoning_effort=values.get("OPENAI_REASONING_EFFORT"),
            max_output_tokens=(
                int(values["OPENAI_MAX_OUTPUT_TOKENS"])
                if values.get("OPENAI_MAX_OUTPUT_TOKENS")
                else None
            ),
            live=live,
        )


class ModelGatewayResult(FrozenModel):
    """Validated transport result before domain-specific parsing."""

    response_id: str | None = None
    model: str
    model_reported_by_endpoint: bool = True
    output_text: str
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    response_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    latency_ms: int = Field(ge=0)


class ModelGatewayError(RuntimeError):
    """Safe error that never includes API keys or raw evidence."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class OpenAICompatibleClient:
    """POST structured requests to Responses or Chat Completions endpoints."""

    def __init__(self, config: ModelEndpointConfig, *, api_key: str) -> None:
        if not api_key:
            raise ModelGatewayError(f"model API key is missing from {config.api_key_env}")
        self.config = config
        self._api_key = api_key

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        live: bool = True,
    ) -> OpenAICompatibleClient:
        """Build a client without ever persisting the secret value."""

        values = os.environ if environ is None else environ
        config = ModelEndpointConfig.from_env(values, live=live)
        return cls(config, api_key=values.get(config.api_key_env, ""))

    def generate_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        json_schema: dict[str, Any],
        image_data_urls: tuple[str, ...] = (),
    ) -> ModelGatewayResult:
        """Request strict structured output and return only aggregated text."""

        for image_url in image_data_urls:
            if not image_url.startswith("data:image/"):
                raise ValueError("only local image data URLs are accepted by this gateway")
        if image_data_urls and "image" not in self.config.capabilities:
            raise ValueError("model profile does not declare image capability")
        payload = self._payload(
            instructions=instructions,
            input_text=input_text,
            schema_name=schema_name,
            json_schema=json_schema,
            image_data_urls=image_data_urls,
        )
        request_bytes = _canonical_json_bytes(payload)
        endpoint = (
            "/responses" if self.config.api_mode is ModelApiMode.RESPONSES else "/chat/completions"
        )
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + endpoint,
            data=request_bytes,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(  # noqa: S310 - validated configurable HTTP(S) endpoint
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                response_bytes = response.read()
        except urllib.error.HTTPError as error:
            diagnostic = self._safe_http_diagnostic(error)
            raise ModelGatewayError(
                f"model endpoint returned HTTP {error.code}{diagnostic}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ModelGatewayError("model endpoint request failed or timed out") from error
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            raw = json.loads(response_bytes)
            output_text = self._output_text(raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ModelGatewayError(
                "model endpoint returned an invalid response envelope"
            ) from error
        reported_model = raw.get("model")
        return ModelGatewayResult(
            response_id=raw.get("id"),
            model=str(reported_model or self.config.model),
            model_reported_by_endpoint=bool(reported_model),
            output_text=output_text,
            request_sha256=hashlib.sha256(request_bytes).hexdigest(),
            response_sha256=hashlib.sha256(response_bytes).hexdigest(),
            latency_ms=latency_ms,
        )

    def _payload(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        json_schema: dict[str, Any],
        image_data_urls: tuple[str, ...],
    ) -> dict[str, Any]:
        effective_instructions = self._structured_instructions(
            instructions,
            schema_name=schema_name,
            json_schema=json_schema,
        )
        if self.config.api_mode is ModelApiMode.RESPONSES:
            content: list[dict[str, Any]] = [{"type": "input_text", "text": input_text}]
            content.extend(
                {"type": "input_image", "image_url": image_url, "detail": "low"}
                for image_url in image_data_urls
            )
            text_format: dict[str, Any]
            if self.config.structured_output_mode is StructuredOutputMode.JSON_SCHEMA:
                text_format = {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                }
            else:
                text_format = {"type": "json_object"}
            payload: dict[str, Any] = {
                "model": self.config.model,
                "instructions": effective_instructions,
                "input": [{"role": "user", "content": content}],
                "text": {"format": text_format},
            }
            if self.config.reasoning_effort:
                payload["reasoning"] = {"effort": self.config.reasoning_effort}
            if self.config.max_output_tokens is not None:
                payload["max_output_tokens"] = self.config.max_output_tokens
            return payload
        chat_content: list[dict[str, Any]] = [{"type": "text", "text": input_text}]
        chat_content.extend(
            {"type": "image_url", "image_url": {"url": image_url}} for image_url in image_data_urls
        )
        response_format: dict[str, Any]
        if self.config.structured_output_mode is StructuredOutputMode.JSON_SCHEMA:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                },
            }
        else:
            response_format = {"type": "json_object"}
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": effective_instructions},
                {"role": "user", "content": chat_content},
            ],
            "response_format": response_format,
        }
        if self.config.max_output_tokens is not None:
            payload["max_tokens"] = self.config.max_output_tokens
        return payload

    def _structured_instructions(
        self,
        instructions: str,
        *,
        schema_name: str,
        json_schema: dict[str, Any],
    ) -> str:
        """Make JSON-object mode explicit and carry its otherwise unenforced schema."""

        if self.config.structured_output_mode is StructuredOutputMode.JSON_SCHEMA:
            return instructions
        schema = _canonical_json_bytes(json_schema).decode("utf-8")
        return (
            f"{instructions.rstrip()}\n\n"
            "Return exactly one valid JSON object matching the JSON Schema below. "
            "Do not wrap the JSON in Markdown and do not add properties outside the schema. "
            f"Contract name: {schema_name}.\nJSON Schema: {schema}"
        )

    def _output_text(self, response: dict[str, Any]) -> str:
        if self.config.api_mode is ModelApiMode.CHAT_COMPLETIONS:
            content = response["choices"][0]["message"]["content"]
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                text = "".join(
                    str(item.get("text", "")) for item in content if isinstance(item, dict)
                )
                if text.strip():
                    return text
            raise ValueError("chat completion has no text content")
        chunks: list[str] = []
        for item in response.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    chunks.append(str(content.get("text", "")))
        output_text = "".join(chunks)
        if not output_text.strip():
            raise ValueError("response has no output_text content")
        return output_text

    @staticmethod
    def _safe_http_diagnostic(error: urllib.error.HTTPError) -> str:
        """Extract non-evidence error identifiers without returning the server message."""

        try:
            body = json.loads(error.read(64 * 1024))
        except (json.JSONDecodeError, OSError, TypeError):
            return ""
        if not isinstance(body, dict):
            return ""
        upstream_status: int | None = None
        details = body.get("error")
        detail = body.get("detail")
        if not isinstance(details, dict) and isinstance(detail, dict):
            details = detail.get("error")
        if not isinstance(details, dict) and isinstance(detail, str):
            json_start = detail.find("{")
            prefix = detail[:json_start].strip() if json_start >= 0 else detail.strip()
            if prefix.startswith("Failed:"):
                status = prefix.removeprefix("Failed:").strip()
                if status.isdigit():
                    upstream_status = int(status)
            if json_start >= 0:
                try:
                    nested = json.loads(detail[json_start:])
                except (json.JSONDecodeError, TypeError):
                    nested = None
                if isinstance(nested, dict):
                    details = nested.get("error")
        if not isinstance(details, dict):
            return ""
        fields = []
        if upstream_status is not None:
            fields.append(f"upstream_status={upstream_status}")
        for key in ("type", "code", "param"):
            value = details.get(key)
            rendered = str(value) if isinstance(value, (str, int)) else ""
            if rendered and len(rendered) <= 128 and all(
                character.isalnum() or character in "._-/[]" for character in rendered
            ):
                fields.append(f"{key}={rendered}")
        return f" ({', '.join(fields)})" if fields else ""


__all__ = [
    "DEFAULT_OPENAI_BASE_URL",
    "DEFAULT_OPENAI_MODEL",
    "ModelApiMode",
    "ModelEndpointConfig",
    "ModelGatewayError",
    "ModelGatewayResult",
    "OpenAICompatibleClient",
    "StructuredOutputMode",
]
