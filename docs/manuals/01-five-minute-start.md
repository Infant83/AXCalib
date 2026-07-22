# 5분 시작: 가장 작은 AXCalib 인터페이스

> 상태: `two-gate-pptx@v1alpha1`과 G3 policy/Docling/retrieval/structured-model reference는
> 구현·테스트됐고 fail-closed runtime API도 local Alpha로 존재한다. 추가 live model, on-prem 품질,
> 운영 알림, full evaluation/HITL API·OIDC/worker와 Web은 아직 승인·구현되지 않았다.

## 가장 작은 Python 사용

```python
from pathlib import Path

from axcalib import AXCalib
from axcalib.pipelines import TwoGatePptxRequest

client = AXCalib.from_toml(
    "config/axcalib.toml",
    workspace="output/my-review",
)

result = client.run_pptx(
    TwoGatePptxRequest(
        proposal_path=Path("tests/sources/oled_qc_project_outline.pptx"),
        proposal_sidecar_path=Path(
            "tests/sources/oled_qc_project_outline.axcalib.json"
        ),
        title="검토할 과제",
    )
)

print(result.final_status)  # registration_hitl_pending
print(result.registration_report_uri)
```

관리자 결정을 전달하지 않았기 때문에 등록심의 초안과 recording notification을 만든 뒤
멈춘다. `run_pptx`가 Agent 판단만으로 승인하지 않는 것이 정상 동작이다.

## 단계별로 재개하기

```python
project = client.register_case(
    "proposal.pptx",
    title="검토할 과제",
    sidecar_path="proposal.axcalib.json",
)
client.submit_registration(project.project_id)
draft = client.evaluate(project.project_id, "registration")

# 운영에서는 인증된 관리자 boundary만 아래 명령을 호출해야 한다.
# 현재 local/offline client는 actor identity를 인증하지 않고 demo input으로 기록한다.
client.decide_registration(
    project.project_id,
    command="approve",
    actor_id="admin:reviewer-001",
    rationale="근거와 보완조건을 확인했다.",
)
client.start_execution(project.project_id)
client.record_progress(
    project.project_id,
    note="첫 검증 실험의 입력과 환경을 고정했다.",
)
```

비동기 평가는 같은 의미를 가진다.

```python
draft = await client.aevaluate(project.project_id, "registration")
```

## 전체 demo에서 사람 결정을 명시하기

`TwoGatePptxRequest`의 `registration_decision` 또는 `completion_decision`을 설정하면 각각의
`rationale`도 필수다. 완료 결정을 넣으려면 등록 결정이 `approve`여야 한다. 이 필드는 자동
승인 설정이 아니라 사람 결정 command를 library boundary에 전달하는 입력이다. 현재 offline
구현은 이를 `authority_context=offline_unverified_actor`로 기록하며 실제 인증은 하지 않는다.

```python
request = TwoGatePptxRequest(
    proposal_path=Path("proposal.pptx"),
    final_path=Path("final.pptx"),
    title="검토할 과제",
    registration_decision="approve",
    registration_rationale="관리자 검토 근거",
    completion_decision="accept",
    completion_rationale="관리자 완료 수용 근거",
)
result = client.run_pptx(request)
```

## 현재 확인할 수 있는 것

- network/GPU/DB 없는 PPTX two-gate 실행
- sync/async entrypoint와 typed result
- locator 없는 기준의 `insufficient_evidence` 처리
- notification 실패 시 HITL pending 전이 금지
- mentor 배정 시 mentor의 완료 제출 승인 강제
- 동일 제안서/최종안 hash의 `not_accept` 제안
- version/hash-bound review profile과 별도 reviewer adjustment
- optional Docling manifest와 opt-in structured model evaluator

local idempotent resume, durable recording outbox와 multi-process filesystem lock은 Alpha 범위에서
있다. 실제 OCR/VLM, 운영 notification/database, education/full API·OIDC/immutable upload/worker와 Web은 다음
hardening 범위다.

사업별 심사기준과 OpenAI/on-prem endpoint 설정은
[심사 프로필과 모델 endpoint](04-review-profiles-and-model-endpoints.md)를 따른다.
