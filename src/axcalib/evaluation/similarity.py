"""Validation for configurable historical-similarity contribution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimilarityPolicy:
    """Stage-scoped retrieval policy; final decisions still require a human."""

    adapter: str
    stage: str
    portion: float
    required_for_decision: bool = False

    def errors(self) -> list[str]:
        errors: list[str] = []
        if self.stage not in {"registration", "completion"}:
            errors.append("stage must be registration or completion")
        if not 0.0 <= self.portion <= 1.0:
            errors.append("similarity_portion must be between 0.0 and 1.0")
        if self.adapter in {"", "disabled", "null"} and self.portion > 0:
            errors.append("a positive portion requires a configured retrieval adapter")
        if self.required_for_decision and self.adapter in {"", "disabled", "null"}:
            errors.append("required retrieval cannot use a disabled/null adapter")
        return errors

    def warnings(self) -> list[str]:
        if self.portion > 0.25:
            return ["similarity_portion above 0.25 requires explicit Evaluation Owner approval"]
        return []

