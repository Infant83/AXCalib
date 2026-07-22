from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from axcalib import AXCalib
from axcalib.api import ApiPipelineGrant, ApiPrincipal, ApiRole, create_app


class _TokenVerifier:
    def verify(self, token: str) -> ApiPrincipal | None:
        principals = {
            "viewer-token": ApiPrincipal(
                subject="user:viewer",
                role=ApiRole.VIEWER,
                scopes=frozenset({"runs:read:any"}),
            ),
            "operator-token": ApiPrincipal(
                subject="user:operator",
                role=ApiRole.OPERATOR,
                organization_id="org:synthetic",
            ),
            "other-operator-token": ApiPrincipal(
                subject="user:other-operator",
                role=ApiRole.OPERATOR,
            ),
        }
        return principals.get(token)


def _runtime_client(tmp_path: Path) -> tuple[AXCalib, TestClient]:
    runtime = AXCalib(tmp_path / "workspace")
    app = create_app(
        runtime,
        token_verifier=_TokenVerifier(),
        pipeline_grants=(
            ApiPipelineGrant(
                pipeline_id="workspace.maintenance",
                pipeline_version="v1alpha1",
            ),
        ),
    )
    return runtime, TestClient(app)


def _auth(token: str = "operator-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_api_is_fail_closed_and_role_checked(tmp_path: Path) -> None:
    _, client = _runtime_client(tmp_path)

    missing = client.get("/v1/pipelines")
    assert missing.status_code == 401
    assert missing.headers["content-type"].startswith("application/problem+json")
    assert missing.headers["www-authenticate"] == "Bearer"
    assert missing.json()["code"] == "authentication_required"

    invalid = client.get("/v1/pipelines", headers=_auth("invalid-token"))
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "invalid_bearer_token"

    catalog = client.get("/v1/pipelines", headers=_auth("viewer-token"))
    assert catalog.status_code == 200
    assert any(
        item["pipeline_id"] == "workspace.maintenance" for item in catalog.json()["pipelines"]
    )

    forbidden = client.post(
        "/v1/pipelines/workspace.maintenance/versions/v1alpha1/runs",
        headers=_auth("viewer-token"),
        json={"run_id": "viewer-run", "payload": {}},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "pipeline_role_forbidden"


def test_api_exposes_no_pipeline_without_an_explicit_delivery_grant(
    tmp_path: Path,
) -> None:
    runtime = AXCalib(tmp_path / "workspace")
    client = TestClient(create_app(runtime, token_verifier=_TokenVerifier()))

    catalog = client.get("/v1/pipelines", headers=_auth())
    assert catalog.status_code == 200
    assert catalog.json()["pipelines"] == []

    denied = client.post(
        "/v1/pipelines/workspace.maintenance/versions/v1alpha1/runs",
        headers=_auth(),
        json={"payload": {}},
    )
    assert denied.status_code == 404
    assert denied.json()["code"] == "pipeline_not_found"


def test_api_runs_same_registry_checkpoint_and_redacts_transport_details(
    tmp_path: Path,
) -> None:
    runtime, client = _runtime_client(tmp_path)
    route = "/v1/pipelines/workspace.maintenance/versions/v1alpha1/runs"
    request = {
        "run_id": "api-maintenance",
        "idempotency_key": "maintenance-1",
        "payload": {},
    }

    executed = client.post(route, headers=_auth(), json=request)
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "succeeded"
    assert "checkpoint_uri" not in executed.json()

    record = runtime.executor.load("api-maintenance")
    assert record.context.actor_id == "user:operator"
    assert record.context.actor_role == "operator"
    assert record.context.metadata == {"transport": "api"}
    checkpoint = Path(runtime.executor.root / "run-api-maintenance.json").read_text(
        encoding="utf-8"
    )
    assert "operator-token" not in checkpoint

    semantic_replay = dict(request)
    semantic_replay["payload"] = {"apply": False}
    replayed = client.post(route, headers=_auth(), json=semantic_replay)
    assert replayed.status_code == 200
    assert replayed.json()["replayed"] is True

    status = client.get("/v1/runs/api-maintenance", headers=_auth("viewer-token"))
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"
    assert status.json()["output"] == executed.json()["output"]

    cross_actor = client.get(
        "/v1/runs/api-maintenance",
        headers=_auth("other-operator-token"),
    )
    assert cross_actor.status_code == 403
    assert cross_actor.json()["code"] == "run_access_forbidden"

    conflict_request = dict(request)
    conflict_request["idempotency_key"] = "maintenance-2"
    conflict = client.post(route, headers=_auth(), json=conflict_request)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "run_conflict"

    generated = client.post(
        route,
        headers=_auth(),
        json={"idempotency_key": "generated-maintenance-1", "payload": {}},
    )
    generated_replay = client.post(
        route,
        headers=_auth(),
        json={"idempotency_key": "generated-maintenance-1", "payload": {}},
    )
    assert generated.status_code == 200
    assert generated.json()["run_id"] == generated_replay.json()["run_id"]
    assert generated_replay.json()["replayed"] is True

    header_auth = _auth() | {"Idempotency-Key": "header-maintenance-1"}
    header_run = client.post(route, headers=header_auth, json={"payload": {}})
    header_replay = client.post(route, headers=header_auth, json={"payload": {}})
    assert header_run.status_code == 200
    assert header_run.json()["run_id"] == header_replay.json()["run_id"]
    assert header_replay.json()["replayed"] is True

    key_conflict = client.post(
        route,
        headers=_auth() | {"Idempotency-Key": "header-key"},
        json={"idempotency_key": "body-key", "payload": {}},
    )
    assert key_conflict.status_code == 422
    assert key_conflict.json()["code"] == "idempotency_key_conflict"

    cancelled = client.post("/v1/runs/api-maintenance/cancel", headers=_auth())
    assert cancelled.status_code == 200
    assert cancelled.json()["cancellation_requested"] is True

    result_path = runtime.executor.root / "run-api-maintenance.result.json"
    result_path.write_text("{}\n", encoding="utf-8")
    corrupted = client.get("/v1/runs/api-maintenance", headers=_auth())
    assert corrupted.status_code == 409
    assert corrupted.json()["code"] == "run_integrity_failure"


def test_api_distinguishes_unknown_pipeline_and_redacted_validation(
    tmp_path: Path,
) -> None:
    _, client = _runtime_client(tmp_path)

    unknown = client.post(
        "/v1/pipelines/unknown.pipeline/versions/v1alpha1/runs",
        headers=_auth(),
        json={"payload": {}},
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "pipeline_not_found"

    invalid = client.post(
        "/v1/pipelines/workspace.maintenance/versions/v1alpha1/runs",
        headers=_auth(),
        json={"payload": {"unknown": "secret-value"}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "pipeline_request_invalid"
    assert "secret-value" not in invalid.text

    authority = client.post(
        "/v1/pipelines/workspace.maintenance/versions/v1alpha1/runs",
        headers=_auth(),
        json={"payload": {"actor_id": "impersonated-user"}},
    )
    assert authority.status_code == 422
    assert authority.json()["code"] == "authority_field_forbidden"
    assert "impersonated-user" not in authority.text

    invalid_envelope = client.post(
        "/v1/pipelines/workspace.maintenance/versions/v1alpha1/runs",
        headers=_auth(),
        json={"payload": {}, "actor_id": "impersonated-user"},
    )
    assert invalid_envelope.status_code == 422
    assert invalid_envelope.json()["code"] == "request_invalid"
    assert "impersonated-user" not in invalid_envelope.text

    missing_run = client.get("/v1/runs/does-not-exist", headers=_auth())
    assert missing_run.status_code == 404
    assert missing_run.json()["code"] == "run_not_found"


def test_api_binds_envelope_revision_to_pipeline_revision(tmp_path: Path) -> None:
    runtime = AXCalib(tmp_path / "workspace")
    client = TestClient(
        create_app(
            runtime,
            token_verifier=_TokenVerifier(),
            pipeline_grants=(
                ApiPipelineGrant(
                    pipeline_id="dossier.update",
                    pipeline_version="v1alpha1",
                ),
            ),
        )
    )

    mismatch = client.post(
        "/v1/pipelines/dossier.update/versions/v1alpha1/runs",
        headers=_auth(),
        json={
            "expected_revision": 1,
            "payload": {
                "project_id": "AXC-SYNTHETIC-REVISION",
                "expected_revision": 2,
                "progress_note": "synthetic",
            },
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "revision_context_conflict"


def test_generated_runtime_openapi_matches_committed_artifact(tmp_path: Path) -> None:
    runtime = AXCalib(tmp_path / "workspace")
    schema = create_app(
        runtime,
        token_verifier=_TokenVerifier(),
        pipeline_grants=(
            ApiPipelineGrant(
                pipeline_id="workspace.maintenance",
                pipeline_version="v1alpha1",
            ),
        ),
    ).openapi()

    assert schema["openapi"] == "3.1.0"
    assert schema["jsonSchemaDialect"].endswith("draft/2020-12/schema")
    assert schema["x-axcalib-contract"]["status"] == "implemented-local-alpha"
    assert "operator-token" not in json.dumps(schema)
    assert set(schema["paths"]) == {
        "/v1/pipelines",
        "/v1/pipelines/{pipeline_id}/versions/{pipeline_version}/runs",
        "/v1/projects",
        "/v1/projects/{project_id}/decisions/completion",
        "/v1/projects/{project_id}/decisions/registration",
        "/v1/runs/{run_id}",
        "/v1/runs/{run_id}/cancel",
    }
    artifact = Path("docs/api/openapi.runtime.v1alpha1.json")
    assert schema == json.loads(artifact.read_text(encoding="utf-8"))


def test_core_import_does_not_load_optional_fastapi() -> None:
    script = (
        "import sys; sys.path.insert(0, 'src'); import axcalib; assert 'fastapi' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
