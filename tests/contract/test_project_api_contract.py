from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from axcalib import AXCalib
from axcalib.api import (
    ApiPrincipal,
    ApiRole,
    ArtifactPurpose,
    StagedArtifactRef,
    create_app,
)
from axcalib.api.models import PPTX_MEDIA_TYPE
from axcalib.ingest.pptx import sha256_file
from axcalib.pipelines import ProjectSourceIntegrityError


class _TokenVerifier:
    def verify(self, token: str) -> ApiPrincipal | None:
        principals = {
            "owner-token": ApiPrincipal(
                subject="user:owner",
                role=ApiRole.PROJECT_OWNER,
                organization_id="org:alpha",
                scopes=frozenset({"projects:create", "projects:read:own"}),
            ),
            "other-owner-token": ApiPrincipal(
                subject="user:other-owner",
                role=ApiRole.PROJECT_OWNER,
                organization_id="org:alpha",
                scopes=frozenset({"projects:read:own"}),
            ),
            "admin-token": ApiPrincipal(
                subject="user:administrator",
                role=ApiRole.ADMINISTRATOR,
                organization_id="org:alpha",
                scopes=frozenset({"projects:decide:any", "projects:read:any"}),
            ),
            "second-admin-token": ApiPrincipal(
                subject="user:second-administrator",
                role=ApiRole.ADMINISTRATOR,
                organization_id="org:alpha",
                scopes=frozenset({"projects:decide:any", "projects:read:any"}),
            ),
            "other-admin-token": ApiPrincipal(
                subject="user:other-administrator",
                role=ApiRole.ADMINISTRATOR,
                organization_id="org:other",
                scopes=frozenset({"projects:decide:any", "projects:read:any"}),
            ),
            "unscoped-admin-token": ApiPrincipal(
                subject="user:unscoped-administrator",
                role=ApiRole.ADMINISTRATOR,
                organization_id="org:alpha",
            ),
        }
        return principals.get(token)


class _ArtifactResolver:
    def __init__(self, artifacts: dict[str, Path]) -> None:
        self.artifacts = artifacts
        self.calls: list[tuple[str, str, str]] = []

    def resolve(
        self,
        artifact: StagedArtifactRef,
        *,
        principal: ApiPrincipal,
        purpose: ArtifactPurpose,
    ) -> Path | None:
        self.calls.append((artifact.artifact_id, principal.subject, purpose))
        return self.artifacts.get(artifact.artifact_id)


def _auth(token: str, idempotency_key: str = "registration-request-1") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": idempotency_key,
    }


def _artifact(path: Path, artifact_id: str, media_type: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "sha256": sha256_file(path),
        "byte_size": path.stat().st_size,
        "media_type": media_type,
    }


def _registration_request() -> tuple[dict[str, Any], dict[str, Path]]:
    proposal = Path("tests/sources/oled_qc_project_outline.pptx").resolve()
    sidecar = Path("tests/sources/oled_qc_project_outline.axcalib.json").resolve()
    return (
        {
            "title": "Synthetic principal-bound project",
            "proposal": _artifact(proposal, "staged-proposal-1", PPTX_MEDIA_TYPE),
            "sidecar": _artifact(sidecar, "staged-sidecar-1", "application/json"),
            "certification_level": "AX-L1",
        },
        {
            "staged-proposal-1": proposal,
            "staged-sidecar-1": sidecar,
        },
    )


def _project_client(tmp_path: Path) -> tuple[AXCalib, TestClient, _ArtifactResolver]:
    _, source_paths = _registration_request()
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    paths: dict[str, Path] = {}
    for artifact_id, source in source_paths.items():
        target = staging / source.name
        shutil.copy2(source, target)
        paths[artifact_id] = target
    resolver = _ArtifactResolver(paths)
    runtime = AXCalib(tmp_path / "workspace")
    app = create_app(
        runtime,
        token_verifier=_TokenVerifier(),
        artifact_resolver=resolver,
    )
    return runtime, TestClient(app), resolver


def _register(
    client: TestClient,
    idempotency_key: str = "registration-request-1",
) -> dict[str, Any]:
    request, _ = _registration_request()
    response = client.post(
        "/v1/projects",
        headers=_auth("owner-token", idempotency_key),
        json=request,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_project_registration_binds_principal_and_opaque_artifacts(tmp_path: Path) -> None:
    runtime, client, resolver = _project_client(tmp_path)
    request, _ = _registration_request()

    registered = client.post(
        "/v1/projects",
        headers=_auth("owner-token"),
        json=request,
    )
    assert registered.status_code == 200, registered.text
    body = registered.json()
    assert body["proposer_org_id"] == "org:alpha"
    assert body["artifact"]["sha256"] == request["proposal"]["sha256"]
    assert "uri" not in body["artifact"]
    assert str(Path("tests/sources").resolve()) not in registered.text
    assert resolver.calls == [
        ("staged-proposal-1", "user:owner", "registration_proposal"),
        ("staged-sidecar-1", "user:owner", "pptx_sidecar"),
    ]

    dossier = runtime.service.dossiers.load(str(body["project_id"]))
    assert dossier.review_context.proposer_org_id == "org:alpha"
    created = next(
        event
        for event in runtime.service.audit.entries()
        if event["event_type"] == "project_created"
    )
    assert created["actor_id"] == "user:owner"
    assert created["actor_role"] == "project_owner"

    resolver.artifacts.clear()
    replay = client.post(
        "/v1/projects",
        headers=_auth("owner-token"),
        json=request,
    )
    assert replay.status_code == 200
    assert replay.json()["project_id"] == body["project_id"]
    assert replay.json()["replayed"] is True
    assert len(resolver.calls) == 2

    changed = dict(request)
    changed["title"] = "Different request with reused key"
    conflict = client.post(
        "/v1/projects",
        headers=_auth("owner-token"),
        json=changed,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "project_registration_conflict"

    runtime.service.audit.path.write_text("", encoding="utf-8")
    incomplete = client.post(
        "/v1/projects",
        headers=_auth("owner-token"),
        json=request,
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["code"] == "project_registration_integrity_failure"


def test_project_registration_rejects_paths_and_integrity_failures(tmp_path: Path) -> None:
    _, client, _ = _project_client(tmp_path)
    request, _ = _registration_request()

    with_path = dict(request)
    with_path["proposal"] = dict(request["proposal"])
    with_path["proposal"]["path"] = "C:/sensitive/proposal.pptx"
    invalid_path = client.post(
        "/v1/projects",
        headers=_auth("owner-token"),
        json=with_path,
    )
    assert invalid_path.status_code == 422
    assert invalid_path.json()["code"] == "request_invalid"
    assert "sensitive" not in invalid_path.text

    bad_hash = dict(request)
    bad_hash["proposal"] = dict(request["proposal"])
    bad_hash["proposal"]["sha256"] = "0" * 64
    integrity = client.post(
        "/v1/projects",
        headers=_auth("owner-token") | {"Idempotency-Key": "bad-hash"},
        json=bad_hash,
    )
    assert integrity.status_code == 409
    assert integrity.json()["code"] == "staged_artifact_integrity_failure"

    no_resolver = TestClient(
        create_app(AXCalib(tmp_path / "reject-all"), token_verifier=_TokenVerifier())
    )
    unavailable = no_resolver.post(
        "/v1/projects",
        headers=_auth("owner-token"),
        json=request,
    )
    assert unavailable.status_code == 404
    assert unavailable.json()["code"] == "staged_artifact_not_found"


def test_project_get_requires_owner_or_admin_scope_and_returns_safe_view(
    tmp_path: Path,
) -> None:
    _, client, _ = _project_client(tmp_path)
    registered = _register(client)
    project_id = str(registered["project_id"])
    path = f"/v1/projects/{project_id}"

    owner = client.get(path, headers=_auth("owner-token"))
    assert owner.status_code == 200, owner.text
    body = owner.json()
    assert body["project_id"] == project_id
    assert body["proposer_org_id"] == "org:alpha"
    assert body["revision"] == registered["revision"]
    assert body["artifacts"][0]["sha256"] == registered["artifact"]["sha256"]
    assert set(body["execution"]) == {
        "started_at",
        "completion_submitted_at",
        "mentor_assigned",
        "progress_note_count",
    }
    for forbidden in (
        "uri",
        "source_uri",
        "report_json_uri",
        "report_markdown_uri",
        "rationale",
        "notes",
        "mentor_ref",
    ):
        assert forbidden not in owner.text

    admin = client.get(path, headers=_auth("admin-token"))
    assert admin.status_code == 200
    assert admin.json() == body

    unscoped = client.get(path, headers=_auth("unscoped-admin-token"))
    assert unscoped.status_code == 403
    assert unscoped.json()["code"] == "project_read_scope_forbidden"

    different_owner = client.get(path, headers=_auth("other-owner-token"))
    assert different_owner.status_code == 403
    assert different_owner.json()["code"] == "project_owner_read_forbidden"

    wrong_org = client.get(path, headers=_auth("other-admin-token"))
    assert wrong_org.status_code == 403
    assert wrong_org.json()["code"] == "project_organization_forbidden"


def test_project_source_hash_is_rechecked_before_create_and_evaluation(
    tmp_path: Path,
) -> None:
    runtime, client, resolver = _project_client(tmp_path)
    request, _ = _registration_request()
    request.pop("sidecar")

    with pytest.raises(ProjectSourceIntegrityError, match="before dossier registration"):
        runtime.register_case(
            resolver.artifacts["staged-proposal-1"],
            title="Rejected pre-transaction source",
            expected_proposal_sha256="0" * 64,
        )
    assert not tuple(runtime.service.dossiers.root.glob("*.yaml"))

    registered = client.post(
        "/v1/projects",
        headers=_auth("owner-token"),
        json=request,
    )
    assert registered.status_code == 200, registered.text
    project_id = registered.json()["project_id"]
    runtime.submit_registration(project_id)
    with resolver.artifacts["staged-proposal-1"].open("ab") as stream:
        stream.write(b"tampered-after-registration")
    with pytest.raises(ProjectSourceIntegrityError, match="after dossier registration"):
        runtime.evaluate(project_id, "registration")
    assert runtime.service.dossiers.load(project_id).status == "registration_ready"


def test_registration_decision_binds_admin_scope_org_and_revision(tmp_path: Path) -> None:
    runtime, client, _ = _project_client(tmp_path)
    registered = _register(client)
    project_id = str(registered["project_id"])
    runtime.submit_registration(project_id)
    runtime.evaluate(project_id, "registration")
    current = runtime.service.dossiers.load(project_id)
    decision_path = f"/v1/projects/{project_id}/decisions/registration"
    request = {
        "expected_revision": current.revision,
        "command": "approve",
        "rationale": "Evidence and reviewer checklist were checked.",
    }
    decision_headers = _auth("admin-token", "registration-decision-1")

    owner = client.post(decision_path, headers=_auth("owner-token"), json=request)
    assert owner.status_code == 403
    assert owner.json()["code"] == "administrator_role_required"

    unscoped = client.post(
        decision_path,
        headers=_auth("unscoped-admin-token"),
        json=request,
    )
    assert unscoped.status_code == 403
    assert unscoped.json()["code"] == "project_decision_scope_forbidden"

    wrong_org = client.post(
        decision_path,
        headers=_auth("other-admin-token"),
        json=request,
    )
    assert wrong_org.status_code == 403
    assert wrong_org.json()["code"] == "project_organization_forbidden"
    assert runtime.service.dossiers.load(project_id).revision == current.revision

    stale = client.post(
        decision_path,
        headers=_auth("admin-token"),
        json=request | {"expected_revision": current.revision - 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_project_revision"
    assert runtime.service.dossiers.load(project_id).revision == current.revision

    impersonation = client.post(
        decision_path,
        headers=_auth("admin-token"),
        json=request | {"actor_id": "user:impersonated"},
    )
    assert impersonation.status_code == 422
    assert "impersonated" not in impersonation.text

    missing_key = client.post(
        decision_path,
        headers={"Authorization": "Bearer admin-token"},
        json=request,
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["code"] == "request_invalid"
    assert runtime.service.dossiers.load(project_id).revision == current.revision

    approved = client.post(
        decision_path,
        headers=decision_headers,
        json=request,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["dossier_status"] == "registration_approved"
    assert "dossier_uri" not in approved.json()
    event = runtime.service.audit.entries()[-1]
    assert event["event_type"] == "registration_decided"
    assert event["actor_id"] == "user:administrator"
    assert event["actor_role"] == "administrator"
    decided = runtime.service.dossiers.load(project_id)
    assert decided.registration.decision is not None
    assert decided.registration.decision.authority_context == "verified_api_principal"

    replay = client.post(decision_path, headers=decision_headers, json=request)
    assert replay.status_code == 200, replay.text
    assert replay.json() == approved.json()
    assert runtime.service.dossiers.load(project_id).revision == decided.revision
    assert (
        len(
            [
                item
                for item in runtime.service.audit.entries()
                if item["event_type"] == "registration_decided" and item["project_id"] == project_id
            ]
        )
        == 1
    )

    changed_payload = client.post(
        decision_path,
        headers=decision_headers,
        json=request | {"rationale": "A different rationale reuses the key."},
    )
    assert changed_payload.status_code == 409
    assert changed_payload.json()["code"] == "project_decision_idempotency_conflict"
    assert runtime.service.dossiers.load(project_id).revision == decided.revision

    changed_actor = client.post(
        decision_path,
        headers=_auth("second-admin-token", "registration-decision-1"),
        json=request,
    )
    assert changed_actor.status_code == 409
    assert changed_actor.json()["code"] == "project_decision_idempotency_conflict"
    assert runtime.service.dossiers.load(project_id).revision == decided.revision

    second = _register(client, "registration-request-2")
    second_id = str(second["project_id"])
    runtime.submit_registration(second_id)
    runtime.evaluate(second_id, "registration")
    second_current = runtime.service.dossiers.load(second_id)
    changed_resource = client.post(
        f"/v1/projects/{second_id}/decisions/registration",
        headers=decision_headers,
        json=request | {"expected_revision": second_current.revision},
    )
    assert changed_resource.status_code == 409
    assert changed_resource.json()["code"] == "project_decision_idempotency_conflict"
    assert runtime.service.dossiers.load(second_id).revision == second_current.revision


def test_completion_decision_uses_same_principal_and_revision_guard(tmp_path: Path) -> None:
    runtime, client, _ = _project_client(tmp_path)
    registered = _register(client)
    project_id = str(registered["project_id"])
    runtime.submit_registration(project_id)
    runtime.evaluate(project_id, "registration")
    registration = runtime.service.dossiers.load(project_id)
    client.post(
        f"/v1/projects/{project_id}/decisions/registration",
        headers=_auth("admin-token", "completion-flow-registration-decision"),
        json={
            "expected_revision": registration.revision,
            "command": "approve",
            "rationale": "Registration evidence checked.",
        },
    ).raise_for_status()
    runtime.start_execution(project_id)
    final_path = Path(
        "fixtures/synthetic/education_project_lifecycle/completion_report.synthetic.pptx"
    )
    sidecar_path = Path(
        "fixtures/synthetic/education_project_lifecycle/completion_report.synthetic.axcalib.json"
    )
    runtime.submit_completion(project_id, final_path, sidecar_path=sidecar_path)
    runtime.evaluate(project_id, "completion")
    completion = runtime.service.dossiers.load(project_id)
    decision_path = f"/v1/projects/{project_id}/decisions/completion"
    decision_headers = _auth("admin-token", "completion-decision-1")

    stale = client.post(
        decision_path,
        headers=_auth("admin-token"),
        json={
            "expected_revision": completion.revision - 1,
            "command": "accept",
            "rationale": "Completion evidence checked.",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_project_revision"

    accepted = client.post(
        decision_path,
        headers=decision_headers,
        json={
            "expected_revision": completion.revision,
            "command": "accept",
            "rationale": "Completion evidence checked.",
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["dossier_status"] == "completion_accepted"
    event = runtime.service.audit.entries()[-1]
    assert event["event_type"] == "completion_decided"
    assert event["actor_id"] == "user:administrator"
    decided = runtime.service.dossiers.load(project_id)
    assert decided.completion.decision is not None
    assert decided.completion.decision.authority_context == "verified_api_principal"

    request = {
        "expected_revision": completion.revision,
        "command": "accept",
        "rationale": "Completion evidence checked.",
    }
    replay = client.post(decision_path, headers=decision_headers, json=request)
    assert replay.status_code == 200, replay.text
    assert replay.json() == accepted.json()
    assert runtime.service.dossiers.load(project_id).revision == decided.revision

    conflict = client.post(
        decision_path,
        headers=decision_headers,
        json=request | {"command": "not_accept"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "project_decision_idempotency_conflict"
    assert runtime.service.dossiers.load(project_id).revision == decided.revision
