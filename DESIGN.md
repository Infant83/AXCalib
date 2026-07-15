---
document_type: architecture_and_product_design
project: AXCalib
baseline: v0.3-p1
created_at: 2026-07-12
updated_at: 2026-07-16
timezone: Asia/Seoul
status: g3_intelligence_reference_implemented_hardening_pending
---

# AXCalib Architecture와 App Design

## 1. 설계 목표

AXCalib는 문서를 한 번 채점하는 도구가 아니라, 과제의 약속과 수행 증거가 시간에 따라 쌓이고 두 번의 공식 평가 Gate를 통과하는 과정을 다룬다. 설계의 중심 객체는 Agent나 채팅 세션이 아니라 **versioned Project Dossier**다.

2026-07-16 구현 기준으로 filesystem dossier/snapshot, hash-bound review policy, 제한된 PPTX
OOXML+sidecar, optional Docling manifest, deterministic/structured model evaluator, synthetic lexical
retrieval, report, recording notification과 두 Gate pipeline이 G3 reference slice로 연결됐다.
slide-render/VLM, embedding/Vector DB, panel/calibration, 운영 API/Web 설계는 여전히 Target이며
구현 완료가 아니다.

제품은 다음 네 층으로 분리한다.

1. Domain: dossier, rubric, evidence, state transition, result schema
2. Intelligence: parser, retrieval, evaluator, model panel, calibration
3. Delivery: Python Library, CLI, API, batch worker
4. Experience: reviewer Web App와 운영 dashboard

Core Domain은 나머지 층 없이도 실행되고 테스트되어야 한다.

## 2. 핵심 설계 원칙

- Library first: 모든 인터페이스는 같은 application service를 호출한다.
- Human authority is visible: Agent 제안과 권한 있는 사람의 결정을 화면·schema·감사기록에서 분리한다.
- Progressive disclosure: 첫 API와 기본 설정은 작게 두고 전문 profile과 typed option을 단계적으로 연다.
- Composable pipelines: 요소 모듈을 국소 pipeline으로 완결하고 전체 workflow는 이를 연결한다.
- Thin delivery: working script, CLI, API, worker, Web에는 domain 로직을 복제하지 않는다.
- One dossier, many immutable revisions: 사용자 기준 파일은 하나지만 평가 입력은 고정한다.
- Deterministic gates around probabilistic models: 상태·스키마·정책은 코드가, 의미 평가는 모델과 사람이 담당한다.
- Evidence before score: 점수보다 locator와 증거 충분성을 먼저 만든다.
- Human decision is a distinct object: 모델 평가와 최종 검토를 같은 필드에 덮어쓰지 않는다.
- Mandatory HITL notification: 관리자 승인요청이 기록되지 않으면 review pending으로 전이하지 않는다.
- Optional mentor, conditional guard: 멘토는 선택이지만 배정 후 완료 제출에는 mentor 승인이 필요하다.
- Stage-aware retrieval: 등록심의와 완료평가의 유사성 의미를 분리한다.
- Provider and framework independence: Qwen3.5, Deep Agents, Qdrant를 교체 가능한 adapter로 둔다.
- Async by contract, bounded by policy: 병렬성은 허용하되 무제한 fan-out은 금지한다.
- Sensitive by default: 원문, 파생텍스트, embedding, model output을 모두 보호 대상 데이터로 본다.
- Review cockpit, not chatbot: Web App의 주 인터페이스는 process/evidence/review이며 chat은 보조 기능이다.

## 3. System Context

~~~text
                         ┌─────────────────────────┐
                         │ Reviewer / Operator UI  │
                         │ FE selection pending    │
                         │ Enterprise workbench    │
                         └───────────┬─────────────┘
                                     │ OpenAPI + SSE
┌───────────────┐          ┌─────────▼─────────┐          ┌─────────────────┐
│ CLI / Python  ├─────────►│ AXCalib Service   ├─────────►│ Worker / Batch  │
│ Library User  │          │ FastAPI adapter   │          │ bounded jobs    │
└───────┬───────┘          └─────────┬─────────┘          └────────┬────────┘
        │                            │                              │
        └────────────────────────────┼──────────────────────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │ Total Workflows     │
                          │ + Local Pipelines   │
                          └───┬────┬────┬───────┘
                              │    │    │
               ┌──────────────┘    │    └────────────────┐
               ▼                   ▼                     ▼
     ┌──────────────────┐ ┌─────────────────┐  ┌──────────────────┐
     │ Dossier/Artifact │ │ Retrieval Store │  │ Model Gateways   │
     │ FS/S3 + DB       │ │ Qdrant          │  │ on-prem endpoints│
     └──────────────────┘ └─────────────────┘  └──────────────────┘
~~~

API, CLI, worker는 domain model을 복제하지 않는다. Web App의 상태도 API response를 별도 진실원천으로 재해석하지 않는다.

## 4. 모듈 경계

~~~text
core / schemas
       │
       ├── dossier + state machine
       ├── ingest / evidence ◄── Docling adapters
       ├── retrieval ports ◄── lexical / qdrant adapters
       ├── evaluation ◄── model ports / calibration
       ├── reports
       ├── notification ports ◄── recording / GitLab MR / email
       └── audit
             ▲
             │ compose capability modules
      reusable local pipelines
      freeze / prepare / retrieve / evaluate / review
             ▲
             │ connect branch / wait / resume
      versioned total workflows
      registration / execution / completion
             ▲
    scripts / CLI / API / worker / Web client
~~~

의존성 규칙:

- core, schemas, dossier는 model, Docling, Qdrant, FastAPI를 import하지 않는다.
- ingest는 EvidenceDocument를 반환하고 evaluation의 정책을 알지 못한다.
- retrieval은 case와 chunk를 찾지만 assessment를 확정하지 않는다.
- models는 구조화된 후보 판단을 반환하고 dossier를 직접 저장하지 않는다.
- local pipelines만 하나의 use case를 위해 여러 domain module과 port를 조합한다.
- total workflows는 검증된 pipeline id/version만 연결하고 domain invariant를 정의하지 않는다.
- working script, CLI, API, worker는 같은 pipeline/workflow facade를 호출한다.
- UI는 dossier file을 직접 수정하지 않고 revision-aware command를 호출한다.

### 4.1 Element Module → Local Pipeline → Total Workflow

요소 모듈은 capability, 국소 pipeline은 완결된 업무 목적, total workflow는 lifecycle 조합을
책임진다. 이 구분을 사용하면 등록심의 평가, 완료평가, 유사사례 검색을 독립 실행하면서도
표준 two-gate workflow에서 같은 구현을 재사용할 수 있다.

국소 pipeline의 공통 계약은 다음을 포함한다.

- typed request와 output
- immutable PipelineContext
- pipeline_id와 pipeline_version
- sync `run`과 async `arun`의 의미 일치
- succeeded, waiting_human, blocked, stale, retryable/terminal failure, cancelled 상태
- evidence/artifact/event/checkpoint/audit reference
- port를 통한 side effect와 mutation의 expected_revision/idempotency

total workflow는 local pipeline, 조건 분기, 관리자/mentor wait, durable checkpoint와 resume을
연결한다. workflow recipe로 mandatory HITL, notification, mentor guard, snapshot 검증을 끌 수
없다. 초기에는 명시적 Python composition과 allowlisted registry를 사용하고 arbitrary graph나
import path 실행은 허용하지 않는다.

working Python script는 argument parsing, runtime profile 생성, pipeline 호출, 결과 직렬화만
담당한다. FastAPI/CLI/worker는 script subprocess가 아니라 같은 library object를 직접 사용한다.
상세 catalog, interface 적용, WP별 납품 순서는
`docs/architecture/composable-pipeline-plan.md`, 결정 근거는 ADR-013을 따른다.

### 4.2 Visual Blueprint와 Module Control

architecture는 다음 세 view를 함께 유지한다.

- `workflow-blueprint.md`: 계층, 공식 two-gate, sequence, pipeline anatomy, module dependency,
  failure/resume, Delivery Wave의 Mermaid 원문
- `module-delivery-plan.md`: M00~M13의 상태, 입력·출력, 직접 선행조건, 첫 slice, test와 Exit Evidence
- `diagrams/workflow-at-a-glance.svg`: 비기술 이해관계자용 한 장 요약
- `../product/product-brief.md`와 `../manuals`: Excalibur 기억 장치, quickstart, 권한 구조도와 6컷 tutorial

Mermaid를 정확한 구조 기준으로, SVG를 커뮤니케이션 요약으로 사용한다. module/pipeline ID,
상태전이, dependency 또는 현재 구현상태가 바뀌면 세 view와 `PROJECT_STATE.md`를 같은 change
set에서 갱신한다. 구현되지 않은 node를 완료색으로 표시하지 않으며 다이어그램이 domain state
machine을 대신하지 않는다.

## 5. Canonical Project Dossier

### 5.1 파일 계약

- 확장자: .axc.yaml
- schema ID: axcalib.dossier/v1alpha1
- project_id: UUID4, 생성 후 불변
- display_id: 사람이 읽는 별도 식별자, 변경 가능하되 중복 금지
- timestamp: 저장은 UTC ISO 8601, 화면은 Asia/Seoul 표시
- revision: 성공한 mutation마다 1 증가
- content_hash: schema가 정의한 canonical JSON bytes의 SHA-256
- unknown field: alpha 단계에서는 명시적 extensions 아래만 허용

### 5.2 예시 구조

~~~yaml
schema_version: axcalib.dossier/v1alpha1
project_id: 2f993f6e-1d1e-41cb-9846-a6e848e381c3
display_id: AXC-2026-000123
revision: 7
updated_at: 2026-07-12T03:00:00Z

identity:
  title: 고객문의 분류 AX 과제
  project_type: workflow_automation
  owner_ref: user:pseudonym-001
  organization_ref: org:group-a
  access_classification: internal

lifecycle:
  stage: execution
  status: in_progress
  registration_gate: approved
  completion_gate: not_submitted

registration:
  proposal:
    problem: "..."
    objective: "..."
    scope: ["..."]
    kpis:
      - kpi_id: kpi-01
        name: 처리시간
        baseline: {value: 20, unit: minute}
        target: {value: 10, unit: minute}
        measurement_method: "..."
  artifacts: [artifact:pptx-registration-v2]
  rubric_ref: rubric:ax-project-registration@1.0.0
  snapshot_ref: snapshot:registration-r3
  evaluation_runs: [run:reg-20260712-001]
  reviewer_decision:
    status: approved
    reviewer_ref: reviewer:pseudonym-101
    decided_at: 2026-07-12T02:00:00Z
    note: "..."

execution:
  progress_entries:
    - entry_id: progress-001
      occurred_at: 2026-07-12
      author_ref: user:pseudonym-001
      summary: "..."
      evidence_refs: [artifact:test-log-01]
  mentor_notes:
    - note_id: mentor-001
      mentor_ref: mentor:pseudonym-201
      occurred_at: 2026-07-12
      guidance: "..."
      follow_up: "..."
  deliverables: [artifact:prototype-v1]
  kpi_results:
    - kpi_id: kpi-01
      observed: {value: 12, unit: minute}
      measured_at: 2026-07-12
      method: "..."
      evidence_refs: [artifact:kpi-log-01]

completion:
  summary: null
  artifacts: []
  rubric_ref: rubric:ax-project-completion@1.0.0
  snapshot_ref: null
  evaluation_runs: []
  reviewer_decision: null

certification:
  level_framework_ref: null
  decision: null

artifact_refs:
  - artifact_id: artifact:pptx-registration-v2
    media_type: application/vnd.openxmlformats-officedocument.presentationml.presentation
    uri: artifacts/sha256/ab/cd/...
    sha256: "..."
    source_name: registration-v2.pptx
    access_classification: internal

audit:
  created_at: 2026-07-11T01:00:00Z
  created_by: user:pseudonym-001
  latest_event_ref: event:000019
  extensions: {}
~~~

### 5.3 단일 파일과 audit history의 조화

사용자가 열고 갱신하는 파일은 위 dossier 하나다. 그러나 감사와 충돌 복구를 위해 저장 계층은 다음을 별도로 보존한다.

- revision snapshot: 전체 dossier의 immutable copy
- artifact: PPTX, PDF, 이미지, 로그, 추출 JSON
- evaluation run manifest: 모델·프롬프트·corpus·시간·비용
- full report: criterion 결과와 유사사례 상세
- append-only audit event: 누가 어떤 command로 무엇을 바꿨는지

dossier 안에는 최신 상태, 중요한 요약, 위 객체들의 reference를 기록한다. 이 구조는 “하나의 파일로 과제를 관리한다”는 사용자 경험과 원문·평가 재현성을 함께 만족시킨다.

### 5.4 Mutation과 동시성

모든 변경 command는 expected_revision을 받는다.

~~~text
read revision 7
→ validate command
→ build candidate revision 8
→ write temp file
→ validate full candidate
→ atomic replace if current revision == 7
→ append audit event
~~~

현재 revision이 달라지면 409/revision_conflict를 반환한다. 평가 run은 base_snapshot_hash를 가지며, 완료 후 현재 dossier가 같은 base revision일 때만 자동 적용할 수 있다. 그렇지 않으면 stale_result로 보관하고 사람이 비교·병합한다.

사용자·멘토 기록은 append-first다. 잘못된 항목을 수정할 때 원 항목을 조용히 바꾸지 않고 supersedes 또는 correction_ref를 남긴다.

## 6. Lifecycle State Machine

### 6.1 기본 상태

~~~text
draft
  │ submit registration
  ▼
registration_ready
  │ freeze + start
  ▼
registration_under_review
  │ publish Agent draft + notification
  ▼
registration_hitl_pending
  ├──► registration_needs_changes ──revise/resubmit──► registration_ready
  ├──► registration_rejected ──► process terminated
  └──► registration_approved
                 │ start execution
                 ▼
             in_progress
                 │ completion submission report
                 ▼
          completion_ready
                 │ request mentor/owner approval
                 ▼
      completion_approval_pending
                 │ approve and register
                 ▼
        completion_registered
                 │ freeze + evaluate
                 ▼
       completion_under_review
                 │ publish Agent draft + notification
                 ▼
          completion_hitl_pending
          ├──► completion_needs_changes ──revise/resubmit──► completion_ready
          ├──► completion_not_accepted
          └──► completion_accepted
                          │ optional certification policy
                          ▼
                certification_review
                   ├──► certification_on_hold
                   └──► certified
~~~

withdrawn과 cancelled는 정책에 따라 여러 pre-final 상태에서 갈 수 있는 terminal 상태다.

### 6.2 전이 책임

| 전이 | 자동 가능 | 사람 결정 필요 |
|---|---:|---:|
| draft → registration_ready | 예, schema/checklist 충족 시 | 아니오 |
| registration_ready → under_review | 예, snapshot 생성 후 | 아니오 |
| registration_under_review → registration_hitl_pending | Agent draft 후 가능 | notification 필수 |
| registration_hitl_pending → needs_changes/rejected/approved | 아니오 | 관리자 필수 |
| approved → in_progress | 정책에 따라 | 시작 승인 권장 |
| in_progress → completion_ready | 예, 최소 제출요건 충족 시 | 제출자 확인 |
| completion_ready → completion_registered | 아니오 | mentor 배정 시 mentor, 미배정 시 owner/admin |
| completion_registered → under_review | 예, snapshot 생성 후 | 아니오 |
| completion_under_review → completion_hitl_pending | Agent draft 후 가능 | notification 필수 |
| completion_hitl_pending → needs_changes/not_accepted/accepted | 아니오 | 관리자 필수 |
| accepted → certified | 아니오 | 인증권자 필요 |

Agent와 LLM에는 final transition repository 권한을 주지 않는다.

notification adapter가 실패하면 `*_hitl_pending` 전이를 완료하지 않는다. 서비스 구현에서는
review request와 outbox event를 같은 transaction에 기록하고 idempotent worker가 GitLab MR
또는 email delivery를 처리한다. 현재 offline slice는 RecordingNotifier로 fail-closed를
검증하지만 durable cross-file outbox는 아직 구현하지 않았다.

## 7. 등록심의 Pipeline

~~~text
1. Preflight
   schema, required artifacts, access policy, malware/type checks
2. Freeze
   dossier revision, rubric version, artifact hashes
3. Parse and Normalize
   Docling structure + slide rendering + evidence locators
4. Retrieve
   registration-stage historical cases, adapter/corpus/portion 기록
5. Deterministic Evaluation
   completeness, type, numeric consistency, mandatory conditions
6. Semantic Evaluation
   problem validity, objective/scope coherence, KPI measurability, feasibility
7. Model Panel
   independent structured assessments
8. Calibration
   disagreement, missing evidence, historical consistency, confidence diagnostics
9. Draft Report
   criterion findings, similar cases, risks, questions
10. Approval Notification
   GitLab MR, email 또는 offline recording event
11. Administrator HITL
   hallucination, bias, evidence, RAG/weight 검토
12. Final Decision
   approve, reject, request changes, override, record rationale
~~~

위 total flow는 `dossier.freeze`, `evidence.prepare`, `cases.retrieve`,
`registration.evaluate`, `report.render`, `review.request`, `registration.decide` 국소 pipeline의
조합으로 구현한다. 관리자 decision은 evaluation pipeline 안에 넣지 않는다.

등록심의의 핵심 비교 단위:

- 문제 정의와 AX 적용 필요성
- 목표와 범위
- 수행계획·자원·일정의 현실성
- KPI baseline, target, unit, 측정방법
- 보안·데이터·윤리 위험
- 중복 또는 과거 유사과제와의 차별성

## 8. 수행 단계 Update

수행 중에는 전체 dossier를 매번 모델이 재평가하지 않는다. command 단위로 유효성을 검사하고 필요한 파생지표만 갱신한다.

지원 update:

- progress entry 추가
- mentor note 추가
- deliverable/artifact version 추가
- risk/issue/change record 추가
- KPI observation 추가
- 등록 당시 목표·범위·KPI의 change request 연결

등록 당시 approved baseline을 직접 덮어쓰지 않는다. 변경이 필요하면 change request와 승인기록을 만들고 완료평가에서 original baseline, approved change, final result를 함께 비교한다.

멘토 배정은 registration approval 뒤 선택적으로 수행한다. mentor가 없으면 project owner가
계속 수행할 수 있다. mentor_ref가 있으면 완료 제출 등록 전에 해당 mentor의 approval event가
필수이며 owner가 이를 우회할 수 없다.

## 9. 완료평가 Pipeline

~~~text
1. Draft completion submission report
2. Mentor approval when assigned; otherwise owner/admin confirmation
3. Register completion submission
4. Completion preflight and final dossier revision freeze
5. Load approved registration baseline
6. Parse final artifacts and KPI evidence
7. Build baseline-to-result diff
8. Retrieve completion-stage historical cases and record portion
9. Deterministic, semantic, multimodal evaluation
10. Independent model panel and calibration
11. Draft completion evaluation report
12. Administrator approval notification
13. Administrator HITL and final completion decision
14. Optional AX Level/certification policy
~~~

완료 흐름은 `completion.submit`, `dossier.freeze`, `evidence.prepare`, `cases.retrieve`,
`completion.evaluate`, `report.render`, `review.request`, `completion.decide`를 연결한다. 등록
baseline loading과 mentor guard는 workflow option이 아니라 domain precondition이다.

완료평가의 핵심 비교 단위:

- 등록 당시 목표와 최종 수행내용의 일치·승인된 변경
- 산출물의 존재, 작동, 재현성, 품질
- KPI baseline/target/observed와 측정 신뢰성
- 멘토 지적사항의 반영
- 위험, 실패, 한계, 후속 운영계획
- 과거 유사과제 대비 결과의 일관성과 특이점

## 10. Evaluation Result Schema

criterion별 최소 결과:

| 필드 | 의미 |
|---|---|
| criterion_id/version | 적용 기준 |
| assessment | met, partially_met, not_met, insufficient_evidence, not_applicable |
| observation | 제출물에서 확인한 사실 |
| evidence_refs | artifact/page/slide/object/field locator |
| deterministic_checks | 규칙 기반 결과 |
| model_findings | 모델별 독립 결과 |
| similar_case_refs | 과거 사례와 score |
| commonalities/differences | 사례 비교 |
| retrieval_status/adapter | not_configured, empty, completed와 구현체 |
| similarity_portion | historical-consistency contribution과 계산근거 |
| evidence_adequacy | 근거의 양·출처·직접성 |
| disagreement | 모델·규칙·사례 간 충돌 |
| risk_flags | 오판·누락·정책 위험 |
| follow_up_questions | 사람이 확인할 질문 |
| reviewer_action | accept/edit/reject/request_evidence |
| agent_recommendation | Agent의 통과·미통과·자료부족 제안 |
| administrator_decision | 관리자 actor, 시각, 사유를 포함한 최종결정 |
| notification_ref | 승인요청 delivery/outbox reference |
| audit_ref | run manifest |

confidence를 모델의 막연한 자기확신 숫자로 사용하지 않는다. 최소한 다음을 분리한다.

- evidence_coverage
- evidence_reliability
- model_agreement
- rule_consistency
- historical_consistency

최종 confidence 또는 review_priority는 위 신호에서 계산하며 공식 계산식은 calibration dataset으로 검증한다.

## 11. Historical Case와 Vector DB

### 11.1 Corpus 분리

논리적으로 다음 namespace를 분리한다.

- registration_cases
- completion_cases
- rubric_and_policy
- mentor_patterns 선택

동일 Qdrant collection 안에 둘 경우 review_stage와 access_classification payload index를 필수로 만든다. 보안등급이 다른 corpus를 단순 metadata filter만으로 공유할지는 Governance가 결정한다.

### 11.2 Ingestion 흐름

1. source 등록과 hash 계산
2. file type, malware, access policy 검사
3. 개인정보 비식별 또는 pseudonymization
4. Docling/전용 parser로 normalized document 생성
5. project/criterion/stage 기반 semantic section 생성
6. chunk마다 source locator와 context header 부착
7. dense embedding과 optional sparse representation 생성
8. Qdrant batch upsert
9. corpus manifest와 counts/checksum 저장
10. labeled query set으로 retrieval evaluation

특정 파일을 embed하는 공개 루틴은 다음 의미를 갖는다.

~~~python
result = await axcalib.cases.aingest(
    path="past-case.axc.yaml",
    corpus="ax-projects-v1",
    stages=["registration", "completion"],
    access_policy="internal",
)
~~~

이 함수는 원문을 벡터 하나로 만드는 것이 아니라 parse → section → chunk → embed → index → manifest 전 과정을 수행한다.

### 11.3 Chunk 전략

- dossier field와 rubric criterion 경계를 우선한다.
- PPTX는 slide 단위만 고집하지 않고 제목·section·표·chart 설명을 연결한다.
- 각 chunk는 case_id, stage, criterion_ids, locator를 가진다.
- 동일 case의 chunk 여러 개가 top-k를 독점하지 않도록 case-level aggregation한다.
- registration query에 completion outcome이 노출되어 평가를 오염시키지 않도록 outcome-blind retrieval 모드를 둔다.

### 11.4 Query와 rerank

초기 흐름:

~~~text
metadata/access filter
→ lexical top 20 + dense top 20
→ Reciprocal Rank Fusion
→ Qwen3-Reranker-0.6B 후보로 rerank top 8
→ case-level aggregate top 5
→ commonality/difference extraction
~~~

score의 의미와 범위는 backend별로 다르므로 raw score를 합격 임계값으로 사용하지 않는다. corpus snapshot, query version, embedding/reranker version을 report에 남긴다.

### 11.5 Retrieval Evaluation

- Recall@k: 관련 사례가 후보에 포함되는가
- nDCG@k: 사람이 정한 relevance 순서와 맞는가
- criterion coverage: 필요한 기준별 사례가 포함되는가
- stage leakage: completion outcome이 registration 판단에 부당하게 노출되는가
- subgroup bias: 유형·조직·문서길이에 따른 검색 편차
- citation validity: 결과가 실제 source locator로 열리는가

### 11.6 Embedding model이 없는 P1/P2 mode

- `NullRetriever`는 검색 미구성을 `not_configured`로 명시한다.
- `LexicalRetriever`는 synthetic corpus에서 stage filter와 deterministic ranking을 검증한다.
- stage별 `similarity_portion` 기본값은 0.0이며 retrieval 결과를 리포트 참고자료로만 넣는다.
- vector/hybrid adapter는 같은 port를 구현하고 새 corpus/index namespace로 추가한다.
- raw similarity는 점수가 아니라 공통점·차이점·한계를 만드는 입력이다.
- portion은 `0.0..1.0`; 0.25 초과는 policy warning과 Evaluation Owner 승인을 요구한다.
- portion이 양수인데 retrieval이 unavailable이면 다른 항목에 조용히 재분배하지 않는다.

## 12. Model Gateway와 Agent

### 12.1 OpenAI-compatible 최소 계약

모델 adapter는 최소 다음 설정을 받는다. base_url은 OpenAI-compatible API base를 뜻하며 /v1까지 포함하고 trailing slash는 설정 로드 시 제거한다.

~~~text
model
base_url
api_key_env
timeout_seconds
max_concurrency
capabilities
generation_profile
~~~

endpoint 확인은 일반 curl로 가능해야 한다.

~~~bash
curl "$OPENAI_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"<served-model-id>","messages":[{"role":"user","content":"health probe"}]}'
~~~

API key 값은 명령 예시, process listing, log에 출력하지 않는다. 실제 harness는 secret redaction과 env presence만 확인한다.

G3 reference adapter는 표준 `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`을 우선하고
사용자 호환 alias `OPENAPI_API_KEY`, `OPENAPI_BASE_URL`도 읽는다. model이 없으면 외부 기본값은
`gpt-5.5`이며 on-prem expert example은 `Qwen3.5-397B-A17B`다. OpenAI 공식 endpoint에는
Responses API, custom compatible endpoint에는 기본적으로 Chat Completions structured-output
dialect를 사용한다. retry, concurrency, usage/cost와 endpoint allowlist는 운영 전 남은 범위다.

### 12.2 Capability probe

OpenAI-compatible이라는 이름만으로 기능을 가정하지 않는다. endpoint 등록 시 다음을 probe하고 결과를 cache한다.

- chat completion
- vision input
- JSON/structured output
- tool calling
- streaming
- max context와 image limit
- seed 지원
- usage metadata

미지원 기능은 fallback하거나 명확히 실패한다. JSON mode가 없으면 text를 Pydantic으로 검증하고 제한된 repair cycle을 사용하되 원 출력과 오류를 보존한다.

### 12.3 Qwen3.5

- logical primary profile의 기본 계열
- PPTX slide image와 text evidence를 함께 평가하는 VLM 역할
- 정확한 model ID는 on-prem hardware와 품질 benchmark 후 확정
- model card, tokenizer, serving engine version을 run manifest에 기록
- thinking trace 원문을 저장하지 않고 structured answer만 요청

### 12.4 다중 모델

panel 실행 순서:

1. 동일 snapshot, rubric, evidence bundle을 모든 모델에 전달
2. 모델들이 서로의 결과를 보지 않고 독립 평가
3. schema validation과 evidence locator 확인
4. criterion별 assessment distribution 계산
5. rationale가 아니라 observation/evidence 차이를 비교
6. threshold 초과 시 adjudication 또는 human priority 상승

단순 평균보다 다음을 우선 표시한다.

- 판정 범주 분포
- 점수 범위와 중앙값
- 빠진 criterion
- 상충하는 evidence
- 특정 모델의 지속적 높음/낮음 편향
- model/temperature 반복 간 안정성

모델 weight는 expert-labeled calibration 성능이 확인되기 전 모두 동일하거나 결과 집계에서 사용하지 않는다.

### 12.5 Deep Agents

Deep Agents는 axcalib[deepagent] optional extra로 둔다. 적합한 용도:

- 많은 evidence 중 조사계획 세우기
- read-only evidence search
- criterion별 분석 subtask
- 추가 질문 초안

금지 용도:

- dossier 파일 직접 쓰기
- final state transition
- 임의 외부 URL/도구 실행
- rubric 또는 합격선 변경
- 하위 Agent의 결과를 검증 없이 최종 판정으로 사용

Agent tool은 domain command를 감싼 좁은 interface만 제공하고, 모든 write는 expected_revision과 사람 권한을 통과한다.

### 12.6 HITL Review Request와 Notification

평가초안이 완성되면 다음 객체를 분리해 기록한다.

- evaluation report: Agent recommendation, evidence, uncertainty, retrieval context
- review request: project/stage/revision, required administrator, due/status
- notification event: adapter, idempotency key, delivery status, retry/audit reference
- administrator decision: accept/edit/override/reject/request evidence와 rationale

NotificationPort의 우선 adapter는 다음과 같다.

- recording: offline test 전용
- GitLab Merge Request: versioned report/checklist review와 comment/approval 연계 후보
- email: 승인요청 요약과 review URL 전달 후보

운영 구현은 outbox pattern을 사용한다. secret과 원문 전체는 notification payload에 넣지 않는다.

## 13. Async와 Batch

### 13.1 Library API

첫 사용자가 알아야 할 facade의 현재 offline 모양은 다음과 같다.

~~~python
from axcalib import AXCalib

client = AXCalib.from_toml("config/axcalib.toml", workspace="output/review")
project = client.register_case("proposal.pptx", title="검토할 과제")
client.submit_registration(project.project_id)
result = client.evaluate(project.project_id, stage="registration")
# async boundary에서는 위 evaluate 대신 await client.aevaluate(...)를 사용한다.
~~~

- 기본 client는 network, GPU, DB를 암묵적으로 호출하지 않는 offline-safe profile이다.
- 현재 `from_toml`은 offline profile을 기본 조립한다. `live_model=True`이면 환경변수 기반
  OpenAI-compatible structured evaluator를, `enable_docling=True`이면 optional Docling adapter를
  추가한다. expert TOML의 임의 provider 조립과 운영 endpoint policy는 Target이다.
- 세부 service API는 evaluate_registration, evaluate_completion, ingest_cases를 제공할 수 있지만
  첫 quickstart에 모두 노출하지 않는다.
- async service는 aevaluate_registration, aevaluate_completion, aingest_cases처럼 `a` 접두어를 쓴다.
- local pipeline: `run(request, context=...)` / `arun(request, context=...)`
- total workflow: start, inspect, resume를 versioned workflow facade로 제공
- 두 API의 input/output schema와 오류 의미는 같다.
- CLI/API/worker는 같은 pipeline/workflow registry를 공유한다.
- async implementation은 AnyIO task group과 capacity limiter를 사용한다.
- sync wrapper가 event loop 안에서 중첩 실행되지 않도록 별도 Client를 제공한다.

### 13.2 병렬화 단위

병렬 가능:

- 서로 다른 artifact parse
- 독립 embedding batch
- 서로 다른 model panel call
- 서로 다른 dossier batch item

순차 또는 barrier 필요:

- dossier freeze 이전 evaluation
- parse 완료 이전 retrieval query 구성
- 독립 model call 완료 이전 disagreement
- reviewer decision 이전 final transition
- notification event 기록 이전 HITL pending transition
- mentor가 배정된 과제의 mentor approval 이전 completion registration

### 13.3 Batch manifest

~~~json
{"batch_id":"batch-001","item_id":"item-001","project_id":"...","stage":"registration","expected_revision":3,"mode":"panel","idempotency_key":"..."}
~~~

항목 상태:

- queued
- running
- succeeded
- failed_retryable
- failed_terminal
- stale
- cancelled

batch는 checkpoint와 per-item result를 기록한다. resume은 failed_retryable과 미실행 항목만 처리하고 성공 항목을 중복 실행하지 않는다.

### 13.4 Service worker

초기 API는 in-process worker port로 시작할 수 있지만 long-running parse/model job은 202 Accepted와 run_id를 반환한다. 파일럿에서는 Redis/RabbitMQ 기반 worker adapter를 선택하고 다음을 보장한다.

- at-least-once delivery를 고려한 idempotency
- retry with exponential backoff + jitter
- poison item 격리
- cancellation과 timeout
- per-model/per-GPU concurrency limit
- job progress event

## 14. 비정형 문서와 PPTX 분석

### 14.1 네 단계 분석

1. Structural: Docling으로 text, table, picture, hierarchy, metadata 추출
2. Visual: slide를 이미지로 렌더링하고 layout/chart/diagram을 VLM으로 분석
3. Domain: KPI, 일정, 역할, 결과, 위험을 typed evidence로 추출
4. Evaluation: rubric criterion과 evidence를 연결하고 판단

Docling 결과와 VLM 결과는 source와 confidence가 다른 별도 evidence로 유지한다.

### 14.2 정량 지표

- 원본 slide/page 수와 처리 성공 수
- OOXML object 대비 추출 object coverage
- text/table/chart/image count
- OCR/parse warning 수
- KPI value-unit-period 완전성
- 요구 criterion별 evidence count
- source locator가 없는 추출값 수
- 중복/상충 숫자 수
- chart axis/legend/unit 누락
- slide별 정보 밀도와 unreadable text flag

### 14.3 정성 분석

- 문제-해결안 연결
- 목표-활동-KPI 인과성
- 주장과 실제 증거의 정합성
- 결과의 재현 가능성
- 위험과 한계의 명시성
- 등록 당시 계획과 완료 결과의 변화 설명
- 멘토 지적 반영 여부

정성 결과도 criterion, observation, locator, limitation 구조를 사용한다. 시각적으로 세련된 PPTX라는 이유로 과제 품질을 높게 평가하지 않는다.

### 14.4 파서 안전

- URL fetch와 embedded executable 실행을 기본 차단
- 허용 MIME과 확장자를 모두 검사
- pptm 등 macro-enabled format은 기본 거부
- 압축폭탄, 과도한 page/object 수, 대용량 이미지 limit
- parser subprocess/resource limit
- 문서 내 prompt injection 문구를 명령이 아닌 untrusted content로 취급

## 15. 저장·배포 Profile

| 역할 | Offline 개발 | On-prem 파일럿 |
|---|---|---|
| Dossier | local filesystem | S3/MinIO + DB metadata |
| Snapshot | content-addressed files | versioned object bucket |
| Metadata/Audit | SQLite | PostgreSQL |
| Vector | in-memory/Qdrant local container | self-hosted Qdrant |
| Artifact | local artifacts/ | encrypted MinIO |
| Model | deterministic mock | vLLM/승인 endpoint |
| Queue | in-process | Redis/RabbitMQ adapter |
| Auth | local actor fixture | OIDC/사내 SSO |
| Observability | JSONL local | OpenTelemetry collector |

storage port:

- DossierRepository
- SnapshotRepository
- ArtifactRepository
- AuditRepository
- RunRepository
- VectorCaseRepository

각 repository는 tenant/access context를 명시적으로 받는다.

### 15.1 Runtime configuration

configuration은 composition root에서 한 번 검증하고 typed object로 주입한다.

~~~text
code-owned invariant
  > safe package default
  > selected TOML profile
  > environment secret/endpoint
  > allowlisted request option
  > policy guard reject/clamp
~~~

- `config/axcalib.toml`: 작은 synthetic/offline 기본값
- `config/axcalib.expert.example.toml`: on-prem model/retrieval/storage/notification 예시
- `docs/schemas/runtime-config.schema.json`: 허용 키·타입·범위의 기준
- unknown key는 무시하지 않고 실패한다.
- secret 값은 TOML이나 effective config에 넣지 않고 환경변수 이름만 둔다.
- HITL, 승인 알림, 사람 최종결정, stale/revision/mentor guard는 설정으로 끌 수 없다.
- run manifest에는 secret을 제거한 effective-config hash와 각 값의 source를 기록한다.
- Python 3.12 `tomllib` 호환을 위해 작성 문법은 TOML 1.0 범위로 제한한다.

## 16. Backend 전략

### 16.1 계층

- FastAPI route: HTTP validation, auth context, status code
- Workflow facade: versioned graph, branch, wait/resume, checkpoint
- Local pipeline: use case, transaction boundary, idempotency, typed result
- Domain: state/policy/schema
- Adapter: DB, object store, vector, model, parser

route와 working script에서 model call, file parse, 상태판정을 직접 수행하지 않는다.

### 16.2 API 처리 패턴

- pre-implementation 기준 artifact는 `docs/api/openapi.v1alpha1.json`이다.
- OpenAPI 3.1.0과 JSON Schema Draft 2020-12를 사용한다.
- 짧은 read/write: 동기 HTTP response
- parse/evaluation/index: 202 + run_id
- 진행상태: SSE 우선, polling fallback
- 결과 반영: expected_revision 확인 후 explicit apply command
- OpenAPI에서 TypeScript client와 Zod-compatible boundary를 생성
- request `options`는 `additionalProperties: false`인 allowlist이며, protected invariant field는 없다.
- API implementation과 generated SDK는 artifact example에 대한 contract test를 공유한다.
- OpenAPI 3.2 채택은 WP-06 generator/FastAPI/client 호환 spike 뒤 결정한다.

### 16.3 오류 모델

공통 error:

- schema_invalid
- transition_not_allowed
- revision_conflict
- snapshot_stale
- evidence_missing
- capability_not_supported
- policy_denied
- retryable_dependency_error
- terminal_dependency_error

HTTP message와 내부 stack trace를 분리하고 trace_id를 제공한다.

### 16.4 권한

기본 역할:

- submitter: 본인 과제 작성·제출
- mentor: mentor note와 feedback
- reviewer: 평가 초안 검토
- certification_owner: 최종 인증결정
- operator: job/corpus 운영
- auditor: read-only audit
- administrator: rubric/model/access 설정

역할만으로 충분하지 않으며 project/organization/access_classification scope를 함께 검사한다.

## 17. Frontend 전략

### 17.1 UX 목표

첫 화면에서 사용자는 “Agent가 인증한다”가 아니라 다음 순서를 읽어야 한다.

~~~text
증거 → 기준/Calibration → Agent 제안 → 알림 → 관리자 HITL → 사람 최종결정
~~~

Excalibur 비유는 onboarding/empty state/교육 자료에만 사용한다. review workbench에서는
rubric, evidence locator, revision, allowed command를 우선하며 칼 이미지를 권위의 자동 판정이나
gamification 보상처럼 사용하지 않는다.

평가자가 30초 안에 다음을 파악해야 한다.

- 과제 ID와 현재 Gate
- 지금 막힌 이유와 다음 책임자
- 어떤 revision이 평가됐는지
- 기준별 충족·자료부족·불일치 분포
- 근거를 어디서 확인할 수 있는지
- 모델들이 어디서 다르게 판단했는지
- 사람이 어떤 결정을 내려야 하는지

### 17.2 정보구조

~~~text
Portfolio
├── All Projects
├── Registration Queue
├── In Progress
├── Completion Queue
└── Blocked / Needs Evidence

Project
├── Overview
├── Registration Review
├── Execution Log
├── Completion Review
├── Evidence
└── Audit Timeline

Calibration
├── Model Agreement
├── Rubric Performance
├── Retrieval Quality
└── Boundary Cases

Administration
├── Rubrics
├── Level Frameworks
├── Model Profiles
├── Historical Corpora
└── Access Policies
~~~

### 17.3 핵심 화면

#### Portfolio / Process Board

- 상단: 전체, 등록대기, 수행중, 완료대기, 보완요청, 차단 건수
- stage별 column 또는 filterable table
- 과제 카드: display_id, title, owner, stage, due, blocker, evidence completeness
- batch selection과 evaluate 요청
- 기본은 table, kanban은 보조 view

#### Project Overview

- 헤더: display_id, 제목, revision, access class, owner
- 5단계 stepper: 작성 → 등록심의 → 수행 → 완료평가 → 인증
- 각 단계 아래 checklist 완료수, 담당자, 마지막 변경, blocker
- KPI baseline/target/current compact table
- next action card

#### Review Workbench

desktop 3-column:

~~~text
┌───────────────┬──────────────────────────────┬────────────────────┐
│ Criterion Nav │ Observation / Evidence       │ Models / Decision  │
│ filters/count │ source preview + comparison  │ disagreement/action│
└───────────────┴──────────────────────────────┴────────────────────┘
~~~

- 왼쪽: criterion 목록과 상태
- 중앙: 관찰, 원문 slide/page, 유사사례 공통점/차이
- 오른쪽: 모델별 결과, evidence adequacy, reviewer action
- 결정 전 unresolved/insufficient evidence를 명시적으로 확인
- bulk accept는 low-risk이며 disagreement 없는 항목에만 제한

#### Execution Timeline

- progress, mentor note, artifact, KPI observation, change request를 시간순 표시
- 등록 baseline과 승인된 변경을 구분
- KPI trend와 측정근거 연결
- 최신 revision만 보지 않고 correction/supersedes 관계 표시

#### Calibration Dashboard

- criterion × model heatmap
- model별 score distribution
- agreement rate와 boundary case
- evidence coverage 대 disagreement scatter
- retrieval Recall/nDCG trend
- rubric version 전후 비교

평균값 하나로 모델을 순위화하지 않고 sample 수와 confidence interval을 같이 표시한다.

### 17.4 실시간 상태

run 상태는 SSE로 갱신한다.

- queued
- parsing
- retrieving
- evaluating model 1/3
- calibrating
- draft ready
- stale/conflict
- failed

진행률을 알 수 없으면 가짜 percentage 대신 현재 stage와 elapsed time을 표시한다.

### 17.5 반응형 전략

- desktop 1280px 이상: 3-column review workbench
- tablet: criterion drawer + evidence/main + decision panel
- mobile: queue 확인, comment, approval 요약 중심; 정밀 evidence 비교는 desktop 권장
- 대형 표는 horizontal scroll보다 column priority와 detail drawer를 사용

## 18. LG 기반 Design System

### 18.1 브랜드 적용 경계

공개 LG Brand Identity의 색상 체계를 초기 token에 사용한다. 공식 로고, LG 전용 서체, gradient asset, 상표 사용은 권한을 확인하기 전 제품에 포함하지 않는다. 따라서 MVP는 **LG-based internal product UI**이며 공식 LG 제품 인증을 의미하지 않는다.

### 18.2 색상 token

LG 공식 색:

| Token | 값 | 사용 |
|---|---|---|
| lg-active-red | #FD312E | 강조, progress accent, illustration |
| lg-heritage-red | #A50034 | primary action, active navigation |
| lg-warm-grey | #F0ECE4 | page/subtle surface |
| lg-white | #FFFFFF | primary surface |
| lg-black | #000000 | 핵심 text |

제품용 보조 token은 접근성 검증 후 확정한다.

~~~css
:root {
  --brand-active: #fd312e;
  --brand-primary: #a50034;
  --surface-page: #f7f5f1;
  --surface-subtle: #f0ece4;
  --surface-card: #ffffff;
  --text-primary: #161616;
  --text-secondary: #5b5755;
  --border-default: #d8d3cc;
  --status-success: #18704a;
  --status-warning: #9a5200;
  --status-info: #2457a7;
  --status-danger: #a50034;
}
~~~

Active Red는 밝기 때문에 작은 흰색 글자 배경으로 쓰지 않는다. primary button은 Heritage Red + white를 우선하고 실제 contrast를 자동 검사한다. 상태는 색만으로 표현하지 않고 icon, label, pattern을 함께 사용한다.

### 18.3 Typography

- 공식 LG 서체 사용권이 확인되면 brand typography adapter로 교체한다.
- 그 전 한국어 UI는 Pretendard 또는 system sans-serif를 사용한다.
- 숫자·ID·model name은 tabular numerals를 지원하는 mono/system font를 보조로 사용한다.
- 기본 body 14-16px, 최소 interactive label 14px
- 긴 평가문은 70-85자 너비와 1.55 이상 line-height

### 18.4 Layout와 shape

- 4px base spacing, 주요 간격 8/12/16/24/32
- card radius 8-12px, pill은 status/tag에만 제한
- data density는 compact/comfortable 두 모드
- page 최대폭을 임의로 좁히지 않고 evidence 비교 공간을 우선
- shadow보다 border와 surface hierarchy를 사용
- brand gradient는 hero/empty state에 제한하고 review surface에는 쓰지 않는다

### 18.5 Component inventory

- AppShell, GlobalNav, ProjectSwitcher
- StageStepper, GateCard, BlockerBanner
- ProjectTable, ProjectCard
- CriterionNav, CriterionStatus
- EvidenceCitation, EvidenceViewer, SlidePreview
- SimilarCaseCard, DifferenceTable
- ModelVoteMatrix, DisagreementBadge
- KPIComparison, KPITrend
- ReviewDecisionPanel, RequestEvidenceDialog
- RevisionBadge, StaleResultBanner
- AuditTimeline, RunProgress
- BatchActionBar, Empty/Error/Permission states

각 component는 loading, empty, partial, stale, permission denied, error 상태를 문서화한다.

### 18.6 접근성

- WCAG 2.2 AA를 목표로 한다.
- keyboard로 모든 review action 가능
- focus ring을 Active Red만으로 표현하지 않고 두께와 offset 확보
- chart에 table/text alternative 제공
- screen reader용 criterion 상태와 evidence locator
- color vision deficiency를 고려한 palette와 shape
- animation은 prefers-reduced-motion 준수
- decision dialog는 결과와 영향, 대상 revision을 읽어 준다

## 19. Frontend 선택 전 논리 구조

~~~text
apps/web/
  src/
    routes/
      portfolio/
      projects/
      calibration/
      admin/
  components/
    axcalib/
    evidence/
    review/
    charts/
  design-system/
    tokens.css
    primitives/
    patterns/
  lib/
    api-client/
    auth/
    query/
    events/
~~~

전략:

- framework 선택은 Open이며 React + Vite + React Router Data Mode를 현재 권장안으로 둔다.
- Next.js, SvelteKit, Nuxt를 대안으로 유지하고 사용자 선택 전 scaffold하지 않는다.
- TypeScript strict와 framework-neutral design token/component contract를 사용한다.
- OpenAPI-generated client를 API boundary로 사용
- TanStack Query로 server state, URL로 filter state
- form은 dossier command schema에서 생성하되 중요한 review form은 명시적 UI
- Tailwind는 token consumer로만 사용하고 임의 색상값을 component에 쓰지 않는다.
- Radix primitives를 접근성 기반으로 사용하되 AXCalib component API로 감싼다.
- ECharts configuration을 chart component에 캡슐화한다.
- Storybook 또는 동등한 component catalog로 상태를 검증한다.

AI chat panel이 추가되더라도 dossier/evidence source를 명시하고, chat 응답이 review decision을 직접 변경하지 못하게 한다.

## 20. 보안과 위협 경계

주요 trust boundary:

- user browser ↔ API
- API ↔ worker
- worker ↔ model endpoint
- parser ↔ untrusted document
- service ↔ Qdrant/PostgreSQL/MinIO
- tenant/organization 간 데이터

필수 통제:

- OIDC + scoped RBAC/ABAC
- TLS, at-rest encryption, secret manager
- signed artifact URL과 짧은 만료
- malware/type/size 검사
- prompt injection isolation
- outbound network allowlist
- raw prompt/output 접근 로그
- audit event tamper detection
- retention/deletion workflow
- model endpoint별 허용 access classification
- dossier export 시 개인정보 redaction

모델에게 제공한 evidence에는 untrusted_content 경계를 명시한다. 문서 속 지시문을 system instruction으로 승격하지 않으며, 모델 tool은 allowlist만 노출한다.

## 21. Observability와 Audit

모든 실행은 run_id와 trace_id를 가진다.

### Run manifest

- project_id, dossier revision/hash, snapshot_id
- stage, workflow version
- rubric/criterion version
- parser/chunker version
- corpus snapshot
- embedding/reranker model
- evaluator model/profile/serving version
- prompt template hash
- generation parameters
- start/end, latency, token/compute/cost
- retry/error/cancellation
- output schema version/hash

### 운영 지표

- queue depth와 job age
- parser failure by file type
- model latency/error by profile
- vector query latency/empty rate
- dossier conflict/stale rate
- reviewer queue and cycle time
- criterion disagreement
- evidence missing rate
- batch retry/terminal failure

원문 전체와 chain-of-thought는 observability payload에 넣지 않는다.

## 22. Calibration 설계

Calibration은 세 단계로 발전시킨다.

### C1 기술적 안정성

- 같은 fixture 반복 결과
- schema failure와 missing evidence
- parser/retrieval 회귀

### C2 평가자·모델 일치도

- Cohen/Fleiss kappa 또는 적합한 agreement
- ordinal score의 weighted kappa
- 연속 점수의 ICC/MAE
- criterion별 confusion matrix

### C3 확률·경계 보정

- confidence bin의 empirical accuracy
- Brier score/ECE
- Level threshold 주변 오류
- subgroup와 rubric version drift

모델 수가 늘어도 calibration dataset이 없으면 신뢰도가 자동으로 높아졌다고 간주하지 않는다.

## 23. 초기 ADR Backlog

P1에서 다음 ADR을 만든다.

1. ADR-001 Dossier YAML과 immutable snapshot
2. ADR-002 UUID4와 display ID
3. ADR-003 Core port/adapter boundary
4. ADR-004 Qdrant default와 vector abstraction
5. ADR-005 OpenAI-compatible model gateway
6. ADR-006 Deep Agents optional integration
7. ADR-007 SQLite dev / PostgreSQL pilot
8. ADR-008 Docling + slide VLM dual pipeline
9. ADR-009 Async/batch execution and queue adapter
10. ADR-010 Frontend selection and LG token governance (Open)
11. ADR-011 Mandatory HITL approval notification (Accepted, 문서 생성)
12. ADR-012 Stage retrieval and similarity portion (Accepted, 문서 생성)
13. ADR-013 Composable local pipelines and total workflow (Accepted, 문서 생성)

## 24. 검증 계획

설계 검증 순서:

1. two-gate state transition, mandatory notification, mentor guard smoke
2. PipelineContext/Result/Registry와 import boundary contract
3. workflow blueprint/module board/SVG drift와 link validation
4. dossier.freeze local pipeline과 working script parity test
5. dossier schema와 state transition property test
6. synthetic PPTX 3종의 Docling/slide extraction spike
7. mock model structured output contract
8. Qwen3.5 endpoint capability probe
9. 20 synthetic cases의 retrieval baseline
10. 2-model panel의 disagreement report
11. total workflow wait/resume/idempotency scenario
12. CLI/API interface parity와 revision conflict test
13. selected Web App prototype usability review
14. 50 paired de-identified pilot

각 단계가 실패해도 다음 기술을 무조건 추가하지 않는다. 실패 원인이 data, rubric, parser, model, workflow, UX 중 어디에 있는지 분리한 뒤 Narrow/Change/Stop을 결정한다.

## 25. 공식 참고자료

- [LG 공식 Color System](https://www.lg.com/global/our-identity/color/)
- [LG Brand Identity 소개](https://www.lg.com/global/newsroom/news/corporate/lg-smiles-back-to-the-world-with-its-new-brand-identity/)
- [Qwen3.5 모델 문서](https://huggingface.co/docs/transformers/model_doc/qwen3_5)
- [Qwen3.5-9B 공식 모델 카드](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Qwen3 Embedding 공식 모델](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [Qwen3 Reranker 공식 모델](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/)
- [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)
- [Deep Agents model configuration](https://docs.langchain.com/oss/python/deepagents/models)
- [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/)
- [Docling DocumentConverter](https://docling-project.github.io/docling/reference/document_converter/)
- [Qdrant filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qdrant hybrid search](https://qdrant.tech/documentation/search/text-search/hybrid-search/)
- [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)
