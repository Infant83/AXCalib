# AXCalib Library 매뉴얼

## 핵심 객체: Dossier와 Case

Dossier는 한 프로젝트의 등록 목표, 증거, 멘토 기록, 수행 이력, 등록심의와 완료평가 결과를 모은
기록철이다. Python의 `AXCalib` 인스턴스는 workspace를 관리하고, 각 프로젝트는 `project_id`와
revision을 가진 Dossier로 구분한다.

대용량 PPTX·PDF·이미지·코드는 Dossier 내부에 복사하지 않는다. content hash와 URI를 기록하고,
평가할 때 revision과 SHA-256으로 freeze한 snapshot을 읽는다.

`Case`는 dossier를 복제하는 두 번째 진실원천이 아니다. project_id와 Library read service를 들고
있다가 `get_current_status()` 또는 `get_summary()`가 호출될 때마다 최신 dossier revision과 연결된
불변 report를 다시 읽는 작은 핸들이다. 따라서 관리자 결정이나 criterion 보정 뒤에도 같은
`case` 변수를 계속 사용할 수 있다.

## 가장 작은 공개 인터페이스

```python
from axcalib import AXCalib

ax = AXCalib("output/review-workspace")
case = ax.register_case(
    "proposal.pptx",
    title="검토할 프로젝트",
    sidecar_path="proposal.axcalib.json",
)
ax.submit_registration(case.project_id)
registration = ax.evaluate(case.project_id, "registration")

status = case.get_current_status()  # typed CaseStatus
status_md = case.get_current_status(format="md")
summary_md = case.get_summary(format="md", verbose=True)
```

비동기 호출은 같은 의미를 가진다.

```python
registration = await ax.aevaluate(case.project_id, "registration")
```

## 단계별 명령

| 목적 | Library 호출 | 사람 경계 |
|---|---|---|
| 과제 등록 | `register_case` | 제출자료와 project context 확인 |
| 등록심의 제출 | `submit_registration` | freeze할 revision 확인 |
| 등록 평가초안 | `evaluate(..., "registration")` | 결과는 제안이며 관리자 승인 필요 |
| 등록 결정 | `decide_registration` | 인증된 관리자만 호출 |
| 수행 시작·갱신 | `start_execution`, `record_progress` | 수행자·멘토 권한 확인 |
| 완료평가 제출 | `submit_completion` | 멘토가 있으면 mentor 승인 필수 |
| 완료 평가초안 | `evaluate(..., "completion")` | 관리자 수용·미수용 결정 필요 |
| 완료 결정 | `decide_completion` | 인증된 관리자만 호출 |
| 현재 상태 | `case.get_current_status` | next action은 domain-valid 안내이며 caller 권한 인증이 아님 |
| 전체 요약 | `case.get_summary` | Agent 원본과 사람 결정·보정을 분리해 표시 |

현재 local Library의 actor 문자열은 운영 신원 인증을 대신하지 않는다. 실제 원격 명령은 승인된
OIDC/JWKS, assignment source와 resource scope에 연결되기 전까지 운영에 사용하면 안 된다.

기본 status/summary object와 JSON/Markdown에는 dossier/report local URI와 사람 결정 사유를 넣지
않는다. `verbose=True`는 local Library 사용자가 criterion 근거, pseudonymous actor와 결정 사유를
명시적으로 요청하는 옵션이다. Web/API 응답에 그대로 전달하지 말고 기존 principal-bound safe
view와 property-level authorization을 적용한다. raw dossier가 필요하면 `case.dossier`를 읽으며,
초기 snapshot 반환 호환 API는 `create_project(...)`다.

## Pipeline과 Workflow

요소 모듈은 ingest, retrieval, evaluation, report처럼 하나의 capability를 담당한다. 국소 Pipeline은
typed input/output과 명시적 상태를 가진 독립 업무 단위다. 전체 Workflow는 allowlisted Pipeline을
연결하지만 domain state machine이나 HITL Gate를 우회하지 않는다.

```python
result = ax.execute_pipeline(
    "project-evaluation",
    "v1alpha1",
    payload,
    context=context,
)
```

긴 작업은 `enqueue_pipeline(...)`으로 durable local queue에 넣고 `create_worker(...)`로 한 건씩
처리할 수 있다. 이 Worker는 single-host Alpha이며 분산 broker나 heartbeat 완료를 의미하지 않는다.

## 결과를 해석하는 법

- `succeeded`: Pipeline 계산이 성공했다. 사람 인증 완료와 같은 뜻은 아니다.
- `waiting_human`: 평가초안과 알림이 준비되어 권한 있는 결정을 기다린다.
- `blocked`: 선행조건·승인·증거가 부족하다.
- `stale`: 평가 기준 snapshot 뒤 원본 revision이 바뀌었다.
- `retryable_failure`: 같은 idempotency context로 제한된 재시도가 가능하다.
- `terminal_failure` 또는 `cancelled`: 자동 성공 승격이나 재실행을 하지 않는다.

전체 생명주기는 [두 Gate 실습](Two-Gate-Tutorial), 구성은 [설정과 On-prem](Configuration-and-On-Prem)을
참고한다.
