# 두 Gate 프로젝트 인증 실습

이 실습은 “교육과정 자체”가 아니라 교육과정의 한 milestone에 제출된 프로젝트를 인증 대상으로
삼는다. 프로젝트의 완료 수용은 과정 milestone 근거가 되지만 과정 전체 인증을 자동 확정하지 않는다.

![등록부터 완료까지 여섯 장면](assets/axcalib-six-panel-tutorial.jpg)

## 시나리오

- 학습자: OLED 검사 공정의 AX 개선 프로젝트를 제안한다.
- 기획자: 프로그램 version과 milestone, 제출요건, Pipeline ID를 미리 고정한다.
- 멘토: 선택적으로 배정되며 배정된 경우 완료 제출 전에 승인한다.
- 관리자: 등록심의와 완료평가에서 Agent 초안의 근거·편향·환각을 검토하고 최종 결정한다.

## Gate 1: 등록심의

```python
from axcalib import AXCalib

client = AXCalib("output/two-gate-tutorial")
case = client.register_case(
    "tests/sources/oled_qc_project_outline.pptx",
    title="OLED QC AX 프로젝트",
    sidecar_path="tests/sources/oled_qc_project_outline.axcalib.json",
    project_id="edu-oled-001",
)
client.submit_registration(case.project_id)
registration = client.evaluate(case.project_id, "registration")
```

여기서 확인할 내용은 목표·KPI·범위·위험·근거 위치·기준 version이다. Agent가 `pass`를 제안해도
상태는 관리자 HITL 대기여야 한다. 근거가 없으면 추론으로 채우지 않고 `insufficient_evidence`로
남긴다.

관리자 승인 예시는 다음과 같다. 운영에서는 인증된 관리자 API boundary를 통해 호출해야 한다.

```python
client.decide_registration(
    case.project_id,
    command="approve",
    actor_id="admin:reviewer-001",
    rationale="KPI 기준선과 데이터 접근조건을 보완하는 조건으로 승인",
)
client.start_execution(case.project_id)
```

반려하면 등록 결과 리포트를 보존하고 수행 단계로 넘어가지 않는다.

## 수행과 증거 누적

```python
client.record_progress(
    case.project_id,
    note="검증 데이터의 기간·설비 범위와 재현 환경을 고정했다.",
)
```

실제 산출물은 content hash와 URI로 참조한다. 파일을 바꿨다면 새 revision으로 기록하고 과거
snapshot을 덮어쓰지 않는다. 멘토를 배정했다면 mentor 승인 전에는 완료평가 제출을 등록하지 않는다.

## Gate 2: 완료평가

완료평가는 현재 산출물만 보지 않는다. 등록심의 때 고정한 목표·KPI·범위와 수행 중 누적한 증거를
함께 비교한다.

```python
completion_submission = client.submit_completion(
    case.project_id,
    "final-report.pptx",
    sidecar_path="final-report.axcalib.json",
)
completion = client.evaluate(case.project_id, "completion")
```

관리자는 `docs/rubrics/hitl_review_checklist.md` 기준으로 unsupported claim, 편향, RAG leakage,
가중치 계산과 기준 version을 검토한다. 승인요청 알림 event가 기록되지 않으면 HITL pending 전이를
완료하지 않는다.

```python
client.decide_completion(
    case.project_id,
    command="accept",
    actor_id="admin:reviewer-002",
    rationale="등록 KPI 대비 성과와 재현 근거를 확인했다.",
)
```

## 실패·재개 연습

- 같은 idempotency key로 재시도해 중복 평가가 생기지 않는지 확인한다.
- 평가 중 Dossier revision을 바꿔 결과가 `stale`로 분리되는지 확인한다.
- recording notification adapter를 실패시켜 HITL pending 전이가 fail-closed인지 확인한다.
- mentor가 배정된 프로젝트에서 mentor 승인 없이 완료 제출이 거부되는지 확인한다.

더 많은 실행 조합은 [예제와 Recipe](Examples-and-Recipes), 책임 경계는 [보안과 HITL](Security-and-HITL)을
참고한다.
