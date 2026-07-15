"""Provider-independent evaluator model gateways."""

from axcalib.models.openai_compatible import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    ModelApiMode,
    ModelEndpointConfig,
    ModelGatewayError,
    ModelGatewayResult,
    OpenAICompatibleClient,
)

__all__ = [
    "DEFAULT_OPENAI_BASE_URL",
    "DEFAULT_OPENAI_MODEL",
    "ModelApiMode",
    "ModelEndpointConfig",
    "ModelGatewayError",
    "ModelGatewayResult",
    "OpenAICompatibleClient",
]
