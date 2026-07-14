# AXCalib Composable Pipeline 구현계획

이 문서는 AXCalib를 요소 모듈, 재사용 가능한 국소 파이프라인, 전체 workflow, 전달
interface로 나누는 구현계약을 정의한다. 현재 문서는 설계 baseline이며 `Pipeline` kernel이나
개별 파이프라인이 구현됐다는 뜻은 아니다.

전체 흐름과 sequence는 `workflow-blueprint.md`, M00~M13의 현재 상태·선행조건·Exit Evidence는
`module-delivery-plan.md`, 한 장 요약은 `diagrams/workflow-at-a-glance.svg`를 함께 본다.

## 1. 결정 요약

AXCalib 구현 단위는 다음 네 층으로 고정한다.

1. **요소 모듈**: dossier, evidence, retrieval, evaluation, report, notification처럼 한 책임을
   가진 library package
2. **국소 파이프라인**: 여러 요소 모듈을 조합해 하나의 업무 목적과 typed result를 완결하는
   application service
3. **전체 workflow**: 국소 파이프라인, 조건 분기, 사람 대기, 재개 지점을 연결한 versioned
   orchestration
4. **전달 interface**: Python script, CLI, API, worker, Web App에서 같은 pipeline/workflow를 호출

핵심 원칙은 다음과 같다.

- 업무 로직은 `src/axcalib` 안에만 둔다.
- 실행용 Python script는 argument/file 입출력과 library 호출만 담당한다.
- API, CLI, worker는 script를 실행하지 않고 같은 library object를 직접 호출한다.
- Web App은 workflow를 재구현하지 않고 API가 제공하는 상태와 command를 사용한다.
- workflow graph는 domain state machine을 대체하거나 우회하지 않는다.
- 모델 출력은 pipeline result의 일부일 뿐 관리자 전용 final transition 권한을 갖지 않는다.

## 2. 용어와 책임

| 용어 | 책임 | 하지 않는 일 |
|---|---|---|
| Element module | 한 domain capability와 port 제공 | 전체 업무 순서 결정 |
| Pipeline step | 검증, 변환, port 호출 등 작은 실행 단위 | 임의 전역 상태 변경 |
| Local pipeline | 하나의 use case를 시작부터 typed result까지 완결 | 다른 업무의 상태기계 복제 |
| Total workflow | pipeline 연결, 분기, wait/resume, checkpoint | domain invariant 변경 |
| Delivery adapter | HTTP/CLI/script/UI 입력을 command로 변환 | 평가·승인 로직 보유 |
| Runtime profile | 승인된 adapter와 설정을 dependency injection | secret 값을 report에 노출 |

`module`이라는 이름의 범용 폴더는 만들지 않는다. dossier, ingest, retrieval처럼 실제 bounded
capability 이름을 package로 사용한다.

## 3. 계층과 의존 방향

~~~text
Python scripts / CLI / FastAPI / Worker / Web API client
                         |
                  Workflow facade
              start / resume / inspect
                         |
          Versioned total workflow definitions
       branch / wait-human / checkpoint / compensate
                         |
               Reusable local pipelines
       freeze / prepare / retrieve / evaluate / report
                         |
     Domain modules + ports + deterministic state machine
                         |
       FS / DB / Docling / Qdrant / Model / Notification
                    adapter implementations
~~~

허용 import 방향은 위에서 아래다. domain과 pipeline은 FastAPI, Typer, React, GitLab SDK,
SMTP 구현을 import하지 않는다. adapter는 domain port를 구현하지만 domain이 adapter를 알지
못한다.

## 4. Pipeline 공통 계약

첫 구현은 범용 DAG framework가 아니라 작은 typed Protocol과 명시적 Python class를 사용한다.
아래는 목표 API 모양이며 이름과 field는 WP-01 contract test에서 고정한다.

~~~python
RequestT = TypeVar("RequestT")
OutputT = TypeVar("OutputT")

class Pipeline(Protocol[RequestT, OutputT]):
    pipeline_id: str
    pipeline_version: str

    def run(
        self, request: RequestT, *, context: PipelineContext
    ) -> PipelineRun[OutputT]: ...

    async def arun(
        self, request: RequestT, *, context: PipelineContext
    ) -> PipelineRun[OutputT]: ...
~~~

`run`과 `arun`은 input, output, validation, error 의미가 같다. script/CLI는 주로 `run`, API와
worker는 `arun`을 사용한다.

### 4.1 PipelineContext

실행 중 암묵적 global을 사용하지 않고 다음 문맥을 명시적으로 전달한다.

- run_id, correlation_id, idempotency_key
- project_id, stage, actor와 권한 context
- expected dossier revision, snapshot_id/hash
- workflow_id/version, pipeline_id/version
- rubric/checklist/policy/corpus/model profile version
- deadline, cancellation scope, trace context
- runtime profile 이름과 선택된 adapter id/version

API key 값이나 원문 전체는 context와 audit metadata에 넣지 않는다.
port 구현체는 runtime container가 pipeline 생성자에 주입하며 context를 service locator로
사용하지 않는다.

### 4.2 PipelineRun

`bool` 성공값 하나로 결과를 축약하지 않는다.

| status | 의미 |
|---|---|
| succeeded | 결과와 필수 side effect가 계약대로 완료됨 |
| waiting_human | 승인·추가자료 등 사람 command를 기다림 |
| blocked | 정책·필수입력·승인이 없어 진행 불가 |
| stale | 기준 revision이 바뀌어 자동 적용 불가 |
| failed_retryable | 일시 장애이며 같은 idempotency key로 재시도 가능 |
| failed_terminal | validation 또는 정책 위반으로 같은 입력 재시도 불가 |
| cancelled | 명시적 취소 또는 deadline 종료 |

결과에는 최소한 `output`, `events`, `warnings`, `evidence_refs`, `artifact_refs`, `metrics`,
`checkpoint_ref`, `audit_ref`를 둘 수 있다. 실제 field는 pipeline별 Pydantic output model로
좁힌다.

### 4.3 Side effect 규칙

- 파일, DB, model, retrieval, notification 접근은 port를 통해서만 수행한다.
- mutation pipeline은 expected_revision, actor, idempotency_key를 요구한다.
- dossier mutation과 notification outbox 기록은 같은 local transaction에 둔다.
- 외부 메일/GitLab 전달은 commit 뒤 idempotent worker가 처리한다.
- pipeline 간 분산 transaction을 만들지 않고 durable checkpoint와 보상 command를 사용한다.
- retry가 새 평가, 새 알림, 새 final decision을 중복 생성하지 않아야 한다.

## 5. 요소 모듈 계약

| 모듈 | 대표 입력 | 대표 출력/port |
|---|---|---|
| dossier | command, expected revision | validated dossier, snapshot, transition event |
| ingest | ArtifactRef | EvidenceDocument, locator, parse warning |
| retrieval | stage query, filters | RetrievalResult, corpus snapshot, comparison context |
| evaluation | snapshot, rubric, evidence | criterion findings, recommendation |
| calibration | model/rule findings | disagreement와 confidence diagnostics |
| reports | typed evaluation result | Markdown/JSON artifact |
| notifications | ReviewRequest | outbox/delivery reference |
| audit | run event와 version manifest | append-only audit reference |

각 모듈은 독립 unit test와 fake/in-memory adapter를 제공한 뒤 local pipeline에 연결한다.

## 6. 초기 국소 파이프라인 카탈로그

| pipeline_id | 업무 목적 | 주요 결과 |
|---|---|---|
| dossier.initialize | 신규 dossier 생성 | revision 1 dossier |
| dossier.update | progress/KPI/artifact/change 갱신 | 새 revision 또는 conflict |
| dossier.freeze | 평가 입력 고정 | immutable snapshot |
| evidence.prepare | artifact parse/normalize/locator 생성 | EvidenceBundle |
| cases.retrieve | stage-aware 유사사례 검색 | RetrievalResult |
| registration.evaluate | 등록 기준 평가초안 생성 | RegistrationEvaluationReport |
| review.request | 관리자 검토요청과 outbox 기록 | waiting_human ReviewRequest |
| registration.decide | 관리자 등록 결정 적용 | approved/rejected/needs_changes |
| completion.submit | 완료 제출 리포트와 승인 확인 | completion_registered 또는 blocked |
| completion.evaluate | 등록 baseline 대비 완료평가 초안 | CompletionEvaluationReport |
| completion.decide | 관리자 완료 결정 적용 | accepted/not_accepted/needs_changes |
| report.render | typed result를 전달 형식으로 변환 | Markdown/JSON artifact |

`registration.evaluate`와 `completion.evaluate`는 내부에서 evidence/retrieval/evaluation/report
모듈을 사용하지만 final state를 확정하지 않는다. `*.decide`는 관리자 actor와 대상 snapshot을
검증하고 domain state machine을 통해서만 전이한다.

## 7. 전체 workflow 조합

초기 workflow는 코드로 명시하고 registry에서 allowlist한다.

~~~text
two-gate-standard/v1

dossier.initialize/update
  → registration.evaluate
  → review.request
  → WAIT administrator registration decision
      ├─ rejected ───────────────→ END
      ├─ needs_changes ──────────→ dossier.update → registration.evaluate
      └─ approved
           → optional mentor assignment
           → repeated dossier.update
           → completion.submit
           → completion.evaluate
           → review.request
           → WAIT administrator completion decision
               ├─ needs_changes ─→ dossier.update → completion.submit
               ├─ not_accepted ──→ END
               └─ accepted ──────→ optional certification policy
~~~

### 7.1 조합으로 허용할 variation

- evaluator mode: deterministic, single, panel, adjudicated
- retrieval profile: null, lexical, approved vector/hybrid
- stage/rubric별 similarity portion
- report renderer: Markdown, JSON, 향후 PDF
- notification route: recording, GitLab MR, email 또는 승인된 조합
- batch wrapper와 priority/deadline policy

### 7.2 variation으로 변경할 수 없는 invariant

- 등록 승인 전 수행 시작 금지
- 관리자 HITL과 승인요청 알림 생략 금지
- 배정된 mentor의 완료 제출 승인 우회 금지
- completion 평가의 approved registration baseline 생략 금지
- snapshot/revision/stale 검증 생략 금지
- Agent에 final decision 권한 부여 금지
- 실제 데이터의 access/security policy 완화 금지

### 7.3 초기 workflow recipe 후보

| workflow_id | 적용 사례 | 종료/제약 |
|---|---|---|
| two-gate-standard/v1 | 등록부터 완료판정까지 공식 흐름 | 두 관리자 HITL 필수 |
| registration-readiness/v1 | 제출 전 schema/evidence/KPI 사전점검 | advisory report, 승인 상태전이 없음 |
| registration-review/v1 | 등록평가와 관리자 결정을 독립 운영 | waiting_human 뒤 관리자 command 필요 |
| completion-reassessment/v1 | 고정 snapshot의 완료평가 재검토 | 기존 결정을 덮어쓰지 않고 별도 run 생성 |
| portfolio-draft-batch/v1 | 여러 과제의 평가초안 생성 | item별 실패/상태 분리, 자동 final decision 없음 |
| retrieval-benchmark/v1 | corpus/query/retriever 품질비교 | dossier 상태를 변경하지 않음 |

이 recipe들은 새로운 평가 로직이 아니라 동일 pipeline의 연결과 실행정책만 다르게 한다. 공식
상태를 변경하는 recipe는 항상 domain precondition과 사람 command를 통과한다.

## 8. Workflow definition과 registry

MVP에서 사용자 YAML로 임의 Python class나 import path를 실행하지 않는다. registry에는
검증된 `workflow_id/version`과 `pipeline_id/version`만 등록한다.

Workflow definition은 다음을 선언한다.

- node id와 참조 pipeline id/version
- input/output mapping
- 선행조건과 domain transition guard
- branch condition의 허용 enum
- human wait role와 resume command schema
- checkpoint와 timeout/retry policy
- 실패 전파 또는 보상 command

workflow 실행기 자체는 assessment 의미를 알지 못한다. domain command 결과만 읽어 다음 노드를
결정한다.

## 9. Interface 적용

### 9.1 Working Python script

~~~python
from axcalib.runtime import create_runtime
from axcalib.pipelines.registration import RegistrationEvaluationRequest

runtime = create_runtime(profile="offline")
result = runtime.pipelines.registration_evaluate.run(
    RegistrationEvaluationRequest.from_path("AXC-demo.axc.yaml"),
    context=runtime.context(actor="project_owner"),
)
~~~

`scripts/pipelines/run_registration_review.py` 같은 script는 argument parsing, runtime 생성,
result 직렬화와 exit code만 담당한다. pipeline 단계나 판정 규칙을 script에 복사하지 않는다.

### 9.2 CLI

Typer command는 request model을 만들고 같은 pipeline 또는 workflow facade를 호출한다. CLI
전용 평가 규칙을 두지 않는다.

### 9.3 API와 worker

FastAPI route는 HTTP/auth context를 command로 변환한다. 짧은 작업은 결과를 반환하고 긴 작업은
workflow run을 생성해 `202 + run_id`를 반환한다. worker는 같은 registry와 checkpoint를 통해
재개한다.

### 9.4 Web App

Web App은 `workflow_id/version`, 현재 node, wait reason, checklist, allowed commands, report와
audit reference를 표시한다. 브라우저가 다음 상태를 계산하거나 final transition을 직접 쓰지
않는다.

## 10. 제안 디렉터리

~~~text
src/axcalib/
  core/
  schemas/
  dossier/
  ingest/
  retrieval/
  evaluation/
  calibration/
  reports/
  notifications/
  audit/
  pipelines/
    base.py
    context.py
    result.py
    registry.py
    dossier.py
    evidence.py
    registration.py
    completion.py
    review.py
  workflows/
    base.py
    registry.py
    two_gate.py
  runtime/
    container.py
    profiles.py
  cli/
  api/
scripts/pipelines/
  run_dossier_freeze.py
  run_registration_review.py
  run_completion_review.py
  run_two_gate_workflow.py
~~~

현재 `src/axcalib/workflows/two_gate.py`는 P1 reference state machine이다. 위 구조로 이동하거나
확장할 때 공개 import 호환성과 기존 테스트를 유지한다.

## 11. 구현 cadence와 Work Package 연결

모든 capability는 다음 순서로 납품한다.

1. domain schema/port와 invariant
2. element module 구현과 unit test
3. local pipeline class와 in-memory integration test
4. 실제로 실행되는 synthetic Python script
5. pipeline eval/재현성 기록
6. 안정된 pipeline을 CLI/API/worker에 노출
7. Web App에서 같은 API command와 run state를 사용

Work Package 적용:

| WP | pipeline 산출물 |
|---|---|
| WP-01 | PipelineContext/Run/Registry 최소계약, dossier.initialize/update/freeze, working script |
| WP-02 | evidence.prepare와 parser adapter contract |
| WP-03 | registration.evaluate, completion.evaluate, report.render의 deterministic baseline |
| WP-04 | cases.retrieve와 corpus/index pipeline |
| WP-05 | model evaluator를 기존 evaluation pipeline에 주입; 별도 workflow를 복제하지 않음 |
| WP-06 | total workflow runner, wait/resume/checkpoint, CLI/API/worker parity |
| WP-07 | Web App이 workflow run과 allowed command를 소비 |

## 12. 검증 전략

- module unit: 순수 계산, schema, error와 side-effect port 호출
- local pipeline integration: in-memory repository, fake parser/retriever/model/notifier
- workflow scenario: approve, reject, needs_changes, stale, retry, notification failure
- import boundary: core/domain/pipeline에서 FastAPI·Docling·Qdrant 구현 import 금지
- interface parity: 같은 fixture를 script/CLI/API로 실행해 같은 구조적 result 확인
- resume: waiting_human checkpoint에서 authorized command로 정확히 한 번 재개
- idempotency: 같은 key 재시도가 평가·알림·decision을 중복 생성하지 않음
- audit: workflow/pipeline/module/config version이 run manifest에 연결됨

## 13. 수용기준

구현 방식이 정착됐다고 말하려면 다음을 만족해야 한다.

- 국소 pipeline이 transport framework 없이 import·실행된다.
- working script에 domain 판단과 상태전이 규칙이 복제되지 않는다.
- CLI/API/worker가 같은 pipeline/workflow registry를 호출한다.
- 각 pipeline input/output/status가 Pydantic으로 검증된다.
- total workflow의 branch가 domain state machine의 허용 전이와 일치한다.
- `waiting_human`, `stale`, retryable/terminal failure가 success와 구분된다.
- workflow run을 중단·재개해도 snapshot, version, idempotency가 보존된다.
- pipeline을 교체하거나 추가해도 관리자 HITL 등 invariant를 config로 끌 수 없다.

## 14. 위험과 통제

| 위험 | 통제 |
|---|---|
| 지나치게 작은 pipeline의 폭증 | 하나의 독립 업무 결과와 재사용자가 있을 때만 pipeline으로 승격 |
| 범용 workflow engine 조기개발 | 명시적 Python composition부터 시작하고 실제 variation이 쌓인 뒤 일반화 |
| context가 범용 dictionary가 됨 | immutable typed context와 pipeline별 request 사용 |
| script/API별 로직 분기 | thin adapter와 interface parity contract test |
| workflow가 state machine을 우회 | 모든 mutation은 domain command와 transition guard 통과 |
| pipeline 버전 조합 불일치 | allowlisted registry, compatibility test, run manifest |
| 부분 side effect와 중복 알림 | local transaction + outbox + idempotency + checkpoint |
| 사용자 정의 graph의 보안위험 | MVP에서는 arbitrary import/expression 금지, 승인된 recipe만 허용 |

## 15. 당장 구현할 가장 작은 slice

WP-01의 첫 slice는 `dossier.freeze/v1alpha1`이다.

1. typed request/context/result 정의
2. dossier revision 검증과 canonical SHA-256 snapshot 생성
3. in-memory/filesystem port 뒤에 저장
4. stale/invalid/duplicate 결과 분리
5. `scripts/pipelines/run_dossier_freeze.py`에서 실행
6. 같은 pipeline을 향후 CLI/API가 호출할 수 있음을 contract test로 검증

이 slice에는 FastAPI, Web, 실제 모델, Vector DB, 실제 데이터가 필요하지 않다.
