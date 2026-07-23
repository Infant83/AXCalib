# AXCalib Library 매뉴얼

## 핵심 객체: Dossier

Dossier는 한 프로젝트의 등록 목표, 증거, 멘토 기록, 수행 이력, 등록심의와 완료평가 결과를 모은
기록철이다. Python의 `AXCalib` 인스턴스는 workspace를 관리하고, 각 프로젝트는 `project_id`와
revision을 가진 Dossier로 구분한다.

대용량 PPTX·PDF·이미지·코드는 Dossier 내부에 복사하지 않는다. content hash와 URI를 기록하고,
평가할 때 revision과 SHA-256으로 freeze한 snapshot을 읽는다.

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

현재 local Library의 actor 문자열은 운영 신원 인증을 대신하지 않는다. 실제 원격 명령은 승인된
OIDC/JWKS, assignment source와 resource scope에 연결되기 전까지 운영에 사용하면 안 된다.

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
