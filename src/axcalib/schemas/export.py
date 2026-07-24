"""Deterministic JSON Schema artifacts for persisted and public read contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from axcalib.dossier import atomic_write_text
from axcalib.schemas.case import CaseStatus, CaseSummary
from axcalib.schemas.domain import ProjectDossier
from axcalib.schemas.education import EducationEnrollment, EducationProgram

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
ARTIFACTS: tuple[tuple[str, type[BaseModel], str], ...] = (
    (
        "axcalib.dossier.v1alpha2.schema.json",
        ProjectDossier,
        "https://axcalib.local/schemas/dossier/v1alpha2",
    ),
    (
        "axcalib.education-program.v1alpha1.schema.json",
        EducationProgram,
        "https://axcalib.local/schemas/education-program/v1alpha1",
    ),
    (
        "axcalib.education-enrollment.v1alpha1.schema.json",
        EducationEnrollment,
        "https://axcalib.local/schemas/education-enrollment/v1alpha1",
    ),
    (
        "axcalib.case-status.v1alpha1.schema.json",
        CaseStatus,
        "https://axcalib.local/schemas/case-status/v1alpha1",
    ),
    (
        "axcalib.case-summary.v1alpha1.schema.json",
        CaseSummary,
        "https://axcalib.local/schemas/case-summary/v1alpha1",
    ),
)


def render_schema(model: type[BaseModel], schema_id: str) -> str:
    """Render one Pydantic schema with an explicit Draft 2020-12 dialect."""

    schema = model.model_json_schema(mode="validation")
    schema = {"$schema": SCHEMA_DIALECT, "$id": schema_id, **schema}
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def export_schema_artifacts(output_dir: Path, *, check: bool = False) -> list[str]:
    """Write artifacts or return drift errors in check mode."""

    errors: list[str] = []
    for filename, model, schema_id in ARTIFACTS:
        path = output_dir / filename
        content = render_schema(model, schema_id)
        if check:
            if not path.is_file():
                errors.append(f"missing generated schema: {filename}")
            elif path.read_text(encoding="utf-8") != content:
                errors.append(f"generated schema drift: {filename}")
        else:
            atomic_write_text(path, content)
    return errors


__all__ = ["ARTIFACTS", "export_schema_artifacts", "render_schema"]
