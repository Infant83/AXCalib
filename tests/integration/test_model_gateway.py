import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from axcalib import AXCalib
from axcalib.evaluation import StructuredModelEvaluator, StructuredModelOutputError
from axcalib.models import (
    DEFAULT_OPENAI_MODEL,
    ModelApiMode,
    ModelEndpointConfig,
    OpenAICompatibleClient,
)
from axcalib.pipelines import TwoGatePptxRequest
from axcalib.policies import builtin_default_policy
from axcalib.schemas import EvaluationReport, ReviewContext
from axcalib.workflows.two_gate import ProjectStatus

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"


@contextmanager
def _fake_responses_server(
    output: dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any]],
) -> Iterator[tuple[str, dict[str, Any]]]:
    captured: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
            length = int(self.headers["Content-Length"])
            request_body = self.rfile.read(length)
            captured["path"] = self.path
            captured["authorization"] = self.headers.get("Authorization")
            captured["body"] = json.loads(request_body)
            captured.setdefault("bodies", []).append(captured["body"])
            selected_output = output(captured["body"]) if callable(output) else output
            text = json.dumps(selected_output, ensure_ascii=False)
            if self.path.endswith("/chat/completions"):
                envelope = {
                    "id": "chat-test-001",
                    "model": "mock-structured-model",
                    "choices": [{"message": {"content": text}}],
                }
            else:
                envelope = {
                    "id": "resp-test-001",
                    "model": "mock-structured-model",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": text}],
                        }
                    ],
                }
            data = json.dumps(envelope).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = server.server_address
        host, port = str(address[0]), int(address[1])
        yield f"http://{host}:{port}/v1", captured
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _insufficient_output() -> dict[str, Any]:
    return {
        "criteria": [
            {
                "criterion_id": item.criterion_id,
                "assessment": "insufficient_evidence",
                "observation": "제출 근거만으로 충족 여부를 확인할 수 없습니다.",
                "evidence_slide_numbers": [],
                "follow_up_questions": [item.follow_up],
            }
            for item in builtin_default_policy().registration.criteria
        ],
        "recommendation_summary": "근거 보완 후 관리자 검토가 필요합니다.",
        "limitations": ["mock contract response"],
    }


def _two_gate_output(request_body: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(request_body, ensure_ascii=False)
    policy = builtin_default_policy()
    definitions = (
        policy.completion.criteria
        if "axcalib_completion_review" in serialized
        else policy.registration.criteria
    )
    return {
        "criteria": [
            {
                "criterion_id": item.criterion_id,
                "assessment": "insufficient_evidence",
                "observation": "검증 가능한 근거가 부족합니다.",
                "evidence_slide_numbers": [],
                "follow_up_questions": [item.follow_up],
            }
            for item in definitions
        ],
        "recommendation_summary": "관리자 검토 전 근거 보완이 필요합니다.",
        "limitations": ["mock two-gate response"],
    }


def test_environment_contract_supports_standard_and_openapi_aliases() -> None:
    default = ModelEndpointConfig.from_env({"OPENAI_API_KEY": "present"})
    assert default.model == DEFAULT_OPENAI_MODEL
    assert default.api_mode is ModelApiMode.RESPONSES
    assert default.api_key_env == "OPENAI_API_KEY"

    onprem = ModelEndpointConfig.from_env(
        {
            "OPENAPI_API_KEY": "present",
            "OPENAPI_BASE_URL": "http://model.internal.example/v1",
            "OPENAI_MODEL": "Qwen3.5-397B-A17B",
        }
    )
    assert onprem.api_key_env == "OPENAPI_API_KEY"
    assert onprem.model == "Qwen3.5-397B-A17B"
    assert onprem.api_mode is ModelApiMode.CHAT_COMPLETIONS


def test_structured_model_report_is_evidence_bound_and_context_free(tmp_path: Path) -> None:
    with _fake_responses_server(_insufficient_output()) as (base_url, captured):
        config = ModelEndpointConfig(
            profile_id="test/mock-responses",
            base_url=base_url,
            model="mock-structured-model",
            api_mode=ModelApiMode.RESPONSES,
            reasoning_effort=None,
            live=False,
        )
        gateway = OpenAICompatibleClient(config, api_key="dummy-not-a-secret")
        client = AXCalib(
            tmp_path / "model-flow",
            evaluator=StructuredModelEvaluator(gateway),
        )
        dossier = client.register_case(
            SOURCE,
            title="구조화 모델 평가",
            sidecar_path=SIDECAR,
            project_id="structured-model-001",
            review_context=ReviewContext(proposer_org_id="org-should-not-enter-prompt"),
        )
        client.submit_registration(dossier.project_id)
        result = client.evaluate(dossier.project_id, "registration")
        report = EvaluationReport.model_validate_json(
            Path(result.report_json_uri or "").read_text(encoding="utf-8")
        )

    assert report.model_run is not None
    assert report.model_run.live is False
    assert report.evaluator_id.startswith("axcalib.structured-evidence-model/v1")
    assert captured["path"] == "/v1/responses"
    assert captured["authorization"] == "Bearer dummy-not-a-secret"
    serialized_request = json.dumps(captured["body"], ensure_ascii=False)
    assert "dummy-not-a-secret" not in serialized_request
    assert "org-should-not-enter-prompt" not in serialized_request
    assert captured["body"]["text"]["format"]["type"] == "json_schema"


def test_onprem_chat_compatible_mode_carries_multimodal_and_schema_contract() -> None:
    with _fake_responses_server({"ok": True}) as (base_url, captured):
        config = ModelEndpointConfig(
            profile_id="onprem/qwen35",
            base_url=base_url,
            model="Qwen3.5-397B-A17B",
            api_mode=ModelApiMode.CHAT_COMPLETIONS,
            live=False,
        )
        result = OpenAICompatibleClient(config, api_key="dummy").generate_structured(
            instructions="Return the contract.",
            input_text="multimodal probe",
            image_data_urls=("data:image/png;base64,AA==",),
            schema_name="probe",
            json_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["ok"],
                "properties": {"ok": {"type": "boolean"}},
            },
        )

    assert result.model == "mock-structured-model"
    assert captured["path"] == "/v1/chat/completions"
    user_content = captured["body"]["messages"][1]["content"]
    assert [item["type"] for item in user_content] == ["text", "image_url"]
    assert captured["body"]["response_format"]["type"] == "json_schema"


def test_model_cannot_cite_an_unavailable_slide(tmp_path: Path) -> None:
    output = _insufficient_output()
    output["criteria"][0].update(
        {
            "assessment": "met",
            "evidence_slide_numbers": [999],
            "follow_up_questions": [],
        }
    )
    with _fake_responses_server(output) as (base_url, _captured):
        config = ModelEndpointConfig(
            base_url=base_url,
            model="mock-structured-model",
            api_mode=ModelApiMode.RESPONSES,
            reasoning_effort=None,
            live=False,
        )
        client = AXCalib(
            tmp_path / "invalid-model-flow",
            evaluator=StructuredModelEvaluator(OpenAICompatibleClient(config, api_key="dummy")),
        )
        dossier = client.register_case(
            SOURCE,
            title="금지된 locator",
            sidecar_path=SIDECAR,
            project_id="invalid-model-locator-001",
        )
        client.submit_registration(dossier.project_id)

        with pytest.raises(StructuredModelOutputError, match="unavailable evidence"):
            client.evaluate(dossier.project_id, "registration")


def test_model_not_met_without_source_is_downgraded_and_flagged(tmp_path: Path) -> None:
    output = _insufficient_output()
    output["criteria"][0].update({"assessment": "not_met"})
    with _fake_responses_server(output) as (base_url, _captured):
        config = ModelEndpointConfig(
            base_url=base_url,
            model="mock-structured-model",
            api_mode=ModelApiMode.RESPONSES,
            live=False,
        )
        client = AXCalib(
            tmp_path / "unsupported-negative",
            evaluator=StructuredModelEvaluator(
                OpenAICompatibleClient(config, api_key="dummy")
            ),
        )
        dossier = client.register_case(
            SOURCE,
            title="근거 없는 부정 판정",
            sidecar_path=SIDECAR,
            project_id="unsupported-negative-001",
        )
        client.submit_registration(dossier.project_id)

        result = client.evaluate(dossier.project_id, "registration")
        report = EvaluationReport.model_validate_json(
            Path(result.report_json_uri or "").read_text(encoding="utf-8")
        )

    finding = next(
        item for item in report.criteria if item.criterion_id == "REG-PROBLEM-GOAL"
    )
    assert finding.assessment.value == "insufficient_evidence"
    assert "model_assessment_downgraded_no_evidence" in finding.risk_flags


def test_structured_model_runs_both_gates_without_taking_human_authority(
    tmp_path: Path,
) -> None:
    with _fake_responses_server(_two_gate_output) as (base_url, captured):
        config = ModelEndpointConfig(
            base_url=base_url,
            model="mock-structured-model",
            api_mode=ModelApiMode.RESPONSES,
            reasoning_effort=None,
            live=False,
        )
        client = AXCalib(
            tmp_path / "model-two-gate",
            evaluator=StructuredModelEvaluator(
                OpenAICompatibleClient(config, api_key="dummy")
            ),
        )
        summary = client.run_pptx(
            TwoGatePptxRequest(
                proposal_path=SOURCE,
                proposal_sidecar_path=SIDECAR,
                final_path=SOURCE,
                final_sidecar_path=SIDECAR,
                title="구조화 모델 두 Gate",
                project_id="structured-model-two-gate-001",
                registration_decision="approve",
                registration_rationale="synthetic contract test 진행을 승인한다.",
                completion_decision="not_accept",
                completion_rationale="동일 hash 완료자료를 수용하지 않는다.",
            )
        )

    registration = EvaluationReport.model_validate_json(
        Path(summary.registration_report_uri).with_suffix(".json").read_text(
            encoding="utf-8"
        )
    )
    assert summary.completion_report_uri is not None
    completion = EvaluationReport.model_validate_json(
        Path(summary.completion_report_uri).with_suffix(".json").read_text(
            encoding="utf-8"
        )
    )
    assert summary.final_status is ProjectStatus.COMPLETION_NOT_ACCEPTED
    assert summary.notification_count == 2
    assert registration.model_run is not None
    assert completion.model_run is not None
    completion_request = json.dumps(captured["bodies"][-1], ensure_ascii=False)
    assert "registration_baseline" in completion_request
    assert registration.report_id in completion_request
    deliverable = next(
        item for item in completion.criteria if item.criterion_id == "COM-DELIVERABLE"
    )
    assert "proposal_reused_as_final" in deliverable.risk_flags
