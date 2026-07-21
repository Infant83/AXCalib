"""Secret-free effective runtime configuration manifest."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axcalib.dossier import atomic_write_text, canonical_json_bytes
from axcalib.schemas import EffectiveConfigRef

ROOT_KEYS = frozenset(
    {
        "project",
        "contract",
        "interface",
        "profiles",
        "models",
        "retrieval",
        "notifications",
        "limits",
    }
)
SECTION_KEYS: dict[str, frozenset[str]] = {
    "project": frozenset(
        {
            "baseline",
            "environment",
            "synthetic_only",
            "config_version",
            "default_profile",
            "default_review_profile",
        }
    ),
    "contract": frozenset({"invariants_profile"}),
    "interface": frozenset({"locale", "report_formats"}),
    "profiles.*": frozenset(
        {
            "storage",
            "evaluator",
            "model",
            "notification",
            "registration_retrieval",
            "completion_retrieval",
        }
    ),
    "models.*": frozenset(
        {
            "provider",
            "base_url_env",
            "api_key_env",
            "model_env",
            "api_mode_env",
            "structured_output_mode_env",
            "max_output_tokens_env",
            "default_model",
            "capabilities",
            "generation_profile",
        }
    ),
    "retrieval.*": frozenset(
        {
            "adapter",
            "stage",
            "similarity_portion",
            "top_k",
            "required_for_decision",
            "corpus_snapshot",
        }
    ),
    "notifications.*": frozenset(
        {
            "enabled",
            "adapter",
            "base_url_env",
            "project_id_env",
            "token_env",
            "smtp_host_env",
            "smtp_user_env",
            "smtp_password_env",
            "from_address_env",
        }
    ),
    "limits": frozenset(
        {"evaluation_timeout_seconds", "max_batch_items", "max_parallel_models"}
    ),
}
PROTECTED_KEYS = frozenset(
    {
        "admin_approval_required",
        "approval_notification_required",
        "auto_approve",
        "auto_certify",
        "final_decision",
        "mandatory_hitl",
        "skip_hitl",
    }
)
ENV_NAME_PATTERN = re.compile(r"^(?:AXCALIB|OPENAI|OPENAPI)_[A-Z0-9_]+$")


class RuntimeConfigError(ValueError):
    """Raised before a runtime silently accepts unknown or protected config."""


def _validate_keys(raw: dict[str, Any]) -> None:
    unknown_root = set(raw).difference(ROOT_KEYS)
    if unknown_root:
        raise RuntimeConfigError(f"unknown runtime config keys: {sorted(unknown_root)}")
    exposed: set[str] = set()

    def check_mapping(value: object, allowed: frozenset[str], location: str) -> None:
        if not isinstance(value, dict):
            raise RuntimeConfigError(f"runtime config section {location} must be a table")
        unknown = set(value).difference(allowed)
        exposed.update(set(value).intersection(PROTECTED_KEYS))
        if unknown:
            raise RuntimeConfigError(
                f"unknown runtime config keys at {location}: {sorted(unknown)}"
            )

    for section in ("project", "contract", "interface", "limits"):
        if section in raw:
            check_mapping(raw[section], SECTION_KEYS[section], section)
    for section in ("profiles", "models", "retrieval", "notifications"):
        values = raw.get(section, {})
        if not isinstance(values, dict):
            raise RuntimeConfigError(f"runtime config section {section} must be a table")
        for name, value in values.items():
            check_mapping(value, SECTION_KEYS[f"{section}.*"], f"{section}.{name}")
            if isinstance(value, dict) and section in {"models", "notifications"}:
                for key, candidate in value.items():
                    if key.endswith("_env") and (
                        not isinstance(candidate, str)
                        or ENV_NAME_PATTERN.fullmatch(candidate) is None
                    ):
                        raise RuntimeConfigError(
                            f"{section}.{name}.{key} must name an allowlisted environment variable"
                        )
    if exposed:
        raise RuntimeConfigError(f"protected runtime config keys are forbidden: {sorted(exposed)}")


@dataclass(frozen=True, slots=True)
class LoadedRuntimeConfig:
    """Parsed TOML and its persisted, secret-free identity."""

    value: dict[str, Any]
    reference: EffectiveConfigRef


def load_runtime_config(
    config_path: Path,
    *,
    manifest_path: Path,
    environ: Mapping[str, str] | None = None,
) -> LoadedRuntimeConfig:
    """Load TOML and write a deterministic manifest without credential values."""

    path = config_path.resolve()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    _validate_keys(raw)
    profile_name = str(raw["project"]["default_profile"])
    profile = raw["profiles"][profile_name]
    environment = environ if environ is not None else os.environ
    source_map: dict[str, str] = {
        "config": f"file:{path}",
        "profile": f"toml:profiles.{profile_name}",
    }
    safe_environment: dict[str, object] = {}
    model_name = profile.get("model")
    if model_name:
        model_profile = raw.get("models", {}).get(model_name, {})
        for field in (
            "base_url_env",
            "api_key_env",
            "model_env",
            "api_mode_env",
            "structured_output_mode_env",
            "max_output_tokens_env",
        ):
            env_name = model_profile.get(field)
            if not isinstance(env_name, str):
                continue
            source_map[f"models.{model_name}.{field}"] = f"environment:{env_name}"
            if field == "api_key_env":
                safe_environment[env_name] = {"present": bool(environment.get(env_name))}
            elif field in {
                "model_env",
                "structured_output_mode_env",
                "max_output_tokens_env",
            }:
                safe_environment[env_name] = {
                    "present": bool(environment.get(env_name)),
                    "value": (
                        environment.get(env_name)
                        or (
                            model_profile.get("default_model")
                            if field == "model_env"
                            else None
                        )
                    ),
                }
            else:
                safe_environment[env_name] = {"present": bool(environment.get(env_name))}

    config_sha256 = hashlib.sha256(canonical_json_bytes(raw)).hexdigest()
    safe_effective = {
        "config": raw,
        "environment": safe_environment,
        "profile_name": profile_name,
        "source_map": source_map,
    }
    effective_sha256 = hashlib.sha256(
        canonical_json_bytes(safe_effective)
    ).hexdigest()
    manifest = {
        "schema_version": "axcalib.effective-config/v1alpha1",
        "config_sha256": config_sha256,
        "effective_sha256": effective_sha256,
        "profile_name": profile_name,
        "source_config_uri": str(path),
        "source_map": source_map,
        "safe_environment": safe_environment,
    }
    resolved_manifest_path = manifest_path.resolve()
    atomic_write_text(
        resolved_manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    reference = EffectiveConfigRef(
        config_sha256=config_sha256,
        effective_sha256=effective_sha256,
        profile_name=profile_name,
        source_uri=str(resolved_manifest_path),
        source_map=source_map,
    )
    return LoadedRuntimeConfig(value=raw, reference=reference)


__all__ = ["LoadedRuntimeConfig", "RuntimeConfigError", "load_runtime_config"]
