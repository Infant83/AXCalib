---
document_type: project_work_specification
project_title: AXCalib
expanded_name: AX Certification Agent Library
project_code: AXCALIB
workspace: C:/Users/angpa/myProjects/Daily_Work/AXCalib
created_at: 2026-07-12
updated_at: 2026-07-22
timezone: Asia/Seoul
status: g3_intelligence_reference_baseline_verified
baseline: v0.3
harness_status: executable_offline_harness; g3_reference_verified; t1_partial
git_status: repository_initialized; main_tracks_origin_main
openproject_status: not_registered
---

# AXCalib 작업명세서

## 1. 문서 목적

이 문서는 AXCalib의 제품·기술·데이터·검증 범위를 정의하고 이후 구현의 기준선으로 사용한다.

AXCalib의 개념과 명명 철학은 AXCalib_Concept_Overview.md, 구현 Target과 단계별 수용기준은 GOAL.md, architecture와 Web App design은 DESIGN.md, Agent 작업규칙은 AGENTS.md를 따른다.

이 문서에 없는 요구는 자동으로 포함되지 않는다. 새 요구는 영향분석과 명시적 변경결정 뒤 baseline에 반영한다.

## 2. 제품 정의

AXCalib는 과제 증거를 구조화하고 평가 편차를 보정하여, 권한 있는 사람이 추적 가능한
근거로 AX 인증 결정을 내리도록 돕는 **AX Certification Agent Library**다.

제품의 기억 문장은 다음과 같다.

> **근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다.**

Excalibur의 “아무나 뽑을 수 없는 칼” 이미지는 제품 철학을 설명하는 기억 장치다. 공식 어원,
브랜드명 변경 또는 Agent가 자격을 자동 부여하는 알고리즘을 뜻하지 않는다. Agent는 근거와
제안 리포트를 만들고, 관리자·인증책임자 등 승인된 사람만 최종 상태를 확정한다.

첫 번째 구체 사용 사례는 AX 인증 과제의 전 생명주기다.

~~~text
등록심의
→ 관리자 HITL 승인·반려
→ 선택적 멘토 배정과 과제 수행
→ 진행·멘토링·산출물·KPI 증거 누적
→ 완료 제출 승인·등록
→ 완료평가와 관리자 HITL
→ 선택적 AX Level/인증 결정
~~~

초기 구현은 Python Library와 CLI로 시작하고, API, async/batch worker, on-prem Web App으로 확장한다.

## 3. 배경과 문제정의

평가 대상이 증가하면 사람이 PPTX와 원시트, 수행기록, KPI, 멘토 의견을 찾아 읽고 기준 및 과거 사례와 비교하는 절차가 병목이 된다.

핵심 문제:

- 등록심의와 완료평가 자료가 서로 다른 파일과 시스템에 흩어져 있다.
- 등록 당시 약속과 최종 수행결과를 일관되게 연결하기 어렵다.
- 제출 형식과 슬라이드 순서가 일정하지 않다.
- 평가 기준, checklist, 과거 사례, 질의응답, 시연결과가 분산돼 있다.
- 평가자·모델별 편차와 Level 경계 오류를 통제하기 어렵다.
- LLM이 만든 문서를 LLM이 평가할 때 문서 최적화 game이 생길 수 있다.
- 어떤 revision, 기준, 모델, corpus, 증거로 판단했는지 재현해야 한다.
- 사내 원문과 개인정보를 승인되지 않은 외부 모델로 보낼 수 없다.

AXCalib는 단일 자동점수 대신 **근거, 불확실성, 유사사례, 모델 편차, 사람의 최종결정**을 함께 기록한다.

## 4. 제품 목표와 비목표

### 4.1 1차 목표

- 과제마다 고유 UUID와 단일 canonical dossier 발급
- 등록심의·수행·완료평가를 명시적 state machine으로 연결
- 평가 요청 시 대상 revision을 immutable snapshot으로 고정
- PPTX 등 evidence를 구조화하고 source locator 생성
- versioned rubric/checklist 적용
- 과거 사례를 embedding/index하고 유사점·차이점 검색
- criterion별 근거 포함 평가초안 생성
- Qwen3.5 기반 on-prem model과 다른 model을 같은 gateway로 실행
- 다중 모델 편차와 반복 안정성 측정
- 사람의 수정·수용·반려·추가자료 요청 기록
- 두 Gate의 관리자 승인요청 알림과 delivery/outbox 상태 기록
- 멘토가 배정된 경우 완료 제출 전 mentor 승인 강제
- stage별 retrieval adapter와 similarity contribution 설정
- offline synthetic evaluation과 비식별 pilot 지표 측정
- 기본 한 함수에서 시작하고 expert profile로 확장하는 점진적 Library UX
- TOML profile과 allowlist된 OpenAPI JSON parameter를 통한 통제 가능한 구성
- 제품 브리프, 5분 시작, 권한 구조도와 웹툰형 튜토리얼 제공

### 4.2 비목표

- LLM의 단독 최종 합격·불합격·인증
- 모든 산업·직무에 통용되는 AX Level 표준의 즉시 확정
- 초기 단계의 전사 운영시스템 직접 변경
- 모든 PPTX, image, video, 시연의 완전 자동평가
- 승인 없는 실제 사내 원문·개인정보 외부전송
- 최초 MVP에서 전사 SSO, HA, DR, 운영 SLA
- score 하나로 모든 평가를 환원
- Deep Agents, Qdrant, 특정 LLM에 domain model 종속

## 5. 사용자와 책임

| 사용자 | 필요 |
|---|---|
| 제출자/과제 Owner | dossier 작성, 증거 누적, 보완요청 이해 |
| Mentor | 멘토링 내용, follow-up, 수행 evidence 기록 |
| 평가자 | 기준·원문·유사사례·모델 편차를 비교하고 판단 |
| 관리자 | Agent 제안을 HITL 검토하고 등록·완료 최종 상태 확정 |
| 인증 책임자 | 완료평가와 별도로 Level/인증정책 적용 |
| 운영담당자 | 과제 상태, queue, blocker, batch, 비용 추적 |
| 정책·감사 담당 | 기준·revision·모델·근거·수정이력 재현 |
| 개발·운영팀 | 장애, 성능, 비용, 보안, data lifecycle 관리 |

모델과 Agent는 책임자가 아니다. 사람의 reviewer/certification decision을 별도 object로 기록한다.

## 6. Domain Lifecycle

### 6.1 주요 단계

| Stage | 핵심 상태 |
|---|---|
| Draft | draft, registration_ready |
| Registration | registration_under_review, registration_hitl_pending, registration_needs_changes, registration_rejected, registration_approved |
| Execution | in_progress, execution_paused |
| Completion | completion_ready, completion_approval_pending, completion_registered, completion_under_review, completion_hitl_pending, completion_needs_changes, completion_not_accepted, completion_accepted |
| Certification | certification_review, certification_on_hold, certified |
| Terminal | withdrawn, cancelled |

### 6.2 핵심 규칙

- registration_approved 전에는 in_progress로 전이할 수 없다.
- Agent의 등록·완료 recommendation은 final decision이 아니며 두 Gate 모두 관리자 HITL이 필수다.
- `*_hitl_pending` 진입 전 관리자 승인요청 notification event가 기록 또는 전달되어야 한다.
- 멘토 배정은 선택이지만 배정된 경우 completion_registered 전 mentor 승인이 필요하다.
- completion 평가에는 approved registration baseline을 반드시 포함한다.
- 등록 이후 목표·범위·KPI 변경은 change request와 승인기록으로 남긴다.
- 모델은 approved, accepted, certified 상태를 직접 확정할 수 없다.
- 모든 mutating command는 expected_revision을 요구한다.
- 허용 전이는 한 state machine에서 관리한다.

상세 전이는 DESIGN.md를 따른다.

## 7. Canonical Dossier 명세

### 7.1 단일 파일 원칙

사용자가 관리하는 과제 기준 파일은 project_id별 AXC-{project_id}.axc.yaml 하나다.

포함:

- 과제 정체성과 상태
- 등록 proposal, rubric, 평가 요약, 사람 decision
- 수행 진행내용, mentor note, 산출물, risk/change, KPI 관측
- 완료 submission report, rubric, 평가결과 report, 사람 decision
- review request와 notification/outbox reference
- 선택적 Level/인증 결과
- artifact, snapshot, run, audit reference

미포함:

- PPTX/PDF/image/code/log binary 본문
- raw chain-of-thought
- API key와 secret
- 허용되지 않은 개인정보 원문

대용량 원문과 full report는 content-addressed artifact로 저장하고 dossier에서 reference한다.

### 7.2 Revision과 snapshot

- project_id는 UUID4이며 불변이다.
- mutation 성공마다 revision을 1 증가시킨다.
- dossier는 canonical representation의 SHA-256 content_hash를 가진다.
- 평가 요청은 revision, content_hash, rubric, artifact hash를 snapshot으로 고정한다.
- 결과는 base snapshot과 연결한다.
- 평가 중 dossier가 바뀌면 stale result로 두고 자동 merge하지 않는다.
- 파일 갱신은 full validation 뒤 atomic replace한다.

### 7.3 최소 top-level field

~~~text
schema_version
project_id
display_id
revision
updated_at
identity
lifecycle
registration
execution
completion
certification
artifact_refs
audit
extensions
~~~

정식 schema는 Pydantic model에서 JSON Schema Draft 2020-12로 export한다.

## 8. 기능 요구사항

| ID | 기능 | 요구사항 | 우선순위 |
|---|---|---|---|
| FR-001 | Project ID | 신규 과제에 UUID4 project_id와 display_id 발급 | Must |
| FR-002 | Dossier | 한 .axc.yaml에서 전 생명주기 관리 | Must |
| FR-003 | Schema | versioned Pydantic/JSON Schema validation과 migration | Must |
| FR-004 | State | 허용 전이, 역할, Gate 검증 | Must |
| FR-005 | Snapshot | 평가 대상 revision과 artifact/rubric hash 고정 | Must |
| FR-006 | Registration | 등록심의 제출, 평가초안, 사람 decision | Must |
| FR-007 | Execution | progress, mentor note, deliverable, KPI, change 누적 | Must |
| FR-008 | Completion | 등록 baseline 대비 완료평가 | Must |
| FR-009 | Evidence ingest | PPTX/문서에서 구조와 locator 추출 | Must |
| FR-010 | Visual analysis | slide rendering과 multimodal 분석 | Should |
| FR-011 | Rubric registry | 기준/checklist version과 효력일 관리 | Must |
| FR-012 | Deterministic checks | 필수필드, 수치, 정책조건 검사 | Must |
| FR-013 | Model evaluation | criterion별 structured assessment | Must |
| FR-014 | Similar cases | 과거 사례 검색, 유사점·차이·한계 기록 | Must |
| FR-015 | Case embedding | parse/chunk/embed/index/reindex routine | Must |
| FR-016 | Model gateway | BASE_URL/API_KEY/model profile 주입 | Must |
| FR-017 | Multi-model | 독립 panel, disagreement, adjudication | Should |
| FR-018 | Human review | 수용·수정·반려·추가자료 요청 | Must |
| FR-019 | Audit | 입력·기준·model·prompt·corpus·출력·수정 연결 | Must |
| FR-020 | Sync/async | 같은 의미의 sync/async Library API | Must |
| FR-021 | Batch | idempotency, checkpoint, resume, 부분 실패 | Should |
| FR-022 | Report | dossier 요약 + Markdown/JSON, 향후 PDF | Must |
| FR-023 | CLI/API | Library와 같은 service를 호출 | Should |
| FR-024 | Web process | Gate, checklist, evidence, blocker visualization | Later |
| FR-025 | Calibration | model/rubric/retrieval 편차와 경계 오류 측정 | Should |
| FR-026 | Certification | 완료평가와 분리된 policy/Level decision | Later |
| FR-027 | HITL Gate | 등록·완료 결과를 관리자 승인 전 final 상태로 전이하지 않음 | Must |
| FR-028 | Approval notification | 두 HITL Gate마다 GitLab MR/email/recording adapter event 발생 | Must |
| FR-029 | Mentor assignment | 멘토는 선택, 배정 시 완료 제출 승인 필수 | Must |
| FR-030 | Completion submission | 수행자 제출 리포트와 Agent 완료평가 결과 리포트 분리 | Must |
| FR-031 | Retrieval policy | stage별 adapter/corpus와 similarity portion 설정 | Must |
| FR-032 | Checklist as instruction | 등록·완료·HITL Markdown checklist를 versioned 작업기준으로 사용 | Must |
| FR-033 | Element modules | dossier/ingest/retrieval/evaluation 등 capability를 독립 library module과 port로 구현 | Must |
| FR-034 | Local pipelines | 하나의 업무 목적을 typed input/output/status로 완결하는 재사용 pipeline 제공 | Must |
| FR-035 | Workflow composition | versioned pipeline, branch, human wait/resume, checkpoint를 연결해 전체 workflow 구성 | Must |
| FR-036 | Interface parity | working script, CLI, API, worker가 같은 library pipeline/workflow를 호출 | Must |
| FR-037 | Visual workflow blueprint | 계층, 두 Gate, sequence, 실패·재개, module dependency 구조도를 versioned 문서로 유지 | Must |
| FR-038 | Module delivery control | module별 상태, 입력·출력, 선행조건, test와 Exit Evidence를 control board로 추적 | Must |
| FR-039 | Minimal facade | `AXCalib.evaluate/aevaluate`의 작은 public entrypoint와 동일 의미 제공 | Must |
| FR-040 | Progressive config | 안전 기본 TOML과 expert profile을 분리하고 unknown/protected key 거부 | Must |
| FR-041 | Typed OpenAPI control | OpenAPI 3.1/JSON Schema 2020-12의 allowlist JSON options와 idempotency 계약 | Must |
| FR-042 | Learning system | 제품 브리프, quickstart, 정확한 diagram, 웹툰/강의 storyboard를 함께 유지 | Should |
| FR-043 | Development readiness | owner sign-off와 synthetic/live NO-GO 범위를 감사 가능한 문서로 Gate화 | Must |
| FR-044 | Education program | 과정 기획자가 versioned level/milestone/prerequisite와 allowlisted pipeline을 정의 | Must |
| FR-045 | Enrollment goals | 가입 시 exact program version/hash를 고정하고 학습자별 단계 목표와 진행상태 생성 | Must |
| FR-046 | Project milestone | 같은 program/version/enrollment/milestone/learner context의 project dossier만 연결하고 저장된 상태로 조건 평가 | Must |
| FR-047 | Typed conditions | manual confirmation, score threshold, project status와 명시적 completion rule 제공 | Must |
| FR-048 | Program completion HITL | 필수 milestone 충족 뒤 notification과 관리자 승인 전 과정 완료를 확정하지 않음 | Must |
| FR-049 | Program rollout | 새 version은 신규 가입에 pin하고 기존 가입의 자동 migration을 금지; retire/migration은 별도 정책 | Should |
| FR-050 | Deterministic slide render | 지원하는 PPTX fixture는 source/image SHA-256을 가진 slide별 manifest로 렌더하고 지원 밖 합성 slide는 fail-closed | Must |
| FR-051 | Evidence quality baseline | 검토 locator gold set과 field coverage, locator recall, criterion traceability, unsupported-claim 지표를 hash-bound fixture로 회귀 | Must |
| FR-052 | Structured-output compatibility | `json_object`에 literal JSON과 schema contract를 포함하고 wrapped upstream error를 safe identifier로 진단; model-independent multimodal proxy/deployment probe 제공 | Must |
| FR-053 | Project transaction recovery | project command의 dossier/audit 변경을 revision/hash-bound append-only journal로 복구하고 HITL report/recorded outbox 불일치와 stale revision을 fail-closed | Must |
| FR-054 | Local execution and education recovery | PipelineContext/run checkpoint/cancel/result hash, JSONL batch partial status, education enrollment/audit reconcile와 non-destructive stale artifact maintenance를 같은 allowlisted Library registry로 제공 | Must |

## 9. 등록심의와 완료평가 공통 Pipeline

~~~text
preflight
→ snapshot freeze
→ parse/normalize
→ rubric/checklist load
→ historical case retrieval
→ deterministic checks
→ model evaluation
→ multi-model calibration
→ evidence-backed draft report
→ administrator approval notification
→ HITL hallucination/bias/evidence review
→ administrator final decision
→ dossier/audit update
~~~

완료평가는 위 흐름에 approved registration baseline과 approved change diff를 추가한다.

### 9.1 Composable Pipeline 구현계약

공통 Pipeline을 하나의 거대한 함수로 만들지 않는다. 구현은 다음 방향으로 분리한다.

~~~text
domain schema와 port
→ dossier/ingest/retrieval/evaluation 등 요소 모듈
→ 하나의 업무 목적을 완결하는 국소 pipeline class
→ 실제로 실행되는 synthetic Python script
→ versioned pipeline을 연결한 total workflow
→ CLI / API / worker / Web App
~~~

국소 pipeline은 transport framework 없이 import할 수 있어야 하며 typed request,
`PipelineContext`, typed result, 명시적 status, pipeline id/version을 가진다. sync/async 호출은
같은 input/output/error 의미를 유지한다.

전체 workflow는 조건 분기, 관리자/mentor 대기, checkpoint와 재개를 담당하지만 domain state
machine을 대체하지 않는다. mandatory HITL, notification, mentor guard, revision/snapshot 같은
불변조건은 workflow recipe나 설정으로 끌 수 없다.

working script는 argument와 파일 입출력, runtime profile 생성, 결과 직렬화만 담당한다. CLI,
API, worker는 script를 실행하지 않고 같은 library pipeline/workflow를 직접 호출한다. Web App은
API 상태와 allowed command를 표시하며 업무 로직을 재구현하지 않는다.

초기에는 명시적 Python composition과 allowlisted registry를 사용한다. 임의 class import path,
expression 또는 arbitrary YAML graph 실행은 MVP 범위에서 제외한다. 상세 계약과 초기 pipeline
catalog는 `docs/architecture/composable-pipeline-plan.md`, 결정 근거는 ADR-013을 따른다.

구현 순서와 상태는 `docs/architecture/module-delivery-plan.md`의 M00~M13 control board로
추적한다. 구조·상태·분기 변경은 `docs/architecture/workflow-blueprint.md`의 Mermaid 구조도와
SVG 인포그래픽을 같은 change set에서 갱신한다. 다이어그램과 구현이 충돌하면 완료상태를
올리지 않고 code/state/document 중 기준을 명시적으로 정렬한다.

### 9.2 최소 인터페이스와 설정 경계

초기 public facade의 offline slice는 다음 모양으로 구현됐다.

~~~python
from axcalib import AXCalib

client = AXCalib.from_toml("config/axcalib.toml", workspace="output/review")
project = client.create_project("proposal.pptx", title="검토할 과제")
client.submit_registration(project.project_id)
draft = client.evaluate(project.project_id, stage="registration")
# async boundary에서는 위 evaluate 대신 await client.aevaluate(...)를 사용한다.
~~~

전문 on-prem profile의 model, retrieval, storage, notification adapter 조립은 Target이다. 현재
`from_toml`은 offline filesystem/mock/recording/lexical profile만 실행한다.

설정 우선순위는 `코드 소유 불변조건 > 안전 기본값 > TOML profile > 환경변수 > allowlist된
request options > policy guard`다. 관리자 HITL, 승인요청 알림, 사람 최종결정, revision/stale
guard와 mentor guard는 설정 가능한 값이 아니며 TOML/OpenAPI 양쪽에서 보호 필드를 제공하지
않는다. 적용된 설정에는 secret을 제외한 effective-config hash와 source map을 남긴다.

전체 제품 API target은 `docs/api/openapi.v1alpha1.json`, 실제 구현된 local runtime surface는
FastAPI-generated `docs/api/openapi.runtime.v1alpha1.json`을 기준으로 한다. OpenAPI 3.1.0과 JSON
Schema Draft 2020-12를 사용하며 unknown request field를 거부한다. Library registry와 HTTP
delivery grant는 분리하고 generic API가 request actor/admin decision을 신뢰하지 않는다. Python
3.12 표준 parser 호환을 위해 TOML 작성 문법은 1.0 범위로 제한한다. 자세한 결정은 ADR-014와
ADR-022다.

### 9.3 교육 프로그램 Composition

과정 progression은 프로젝트 dossier 위의 별도 aggregate로 구현한다.

~~~text
EducationProgram@version (immutable blueprint)
→ learner enroll
→ EducationEnrollment (generated milestone goals)
→ manual / score / project pipelines
→ project completion_accepted를 milestone evidence로 roll-up
→ all required milestones complete
→ program completion notification
→ administrator HITL
→ enrollment completed 또는 selected milestone 재개방
~~~

현재 AXCalib가 직접 등록심의·완료평가하는 대상은 제출 프로젝트다. 과정 전체 `completed`는
프로젝트 심의 결과와 기타 이수조건을 모은 상위 사람 결정이며 credential 발급과는 구분한다.

program은 exact version과 canonical SHA-256으로 발행하고 enrollment에 pin한다. 과정 기획자는
level, milestone, prerequisite, required/optional, `all_required`/`minimum_points`를 구성할 수 있다.
조건과 pipeline은 code-owned allowlist만 사용하며 임의 Python import, expression 또는 dynamic
graph 실행은 허용하지 않는다. project 연결은 program/version/enrollment/milestone/learner
context가 모두 일치해야 하며 project status를 request JSON으로 직접 주장할 수 없다.

상세 계약은 `docs/workflows/education_project_lifecycle.md`와 ADR-017을 따른다.

## 10. 리뷰 리포트 최소 형식

criterion별:

| 필드 | 설명 |
|---|---|
| criterion_id/version | 적용한 기준 |
| assessment | met, partially_met, not_met, insufficient_evidence, not_applicable |
| observation | 제출자료에서 확인한 사실 |
| evidence_refs | page/slide/object/field locator |
| deterministic_checks | 규칙 결과 |
| model_findings | model별 독립 결과 |
| similar_case_refs | 사례, score, corpus snapshot |
| commonalities/differences | 사례 비교 |
| retrieval_status/adapter | unavailable, empty, completed 및 사용 구현체 |
| similarity_portion | historical-consistency의 설정 비중과 계산근거 |
| evidence_adequacy | coverage와 reliability |
| disagreement | model/규칙/사례 충돌 |
| risk_flags | 오판·누락·정책 위험 |
| follow_up_questions | 평가자 확인 질문 |
| reviewer_action | 수용·수정·반려·추가자료 |
| agent_recommendation | Agent의 통과·미통과·자료부족 제안 |
| administrator_decision | 관리자 최종결정, actor, 시각, 사유 |
| notification_ref | 승인요청 delivery 또는 outbox 기록 |
| audit_ref | run manifest |

근거가 없으면 insufficient_evidence로 처리한다. confidence는 evidence coverage, reliability, model agreement, rule consistency를 분리해 표시한다.

## 11. 과거 사례와 Vector DB

### 11.1 Ingestion

~~~text
원본 등록
→ 접근등급/비식별
→ parse/normalize
→ registration/completion semantic section
→ chunk + provenance
→ dense/sparse embedding
→ vector upsert
→ corpus manifest
→ retrieval evaluation
~~~

### 11.2 기본 선택

- embedding 후보: Qwen3-Embedding-0.6B
- reranker 후보: Qwen3-Reranker-0.6B
- vector store: Qdrant adapter
- test: in-memory fake
- 검색: metadata filter + lexical/dense hybrid + rerank + case aggregation
- collection/corpus는 stage, rubric, access classification을 구분
- embedding model이 없는 offline baseline은 NullRetriever와 LexicalRetriever를 사용

### 11.3 필수 기록

- source hash/revision
- parser/chunker/embedding version
- corpus_snapshot_id
- case/stage/criterion/rubric metadata
- access classification
- query와 retrieval/rerank version

과거 outcome을 새 과제의 정답으로 복사하지 않는다. 유사사례는 일관성 점검과 follow-up 질문의 근거다.

### 11.4 Similarity contribution policy

- registration과 completion은 adapter, corpus, portion을 독립 설정한다.
- raw cosine/dense score를 직접 합격점수로 사용하지 않는다.
- commonality, difference, limitation을 포함한 historical-consistency 신호에만 portion을 적용한다.
- portion 범위는 `0.0..1.0`, offline 기본값은 `0.0`이다.
- `0.25` 초과는 warning과 Evaluation Owner의 명시적 승인을 요구하는 운영 guard다.
- portion이 양수인데 retrieval이 unavailable이면 가중치를 재분배하지 않고 평가를 차단하거나
  insufficient evidence로 기록한다.

## 12. Model과 Agent

### 12.1 Model profile

~~~text
provider
model
base_url
api_key_env
capabilities
timeout
max_concurrency
generation_profile
~~~

기본 logical profile은 Qwen3.5 multimodal이다. 사용자 계획상 첫 on-prem deployment 검증 ID는
`Qwen3.5-397B-A17B`다. hardware, endpoint identity와 quality evaluation 전 운영 기본으로 확정하지
않으며 `qwen3.5-plus` 같은 provider alias를 exact checkpoint로 간주하지 않는다.

### 12.2 OpenAI-compatible

- base_url은 /v1까지 포함하는 API base로 표준화
- HTTP client와 curl로 base_url + /chat/completions 최소계약 확인
- startup capability probe
- endpoint별 vision, structured output, tool calling, streaming 차이를 기록
- API key는 env/secret manager로만 주입
- on-prem 실행은 canonical `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`을 기준으로 한다.
- capability report는 provider proxy와 exact deployment scope를 구분한다.
- structured-output dialect와 output token limit는 명시하고 조용한 model/dialect fallback을 금지한다.
- `json_object` dialect는 literal JSON과 canonical schema contract를 prompt에 포함하고 최종 text를
  Pydantic으로 다시 검증한다.
- 공통 multimodal probe의 기본 `provider_proxy` scope는 exact identifier가 같아도 deployment-ready로
  승격하지 않는다.
- raw model output와 hidden reasoning은 보존하지 않는다.
- vLLM 또는 승인된 compatible server 사용 가능

### 12.3 실행모드

- single: primary model
- panel: 2개 이상 model 독립평가
- adjudicated: disagreement가 큰 항목 재검토
- repeatability: 동일 model 반복편차 측정

model들은 첫 pass에서 서로의 결과를 보지 않는다. 평균점수보다 criterion별 분포와 evidence 차이를 먼저 보고한다.

### 12.4 Deep Agents

deepagents integration은 optional extra다. read-only evidence 탐색, 분석계획, criterion subtask에 활용할 수 있다. dossier 직접 write, final transition, rubric 변경권한을 주지 않는다.

### 12.5 관리자 HITL과 Notification

- Agent report와 administrator decision은 별도 object다.
- `docs/rubrics/hitl_review_checklist.md`로 unsupported claim, hallucination, bias,
  disagreement, RAG leakage와 score 계산을 검토한다.
- review request notification은 `NotificationPort`를 통해 GitLab MR, email 또는 offline
  recording adapter로 처리한다.
- 운영 adapter는 idempotency key, retry, delivery status와 audit reference를 가져야 한다.
- 알림 실패 시 final 상태는 물론 HITL pending 전이도 완료하지 않는다.

## 13. 비정형 문서 분석

PPTX 분석은 네 층으로 구성한다.

1. Docling 구조 추출
2. slide image rendering
3. Qwen3.5 등 VLM visual analysis
4. typed domain evidence와 rubric mapping

현재 `oled_qc_project_outline.pptx`에 대해서는 일반 PowerPoint renderer가 아니라, 단일 uncropped
full-slide embedded PNG 또는 true blank slide만 허용하는 제한형 local adapter를 사용한다. 이
adapter는 16/16 slide의 content hash manifest를 만들고 합성 text/chart/multiple-picture slide는
거부한다. 13개 수동 검토 locator는 source와 sidecar hash에 고정한 gold fixture로 관리하며,
일반 PPTX 시각 의미 이해나 VLM 품질을 주장하지 않는다.

정량:

- slide/page 처리율
- text/table/chart/image 추출수
- object coverage와 parse warning
- KPI value/unit/period/measurement 완전성
- locator 없는 숫자와 상충 숫자
- criterion별 evidence coverage

정성:

- 문제-해결안 연결
- 목표-수행-KPI 인과성
- 주장과 증거 정합성
- 재현성, 위험, 한계
- 등록계획 대비 변화와 결과

문서 design 품질을 과제 성과로 간주하지 않는다.

## 14. Async와 Batch

- sync/async API는 같은 input/output/error contract를 가진다.
- artifact, model panel, dossier item 단위 병렬성을 지원한다.
- capacity limit와 endpoint별 concurrency limit를 둔다.
- retry는 transient error에만 적용한다.
- batch는 JSONL manifest, item_id, idempotency_key, expected_revision을 가진다.
- 상태는 queued/running/succeeded/retryable/terminal/stale/cancelled로 구분한다.
- resume은 성공항목을 중복 실행하지 않는다.
- long job API는 202 + run_id, SSE/poll progress를 사용한다.

## 15. 기술 Architecture

~~~text
Python scripts / CLI / FastAPI / Worker / Web client
                         |
              Versioned Total Workflows
             branch / wait / resume / checkpoint
                         |
                Reusable Local Pipelines
                         |
 Dossier + Rubric + Evidence + Evaluation Domain Modules
        /          |          \
 Parser Ports  Retrieval Ports  Model/Notification Ports
 Docling       Qdrant            OpenAI-compatible / GitLab / email
                         |
             FS/S3 + SQLite/PostgreSQL + Audit
~~~

### 15.1 baseline stack

| 계층 | 선택 |
|---|---|
| Runtime | Python 3.12+ |
| Packaging | uv + hatchling |
| Schema | Pydantic v2, JSON Schema 2020-12 |
| Dossier | YAML 1.2, ruamel.yaml |
| CLI | Typer + Rich |
| API | FastAPI/OpenAPI 3.1 |
| API schema | OpenAPI 3.1.0 + JSON Schema Draft 2020-12, JSON artifact 기준 |
| Async/HTTP | AnyIO + HTTPX |
| Parser | Docling optional extra |
| Embedding | Qwen3 Embedding 후보 |
| Vector | Qdrant |
| Metadata | SQLite dev / PostgreSQL pilot |
| Artifact | filesystem dev / MinIO pilot |
| Model server | vLLM 또는 compatible on-prem |
| Agent | Deep Agents optional |
| Test | pytest + Hypothesis |
| Quality | Ruff + Pyright |
| Observability | structlog + OpenTelemetry |
| Frontend | Open; React + Vite + React Router Data Mode 권장, 사용자 선택 대기 |

exact version은 scaffold 시 spike 후 lockfile에 고정한다.

## 16. Web App 요구사항

Web App은 process와 evidence를 중심으로 한다.

필수 view:

- Portfolio와 registration/completion queue
- Project overview와 5단계 stepper
- registration review workbench
- execution timeline과 KPI
- completion review workbench
- evidence viewer와 source locator
- similar case comparison
- model disagreement/calibration dashboard
- audit timeline
- rubric/model/corpus administration

각 과제는 단계별 checklist, blocker, 담당자, 대상 revision, next action을 보여야 한다.

Frontend는 Python FastAPI와 분리하고 OpenAPI-generated client와 SSE를 사용한다. MVP 후보는
React + Vite + React Router Data Mode이며 Next.js, SvelteKit, Nuxt 대안을 포함한 디자인 선택은
사용자 확정 전까지 Open이다.

LG 기반 design은 Active Red #FD312E, Heritage Red #A50034, Warm Grey #F0ECE4, White, Black을 token으로 사용한다. 공식 logo/font/asset은 권한 확인 전 사용하지 않는다. 상세 UI 원칙은 DESIGN.md를 따른다.

## 17. 비기능 요구사항

| 영역 | 요구사항 |
|---|---|
| 보안 | 최소권한, secret 분리, endpoint allowlist, malware/type 검사 |
| 개인정보 | pseudonymous ID, 최소수집, 보존/삭제, 외부전송 통제 |
| 재현성 | dossier/rubric/model/prompt/corpus/code version 연결 |
| 신뢰성 | atomic write, idempotency, retry, stale/partial failure 표시 |
| 설명가능성 | 결론보다 evidence, 기준, 불확실성 우선 |
| 관찰성 | run, latency, token/compute/cost, error, reviewer 상태 |
| 테스트성 | synthetic fixture, mock model, fixed evaluation set |
| 이식성 | parser/vector/model/storage를 interface로 교체 |
| 조합성 | 요소 모듈과 국소 pipeline을 versioned workflow로 연결하고 interface별 로직 복제를 금지 |
| 접근성 | Web App WCAG 2.2 AA 목표 |
| 성능 | 초기에는 처리량보다 품질·근거·재현성 우선 |
| 확장성 | single item에서 bounded async/batch로 확장 |

## 18. 데이터 명세

### 18.1 필수 metadata

~~~text
project_id
display_id
participant_id_pseudonymized
project_type
organization_ref
review_stage
dossier_revision
dossier_hash
snapshot_id
source_file_id/version/hash
rubric_id/version
criterion_ids
reviewer_decision
access_classification
corpus_snapshot_id
model_profile/run_id
~~~

### 18.2 데이터 원칙

- 초기 개발은 synthetic fixture만 사용한다.
- 실제 자료는 승인, 최소권한, 비식별, 보존정책 후 반입한다.
- 원문, 파생 text, embedding, model output을 모두 data inventory에 넣는다.
- 실패·경계·자료부족 사례를 포함한다.
- tuning, calibration, final evaluation set을 혼합하지 않는다.
- 삭제 시 원문, 파생물, vector, cache, report까지 추적한다.

## 19. Evaluation 계획

### 19.1 지표

| 지표 | 정의 |
|---|---|
| Parser coverage | required field와 object 추출률 |
| Evidence traceability | criterion 결과가 source locator로 재현되는 비율 |
| Unsupported claim | 근거 없이 충족 판단한 비율 |
| Retrieval Recall/nDCG | 유사사례 후보와 순위 품질 |
| Stage leakage | registration에 completion outcome이 부당 노출된 비율 |
| Human agreement | expert와 model/reviewer 결과 일치도 |
| Model disagreement | model별 criterion 분산 |
| Calibration | confidence와 실제 오류의 정렬 |
| Boundary error | 합격선/Level 경계 오판 |
| Review time | 기존 대비 사람 검토시간 |
| Reproducibility | 동일 version/config의 구조적 재생성 |
| Cost/latency | 건당 GPU/API 비용과 처리시간 |

### 19.2 제안 성공기준

제안값은 GOAL.md를 따른다. Product Owner와 평가책임자가 Gate 0에서 승인하기 전에는 실험 목표이며 공식 성공판정 기준이 아니다.

## 20. 역할과 책임경계

| 역할 | 최종 책임 |
|---|---|
| Sponsor | 우선순위, 공수·예산, Go/No-Go |
| Product Owner | 범위, rubric, 수용기준, 업무 검수 |
| Evaluation Owner | 평가정책, 합격선, Level, 위험오판 |
| Delivery Lead | 계획, 상태, 결정·변경·의존성 |
| Tech Lead | architecture, code/model/parser/retrieval 품질 |
| Developer | 합의된 구현·테스트·증빙 |
| Data Owner | sample, 권한, 기준결과, data dictionary |
| Governance | 개인정보·보안·인프라 승인 |
| Operations | 배포·rollback·운영·인수 |
| Reviewer | 개별 평가의 사람 최종결정 |

위험 제기자와 Risk Owner를 자동으로 동일시하지 않는다. 새 요구와 사후 수용기준은 Change Request로 처리한다.

## 21. Gate와 산출물

| Gate | 산출물 | 통과조건 |
|---|---|---|
| G0 Alignment | WORK_SPEC/GOAL/DESIGN, RACI, 성공기준 | Owner와 첫 use case 결정 |
| G1 Harness | package scaffold, prep, state/decision/risk, pre-development audit | 구현 완료, validate/test/eval 통과와 owner sign-off 뒤 WP-01 허용 |
| G2 Domain MVP | dossier, state, snapshot, synthetic flow | offline vertical slice 통과 |
| G3 Intelligence | parser, retrieval, model, report | reference evidence/retrieval/model baseline; 운영 품질은 별도 Gate |
| G4 Interfaces | CLI/API/async/batch | contract/E2E 통과 |
| G5 Web Review | process/review/calibration UI | 핵심 사용자 flow 검증 |
| G6 Pilot | 50 paired sample 결과 | 위험·시간·편차·보안 검토 |
| G7 Go/No-Go | Continue/Narrow/Stop memo | Sponsor 명시적 결정 |
| G8 Integration | 운영 API, SSO, backup, rollback | 별도 승인과 인수 |

## 22. Codex Harness 계약

### 22.1 목표

다음 Agent가 현재 baseline과 Gate를 즉시 파악하고 작은 변경을 구현·검증하며 근거 없는 완료 선언을 하지 못하게 한다.

### 22.2 계획 명령

~~~powershell
.\prep.ps1 status
.\prep.ps1 next
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 eval
~~~

- status와 validate는 read-only다.
- test는 network/GPU/API key 없이 기본 suite를 실행한다.
- live model evaluation은 별도 opt-in이다.
- 완료 선언에는 file, command, test/eval evidence가 필요하다.
- 실제 data, token, secret, output은 Git에 넣지 않는다.

`prep.ps1`과 executable offline harness는 구현되어 있다. eval은 synthetic workflow contract,
제공 PPTX의 deterministic ingest-to-report 회귀와 작은 stage-aware lexical dataset을 검증한다.
live model은 기본 명령에서 제외되며 사용자 승인 하에 비식별 fixture registration smoke 1회를
별도로 수행했다. 이 smoke와 synthetic metric은 실제 model/retrieval 품질 검증이 아니다.

### 22.3 단일 Project Execution Ledger

- `PROJECT_STATE.md`는 현재 P/WP/G, dependency Gantt, Active Slice, 일정 Queue, Exit Evidence,
  검증 결과, 특이사항과 작업 이력을 한곳에서 관리하는 실행 기준정보다.
- 작업 시작 때 범위·선행조건·목표 Gate를 갱신하고, 종료 때 변경 파일·검증·미검증·다음 작업을
  같은 change set에서 기록한다.
- 현재 상태는 갱신하되 작업 이력은 append-only로 유지한다. 정정은 새 history entry로 남긴다.
- Owner·공수·목표일이 승인되기 전에는 dependency-only 일정을 사용하고 calendar 날짜를 약속하지
  않는다.
- 제품 요구·기술설계·결정·위험의 원문은 각각 WORK_SPEC/GOAL/DESIGN/DECISIONS/RISK_REGISTER에
  유지하고, 실행 원장은 그 변경의 진행 영향과 링크를 기록한다.
- 하네스 validation은 원장의 필수 frontmatter, P0~P9, G0~G8, Gantt, Active Slice와 마지막 이력
  일치를 검사한다.

## 23. 기준정보 우선순위

1. 사용자의 최신 명시적 지시
2. 승인된 WORK_SPEC baseline
3. GOAL의 Target/Acceptance Criteria
4. DESIGN의 architecture/UX
5. 승인된 ADR/Change Request
6. AXCalib_Concept_Overview
7. test/evaluation이 보여 주는 실제 동작

## 24. 초기 Risk와 의존성

| ID | 위험·의존성 | 대응/필요결정 |
|---|---|---|
| R-001 | Product/Evaluation Owner 미정 | G0에서 A 지정 |
| R-002 | AX Level/합격선 미정 | policy registry 외부화 |
| R-003 | 실제 평가량·시간 미검증 | baseline 측정 |
| R-004 | data 권한·format 편차 | synthetic 우선, Data Owner |
| R-005 | 단일 파일 충돌 | revision/snapshot/atomic write |
| R-006 | 자동 최종판정 범위확대 | Human decision 분리 |
| R-007 | 과거사례 편향 | outcome-blind retrieval와 evaluation |
| R-008 | 외부 model data 전송 | on-prem 기본, endpoint policy |
| R-009 | Qwen endpoint capability 차이 | capability probe |
| R-010 | PPTX visual 의미 누락 | Docling + render + VLM |
| R-011 | 다중 모델 평균의 false confidence | disagreement 중심 report |
| R-012 | batch 중복·부분실패 | idempotency/checkpoint |
| R-013 | LG brand asset 권한 | public color token만, 승인 Gate |
| R-014 | 운영시스템 조기통합 | G7 이후 별도 승인 |
| R-015 | Agent 오류·편향·hallucination | HITL checklist와 관리자 전용 final transition |
| R-016 | 승인요청 알림 실패 | HITL 전이 fail closed, outbox/retry 계획 |
| R-017 | similarity portion 과대 설정 | 기본 0, 0.25 초과 warning과 owner 승인 |
| R-018 | mentor 승인 우회 | mentor 배정 시 completion submission guard |
| R-019 | 설정 과다로 첫 사용 실패 | minimal facade/default와 expert profile 분리 |
| R-020 | API/TOML로 사람 권한 우회 | protected field 미제공, unknown key 거부, policy guard |
| R-021 | Excalibur 비유를 Agent 자동인증으로 오해 | 사람 최종권한 문구, 정확한 diagram과 tutorial 반복 |
| R-022 | OpenAPI 문서와 구현 drift | artifact-first contract test와 generated client parity |

## 25. Open Questions

1. 첫 실제 AX 과제 유형과 공식 Product/Evaluation Owner는 누구인가?
2. 등록심의·완료평가 rubric 원본과 version owner는 누구인가?
3. AX Level, 필수역량, 합격선, 재평가·인증 유효기간은 무엇인가?
4. 실제 PPTX/원시트 형식과 등록-완료 연결 ID가 있는가?
5. on-prem GPU, vLLM/Qwen endpoint, 허용 model 목록은 무엇인가?
6. 실제 사례의 이용근거, 비식별 수준, 보존기간은 무엇인가?
7. retrieval relevance와 expert gold label을 누가 작성하는가?
8. PostgreSQL, Qdrant, MinIO, queue 운영 Owner는 누구인가?
9. SSO/RBAC와 reviewer/certification 권한은 어떻게 연결하는가?
10. 공식 LG design asset과 font 사용권한이 있는가?
11. 내부 package registry와 공개/내부 license는 무엇인가?
12. 파일럿의 위험한 오판 허용한도와 time-saving target을 승인할 것인가?
13. 운영 승인요청 수단은 GitLab Merge Request, email 또는 둘 다인가?
14. similarity portion의 stage별 기본값과 허용상한은 무엇인가?
15. mentor 미배정 과제의 완료 제출 확인자를 project owner와 관리자 중 누구로 제한할 것인가?
16. pre-development baseline과 WP-01 synthetic/offline slice를 Product Owner가 승인하는가?
17. program publish/retire와 version owner는 누구이며 기존 enrollment migration을 허용하는가?
18. 과정 완료와 공식 credential 발급을 어떤 권한·정책 Gate로 분리할 것인가?
19. 수업 이수·점수·면제·재수강·기한 조건의 신뢰 가능한 source system은 무엇인가?

## 26. 사용자 요구 추적표

| 요구 | 반영 위치 | 상태 |
|---|---|---|
| 1. Library에서 API/CLI/App/Web으로 확장 | FR-020~024, GOAL P1~P8, DESIGN 3/16/17 | Specified |
| 2. 등록심의와 완료평가 이원화 | Domain Lifecycle, FR-006/008, DESIGN 6~9 | Specified |
| 3. 단일 파일의 지속갱신과 완료평가 요청 | Canonical Dossier, revision/snapshot, FR-002/005/007 | Specified |
| 4. checklist evaluation과 과거 유사사례 report | FR-011~014, Report schema, DESIGN 7/9/10 | Specified |
| 5. 기존 명세와 AXCalib naming 철학 | 문서 우선순위, README, Concept 문서 연결 | Specified |
| 6. 과거 과제 embedding과 Vector DB | FR-015, Vector DB section, GOAL WP-04 | Specified |
| 7. on-prem Qwen3.5, BASE_URL/API_KEY, curl, Deep Agents, multi-model | FR-016/017, Model/Agent section, DESIGN 12 | Specified |
| 8. async와 batch | FR-020/021, Async/Batch section, GOAL WP-06 | Specified |
| 9. Docling PPTX와 정량·정성 비정형 분석 | FR-009/010, Unstructured section, DESIGN 14 | Specified |
| 10. Web App의 프로세스별 check/visualization | FR-024, Web App section, DESIGN 17 | Specified |
| 11. 과제 고유 UUID | FR-001, Dossier section | Specified |
| 12. 추가 체계화 | calibration, audit, security, Gate, ADR, evaluation | Specified |
| 13. frontend/backend와 LG design | Web App section, DESIGN 16~19 | Specified |
| 14. 두 Gate 관리자 HITL과 필수 알림 | FR-027/028, DESIGN 6~9/12, ADR-011 | Reference contract implemented |
| 15. 선택적 mentor와 완료 제출 승인 | FR-029/030, workflow guide | Reference contract implemented |
| 16. RAG adapter와 similarity portion | FR-031, retrieval policy, ADR-012 | Offline lexical contract implemented |
| 17. Markdown checklist 작업지침 | FR-032, docs/rubrics | Draft checklists implemented |
| 18. 요소 모듈·국소 pipeline·전체 workflow 조합 | FR-033~036, DESIGN 4, ADR-013, architecture plan | Supplied-PPTX offline slice implemented; full runtime pending |
| 19. Workflow 구조도와 module별 예측 가능한 작업계획 | FR-037/038, workflow blueprint, module delivery plan | Visual and delivery control baseline documented |
| 20. Excalibur 권한 비유와 사람 책임 철학 | Product brief, concept/manual, authority diagram, D-011 | Applied in offline slice; formal product sign-off pending |
| 21. 미니멀 Library와 expert config | FR-039/040, ADR-014/016, TOML/schema/manual | Offline facade + env-based model reference implemented; full on-prem composition pending |
| 22. OpenAPI 표준 JSON 제어 | FR-041, OpenAPI artifact/examples, API manual | Pre-implementation contract ready |
| 23. 웹툰·강의·매뉴얼 기반 | FR-042, docs/manuals, generated illustrations | Learning baseline documented |
| 24. 개발 전 audit와 readiness Gate | FR-043, development readiness audit | Offline slice verified; actual/operational NO-GO |
| 25. 과정별 progress·milestone·프로젝트 인증 조합 | FR-044~049, education lifecycle, ADR-017 | Actual-PPT offline reference implemented; rollout/auth/credential pending |
| 26. 실제 PPT visual provenance와 근거 품질 회귀 | FR-050~051, ADR-015, evidence-quality eval | Restricted image-only fixture baseline implemented; general render/VLM pending |
| 27. SkillBoss update, HTTP 500 원인복구와 유사 multimodal 비교 | FR-052, ADR-019, WP-05.Q2 recovery report | Qwen/GPT-4o proxy registration verified; exact on-prem/completion/gold pending |
| 28. project cross-file transaction journal과 crash recovery | FR-053, ADR-020, WP-01.R1.1 recovery report | Dossier/audit local slice verified; education/producer/stale-lock recovery pending |

Specified는 구현 완료가 아니라 요구와 수용 방향이 문서에 정의됐다는 뜻이다.

## 27. 현재 완료상태

- [x] 독립 작업공간 생성
- [x] AXCalib 개념과 naming 정의
- [x] WORK_SPEC v0.3 정렬
- [x] AGENTS.md 작업계약 작성
- [x] GOAL.md Target/Gate 작성
- [x] DESIGN.md architecture/UX baseline 작성
- [x] 두 단계 lifecycle과 dossier snapshot 원칙 정의
- [x] Vector DB/model/async/batch/Web 확장계획 정의
- [ ] Sponsor/Product/Evaluation Owner 승인
- [x] executable Codex harness
- [x] package scaffold와 synthetic workflow fixture
- [x] 관리자 HITL/notification/mentor reference contract
- [x] offline Null/Lexical retrieval contract와 similarity policy validation
- [x] 요소 모듈 → 국소 pipeline → total workflow 구현계획과 ADR-013
- [x] workflow blueprint, SVG 인포그래픽과 M00~M13 module delivery control board
- [x] 제품 철학, minimal facade, progressive config와 OpenAPI pre-implementation 계약
- [x] 제품 브리프, quickstart, 권한 구조도와 6컷 튜토리얼
- [x] WP-01 synthetic-only development readiness audit
- [x] 사용자 지시에 따른 supplied-PPTX local/offline slice 착수 승인
- [x] typed PipelineResult/allowlisted Registry와 `two-gate-pptx` working script
- [x] dossier YAML/revision/snapshot, limited PPTX ingest, deterministic report slice
- [x] 두 Gate HITL recording notification과 explicit admin decision integration
- [x] version/hash-bound review policy와 checklist hash drift 검증
- [x] optional Docling manifest, synthetic retrieval baseline, structured model evaluator
- [x] 사용자 승인 하의 비식별 live registration smoke
- [x] versioned EducationProgram과 가입별 generated milestone goals
- [x] manual/score/project typed condition과 allowlisted education pipeline
- [x] 실제 제안 PPTX→별도 synthetic 완료 PPTX→project accepted→program completion HITL 예제
- [x] dossier JSON Schema, multi-process local lock, independent freeze/update script
- [x] local idempotency, durable notification outbox와 secret-free effective-config manifest
- [x] 실제 image-only PPTX의 16/16 deterministic render manifest와 13개 hash-bound gold locator 품질 eval
- [x] JSON-object schema contract, wrapped-upstream safe diagnostic와 model-independent multimodal probe
- [x] SkillBoss Qwen Plus/GPT-4o proxy registration HITL smoke; GLM vision 실패 경계 기록
- [x] project dossier/audit append-only transaction journal, HITL artifact prerequisite와 idempotent recovery
- [x] PipelineContext/checkpoint/result hash/cooperative cancel, JSONL batch와 Alpha Typer CLI
- [x] education enrollment/audit recovery와 stale-lock/orphan quarantine·committed-journal archive
- [ ] Product/Evaluation Owner의 rubric·수치·운영 baseline 정식 sign-off
- [ ] report/outbox producer 자체와 database/distributed worker transaction recovery
- [ ] 일반 PPTX renderer/VLM, Vector DB, on-prem Qwen과 승인된 labeled model/retrieval 품질 spike
- [ ] data/security 승인
- [ ] pilot 시작

## 28. 변경 기록

| 날짜 | Baseline | 변경 |
|---|---|---|
| 2026-07-12 | v0.1 | AI 교육과정 평가 플랫폼 초기 초안 |
| 2026-07-12 | v0.2 | AXCalib로 명명 통일, 두 Gate/dossier/vector/model/async/Web 명세 반영 |
| 2026-07-14 | v0.3 | P1 harness, 관리자 HITL 알림, 선택적 mentor, 두 report, stage RAG/portion/checklist 반영 |
| 2026-07-14 | v0.3-p1 | 요소 모듈, 국소 pipeline, total workflow와 interface parity 구현계약 추가 |
| 2026-07-14 | v0.3-p1 | workflow 구조도, SVG 인포그래픽, module별 Wave·Exit Evidence 계획 추가 |
| 2026-07-15 | v0.3-p1 predev-rc1 | 사람 권한 중심 철학, minimal/expert 설정, OpenAPI 3.1 계약, manual/tutorial, readiness audit 추가 |
| 2026-07-16 | v0.3-p1 mvp-slice1 | 제공 image-only PPTX의 dossier→등록→HITL→수행→완료→HITL offline vertical slice와 report/eval 추가 |
| 2026-07-16 | v0.3-p1 g3-ref1 | hash-bound policy, Docling manifest, synthetic retrieval, structured model gateway와 제한된 live smoke 추가 |
| 2026-07-20 | v0.3-p1 edu-ref1 | versioned 교육 program/enrollment, 실제 PPT project lifecycle, WP-01 local lock/schema/idempotency/outbox/effective-config hardening 추가 |
| 2026-07-21 | v0.3-p1 evidence-q1 | 제한형 actual-PPT render manifest, 13개 hash-bound gold locator와 evidence traceability 품질 eval 추가 |
| 2026-07-21 | v0.3-p1 qwen-capability-q1 | canonical OpenAI-compatible Qwen capability script, alias/exact identity guard, explicit structured-output dialect와 SkillBoss proxy 검증 추가 |
| 2026-07-22 | v0.3-p1 skillboss-http500-q2 | SkillBoss update, JSON-object 500 원인복구, safe wrapped error와 generic multimodal Qwen/GPT-4o/GLM 비교 추가 |
| 2026-07-22 | v0.3-p1 transaction-r1a | project dossier/audit hash-chain journal, HITL artifact prerequisite와 idempotent reconciliation 추가 |
| 2026-07-22 | v0.3-p1 library-alpha | local pipeline checkpoint/cancel/result integrity, education reconcile, non-destructive maintenance, JSONL batch와 Alpha CLI 추가 |
