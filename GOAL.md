---
document_type: project_goal_and_delivery_plan
project: AXCalib
expanded_name: AX Certification Agent Library
baseline: v0.3-p1
created_at: 2026-07-12
updated_at: 2026-07-22
timezone: Asia/Seoul
status: g3_intelligence_reference_baseline_verified
---

# AXCalib Goal과 구현 Target

## 1. 최종 목표

AXCalib의 목표는 한 과제의 등록심의, 수행, 완료평가를 **하나의 추적 가능한 과제 dossier**로 연결하고, 평가기준·체크리스트·과거 유사사례·다중 모델 결과를 근거로 사람이 일관된 인증 판단을 내릴 수 있게 하는 composable Python Library를 만드는 것이다.

성공한 AXCalib는 다음 질문에 재현 가능한 답을 제공한다.

> 어떤 과제가 어떤 버전의 기준과 증거로 등록심의를 통과했고, 수행 중 무엇이 바뀌었으며, 완료평가에서 목표와 KPI를 얼마나 달성했다고 판단했는가?

Library가 안정화된 뒤 같은 기능을 CLI, API, batch worker, on-prem Web App으로 확장한다.

제품의 기억 문장은 **“근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이
인증한다”**다. Excalibur는 이 권한 경계를 설명하는 비유이며 Agent 자동인증을 뜻하지 않는다.

## 2. 구현계획 리뷰 결론

기존 문서는 근거 중심 평가, Human-in-the-loop, 감사 가능성, calibration이라는 방향을 올바르게 잡고 있다. 구현 전 다음 보강이 필요하다.

1. 임시명 AI 교육과정 평가 플랫폼/AICEP를 AXCalib로 통일한다.
2. 단일 제출본 분석이 아니라 등록심의 → 수행 → 완료평가의 상태기계를 명시한다.
3. 하나의 mutable dossier와 평가 시점의 immutable snapshot을 함께 정의한다.
4. 과거 사례 검색을 위한 ingestion, embedding, vector index, retrieval evaluation 계획을 포함한다.
5. on-prem OpenAI-compatible model gateway, Qwen3.5 기본 프로필, 다중 모델 편차 측정을 명세한다.
6. sync/async/batch 계약과 idempotency·resume·부분 실패 처리를 명세한다.
7. Docling 텍스트 추출을 slide rendering, VLM 분석, 정량 품질지표와 결합한다.
8. Core Library와 API/Web App의 의존성 경계를 분리한다.
9. AX Level 정책과 Product Owner가 아직 미정임을 구현 차단이 아닌 정책 Gate로 관리한다.
10. 첫 함수는 작게 유지하고 세부 제어는 expert TOML profile과 typed OpenAPI JSON으로 연다.
11. protected invariant, unknown option, 문서-계약 drift를 machine-readable validation으로 막는다.
12. 제품 브리프, quickstart, 정확한 diagram과 6컷 tutorial을 코드와 같은 기준정보로 유지한다.

## 3. 결정 baseline

상태 의미는 다음과 같다.

- Accepted: 사용자 요구 또는 기존 개념으로 확정된 방향
- Proposed: 초기 구현을 위해 채택할 기본안이며 spike/evaluation 후 변경 가능
- Open: 책임자 결정이나 실제 환경 정보가 필요

| 항목 | 결정 | 상태 |
|---|---|---|
| 공식 이름 | AXCalib / AX Certification Agent Library | Accepted |
| 제품 기억 장치 | Excalibur 비유; Agent는 제안, 권한 있는 사람은 최종결정 | Accepted |
| 제품 문장 | Evidence qualifies. Calibration aligns. Authorized humans certify. | Accepted |
| 제품 출발점 | Python Core Library 우선 | Accepted |
| 첫 인터페이스 | `AXCalib.evaluate/aevaluate` 최소 facade, 동일 result/error 의미 | Accepted |
| 설정 공개 | offline-safe default와 별도 expert TOML profile | Accepted |
| 설정 불변조건 | HITL/알림/사람결정/stale/mentor guard는 조정값이 아님 | Accepted |
| HTTP 계약 | OpenAPI 3.1.0 + JSON Schema 2020-12 typed JSON options | Accepted |
| 구현 단위 | 요소 모듈 → 국소 pipeline → versioned total workflow → thin interface | Accepted |
| Working script | pipeline 검증용 얇은 Python entrypoint이며 업무 로직은 Library에만 둠 | Accepted |
| Architecture control | workflow blueprint와 M00~M13 module control board를 구현상태와 동기화 | Accepted |
| 평가 흐름 | 등록심의와 완료평가의 두 Gate | Accepted |
| 기준 기록 | project_id별 단일 .axc.yaml dossier | Accepted |
| 재현성 | 평가 요청마다 revision + hash snapshot 고정 | Accepted |
| 최종 책임 | 모델 초안 + 사람 최종 판단 | Accepted |
| 관리자 HITL | 등록·완료 final decision은 관리자만 확정 | Accepted |
| 승인요청 알림 | 두 HITL 진입 전에 GitLab MR/email/recording event 필수 | Accepted |
| 멘토 | 선택 배정, 배정 시 완료 제출 전 mentor 승인 필수 | Accepted |
| 모델 환경 | on-prem, BASE_URL/API_KEY 주입, 공급자 교체 가능 | Accepted |
| 기본 모델 | Qwen3.5 multimodal을 가리키는 logical profile | Accepted |
| 모델 실행 | single, panel, adjudicated 세 모드 | Proposed |
| 과거 사례 검색 | stage-aware hybrid retrieval + rerank + case aggregation | Proposed |
| similarity contribution | stage별 설정, offline 기본 0.0, 0.25 초과 owner 승인 guard | Proposed |
| 기본 Vector DB | Qdrant, in-memory adapter를 테스트에 사용 | Proposed |
| 메타데이터 저장 | 개발 SQLite, 파일럿 PostgreSQL | Proposed |
| Agent framework | Deep Agents optional extra, deterministic workflow가 기준 | Proposed |
| Web App | FE stack과 주 디자인은 사용자 선택 대기; Python API/worker와 분리 | Open |
| AX Level/합격선 | rubric registry로 외부화 | Open |
| 첫 실제 파일럿 과정 | 하나의 AX 과제 유형 선정 필요 | Open |
| 라이선스/공개범위 | 내부 전용 또는 공개 패키지 결정 필요 | Open |

## 4. 첫 번째 Product Target

### Target T1: Offline Evidence-to-Review Vertical Slice

2026-07-20 현재 제공된 image-only PPTX 한 건에 대해 이 흐름의 executable slice와 G3
Intelligence reference contract가 통과했다. hash-bound review policy registry, Docling parser
manifest, 작은 synthetic lexical retrieval baseline, strict structured model evaluator와 사용자 승인
하의 live registration smoke를 포함한다. 독립 freeze/update pipeline, dossier JSON Schema,
filesystem lock, local idempotency, durable recording outbox와 effective-config manifest도 reference
수준으로 검증했다. 2026-07-22 R1/I1/I2a에서 project·education transaction recovery,
PipelineContext/checkpoint/cancel, Typer CLI/batch, non-destructive maintenance, fail-closed runtime API,
principal-bound project/education command와 URI-redacted project GET/decision replay contract까지 local
Alpha로 검증했다. WP-06.I3에서는 exact queued grant의 202, hash-bound local job, lease reclaim,
retryable-only bounded retry와 terminal replay를 같은 executor에 연결했다. 단, report/outbox producer,
OIDC/JWKS·immutable upload·distributed broker/heartbeat와 운영 품질평가는 남아 있으므로 제품 전체나
운영 MVP 완료로 기록하지 않는다.

2026-07-23 WP-00.D2에서는 사용자 매뉴얼·실습·코드/프로젝트 설명을 main `wiki/` 단일 원본으로
두고 `PROJECT_STATE.md` 개발원장을 자동 mirror하는 GitHub/GitLab portable publication contract를
추가했다. local validation/export parity와 GitHub Wiki live push/page·asset render를 검증하고
automatic publish variable도 활성화했다. 사내 GitLab remote·runner·credential과 실제 화면
publication은 플랫폼 Owner 작업으로 남는다.

2026-07-21 `WP-02.Q1`에서는 제공 PPTX의 16/16 slide를 제한형 embedded-image renderer로
재현하고, 13개 reviewed locator와 12개 reference field를 source/sidecar hash에 고정한 품질
baseline을 추가했다. 이 결과는 해당 fixture의 provenance·coverage·traceability 계약만 검증하며,
일반 PPTX semantic extraction, VLM 또는 공식 rubric 품질을 의미하지 않는다.

네트워크와 실제 사내 데이터 없이 다음 전체 흐름이 한 번에 실행되는 Python package와 CLI를 첫 Target으로 한다.

~~~text
dossier 생성
→ 등록자료/PPTX 참조 추가
→ schema 검증
→ 등록심의 revision freeze
→ mock evaluator로 criterion별 근거 리포트 생성
→ 관리자 승인요청 알림과 HITL 등록 승인·반려
→ 승인 시 선택적 mentor 배정
→ 수행 진행·멘토링·산출물·KPI 갱신
→ 완료 제출 리포트와 mentor/owner 승인 등록
→ 완료평가 revision freeze
→ 등록 당시 약속과 완료 증거 비교
→ mock evaluator로 완료 리포트 생성
→ 관리자 승인요청 알림과 HITL 완료판정 기록
→ Markdown/JSON report 생성
~~~

### T1 지원 범위

- dossier schema: axcalib.dossier/v1alpha2; v1alpha1 explicit migration 지원
- ID: UUID4 project_id와 별도 human-readable display_id
- 입력: YAML dossier, Markdown/TXT, 제한된 PPTX synthetic fixture
- rubric: 등록심의·완료평가를 묶은 version/hash-bound YAML policy pack 1개
- evaluator: deterministic 1개, optional strict structured model evaluator 1개
- retrieval: NullRetriever/LexicalRetriever, stage filter, similarity portion 기본 0.0
- parser: safe OOXML/sidecar와 optional Docling run manifest
- notification: offline RecordingNotifier
- storage: local filesystem
- output: updated dossier, immutable snapshot, structured JSON, Markdown report
- interface: Python API, Typer CLI와 in-process FastAPI project/runtime Alpha
- public facade: `AXCalib().evaluate/aevaluate`, expert `from_toml(...)`
- pipeline kernel: typed context/result/status/registry와 sync/async parity
- working scripts: dossier freeze, 등록심의, 완료평가, two-gate synthetic entrypoint
- education composition: immutable program, enrollment goal generation, manual/score/project milestone,
  program completion HITL

### T1 수용기준

- 하나의 dossier로 두 Gate와 수행 이력을 round-trip할 수 있다.
- 허용되지 않은 상태 전이를 100% 거부한다.
- 동일한 dossier revision을 freeze하면 같은 hash를 얻는다.
- stale revision에 대한 평가 결과를 현재 dossier에 자동 병합하지 않는다.
- 모든 criterion 결과가 evidence locator 또는 insufficient_evidence를 가진다.
- Agent가 registration_approved/rejected 또는 completion_accepted/not_accepted를 직접 확정하지 못한다.
- 두 HITL pending 진입은 notification event 없이는 실패한다.
- mentor가 배정된 경우 mentor 승인 없이 completion_registered로 전이하지 못한다.
- registration query에서 completion case가 누출되지 않는다.
- 국소 pipeline은 FastAPI/Typer/Web 없이 import하고 실행할 수 있다.
- working script와 CLI가 같은 pipeline id/version과 구조적 result를 사용한다.
- total workflow의 waiting_human/stale/retryable/terminal 상태가 success와 구분된다.
- unit/integration test는 network, API key, GPU 없이 통과한다.
- fixture에 비밀정보와 실제 개인정보가 없다.
- 새 터미널에서 문서화된 명령으로 재현할 수 있다.
- default TOML과 expert example이 schema를 통과하고 unknown/protected key를 거부한다.
- OpenAPI request options에 관리자 전용 상태나 HITL 우회 필드가 존재하지 않는다.
- 적용된 설정이 secret을 제외한 effective-config hash/source map으로 실행기록에 연결된다.
- 가입이 exact program version/hash를 고정하고 prerequisite에 따라 milestone을 단계적으로 연다.
- project milestone은 exact enrollment context와 저장된 dossier 상태만 사용한다.
- 필수 milestone 충족만으로 과정 완료되지 않고 notification과 관리자 HITL에서 대기한다.

## 5. MVP와 파일럿의 경계

### MVP에 포함

- versioned dossier와 state machine
- registration/completion pipeline
- rubric/checklist registry
- evidence extraction과 locator
- Docling PPTX adapter spike
- 과거 사례 ingestion/index/search
- structured evaluator와 report
- model gateway와 Qwen3.5 profile
- multi-model independent panel과 disagreement report
- sync/async/batch API
- CLI와 minimal FastAPI
- audit metadata와 offline evaluation harness
- GitLab/email/recording notification port와 review request audit
- stage별 retrieval adapter와 configurable similarity portion

### MVP에서 제외

- 사람 없이 자동 합격·불합격·인증 확정
- 모든 PPTX 디자인과 영상의 완전한 자동 해석
- AX Level 정책 자체의 확정
- 공식 Credential 발급과 법적 효력
- 기존 운영 인증 DB의 직접 갱신
- 전사 SSO, HA, DR, 운영 SLA
- 완성형 Studio와 mobile app
- 승인 전 실제 개인정보·기밀자료 처리

### 파일럿 데이터 Target

- 개발: 20개 이상의 paired synthetic dossier
- retrieval 평가: 사람이 유사사례 relevance를 표시한 query-case pair
- 승인 후 파일럿: 등록심의와 완료평가가 연결된 비식별 과제 50쌍
- 분포: 우수, 보통, 미달, 경계, 자료부족 사례 포함
- calibration/evaluation set은 prompt 튜닝 자료와 분리

## 6. 제안 품질 Target

아래 수치는 Gate 0에서 Product Owner와 평가 책임자가 승인하기 전까지 **제안값**이다.

| 영역 | 제안 Target |
|---|---|
| Schema | 지원 fixture 100% validate, 손실 없는 round-trip |
| State | 금지 전이와 stale write 100% 차단 |
| Parser | 필수 필드 coverage 95% 이상 |
| Evidence | 평가 항목의 evidence traceability 95% 이상 |
| Unsupported claim | 근거 없는 충족 판정 2% 미만, 치명적 사례 0 |
| Retrieval | labeled set Recall@5 0.80 이상, nDCG@5 추적 |
| Reproducibility | 동일 mock 입력·버전에서 구조적 결과 100% 일치 |
| Multi-model | criterion별 분산·불일치 사유 100% 노출 |
| Human review | 자동 최종판정 0건, 모든 최종결정 reviewer 기록 |
| Notification | 두 HITL Gate의 승인요청 event 누락 0건 |
| 효율 | 기존 사람 검토시간 대비 중앙값 30% 이상 절감 |
| 보안 | secret/개인정보 fixture·log 유출 0건 |

LLM 문장 자체의 byte-level 동일성을 요구하지 않는다. 대신 입력·설정·출력·근거를 재생성할 수 있고, 구조와 판정 분포의 변화를 측정해야 한다.

## 7. 구현 단계와 Gate

| 단계 | 작업 | 핵심 산출물 | Exit Gate |
|---|---|---|---|
| P0 Planning | 명명·목표·제품철학·설계 정렬 | AGENTS, GOAL, DESIGN, WORK_SPEC, product/manual/readiness | 문서 간 충돌 없음, owner sign-off |
| P1 Harness | 실행 뼈대와 reference workflow | pyproject, prep.ps1, harness, state/decision/risk, synthetic flow | 구현 완료, predev contract validation |
| P2 Domain | dossier/schema/state machine와 pipeline kernel | core package, local pipeline contract, working script, fixtures | T1 상태·snapshot 수용기준 |
| P3 Evidence | parser와 provenance | Docling adapter, locators, extraction metrics | PPTX fixture 추출 회귀 |
| P4 Retrieval | 과거사례 index/search | embedding adapter, Qdrant adapter, corpus manifest | retrieval baseline 충족 |
| P5 Evaluation | rubric evaluator와 report | structured result, registration/completion workflows | evidence traceability 충족 |
| P6 Calibration | 다중 모델과 편차 분석 | panel runner, disagreement, adjudication | model별 결과 재현 |
| P7 Interfaces | CLI/API/async/batch | Typer, FastAPI, batch manifest/resume | contract test 통과 |
| P8 Web Review | 사람 검토 UI | LG-based design system, task detail/review/calibration UI | 주요 사용자 흐름 E2E |
| P9 Pilot | 비식별 실제 자료 검증 | 50쌍 report, 위험·시간·비용 분석 | Continue/Narrow/Stop 결정 |

G3의 현재 판정은 **reference baseline verified**다. supplied fixture와 synthetic dataset으로 parser,
stage-separated retrieval, structured model/report 계약을 확인했다는 뜻이며, 실제 template coverage,
Vector DB/embedding, gold label 품질, on-prem Qwen endpoint 또는 model calibration을 통과했다는 뜻이
아니다.

## 8. Work Package

### WP-00 Harness

- pyproject.toml과 src layout
- prep.ps1 status/next/validate/test/eval
- PROJECT_STATE.md, DECISIONS.md, RISK_REGISTER.md
- PROJECT_STATE 단일 실행 원장의 P/WP/G dependency Gantt, Active Slice, 검증·특이사항과
  append-only 작업 이력 contract
- Ruff, Pyright, pytest, coverage, secret scan
- synthetic-only 기본 설정
- 관리자 전용 final transition과 mandatory notification reference contract
- Null/Lexical retrieval과 similarity policy validation
- workflow 계층·두 Gate·sequence·실패/재개·module dependency 구조도
- M00~M13 module control board, dependency Wave와 Exit Evidence
- 유지보수 가능한 Mermaid 원문과 SVG 한 장 인포그래픽
- product brief, 5분 quickstart, 권한 SVG, 6컷 tutorial과 development readiness audit
- minimal/expert TOML, runtime JSON Schema와 OpenAPI pre-implementation artifact
- platform-neutral `wiki/` source, PROJECT_STATE mirror, GitHub/GitLab export parity와 opt-in CI

### WP-01 Dossier와 상태기계

- PipelineContext, PipelineRun status/result, allowlisted PipelineRegistry 최소계약
- Dossier Pydantic models와 JSON Schema export
- YAML serializer와 canonical hash
- atomic write, revision lock, snapshot repository
- registration/execution/completion 상태 전이
- review request/notification outbox의 atomic persistence
- mentor assignment와 conditional completion approval
- schema migration interface
- `dossier.initialize`, `dossier.update`, `dossier.freeze` 국소 pipeline
- `scripts/pipelines/run_dossier_freeze.py` working script와 interface boundary test

### WP-01E 교육 프로그램 Composition Reference

- immutable `EducationProgram@version`과 canonical hash
- 가입 시 `EducationEnrollment` 및 ordered/locked milestone 목표 생성
- allowlisted manual confirmation, score threshold, project status requirement
- program/version/enrollment/milestone/learner exact-context project binding
- project `completion_accepted`를 과정 milestone 근거로 sync
- 필수 milestone 충족 뒤 관리자 notification과 completion HITL
- 명시적 approve 또는 selected milestone `return_for_revision`
- 실제 제안 PPTX와 별도 synthetic 완료 PPTX를 사용한 end-to-end Library 예제

이 WP는 과정 전체 credential 정책, learner identity 인증, program migration 또는 Web course builder를
완료한 것이 아니다. 상세 경계는 ADR-017과 교육 lifecycle 문서를 따른다.

### WP-02 Evidence ingestion

- ArtifactRef와 content hash
- Markdown/TXT parser
- Docling PPTX parser
- slide image rendering adapter
- source locator, extraction coverage, parse warning

`WP-02.Q1 Actual-PPT Evidence Quality Baseline` 완료 범위:

- single full-slide embedded PNG 또는 true blank만 허용하는 `SlideRenderer` reference adapter
- 16/16 slide artifact와 source/image SHA-256 render manifest; 13 visual, 3 blank
- 13개 reviewed locator와 12개 reference field의 hash-bound gold fixture
- locator recall, field coverage, criterion traceability, unsupported-claim 회귀 eval
- Docling 16 page / 0 text 결과와 reviewed sidecar evidence의 출처 분리

남은 범위는 실제 복수 template field mapping, 합성 slide를 지원하는 승인된 renderer, OCR/VLM,
공식 rubric 기반 semantic gold label과 운영 parser sandbox다.

### WP-03 Rubric과 Evaluation

- versioned rubric/criterion schema
- deterministic checklist engine
- structured model evaluator
- evidence binding과 판단불가
- registration/completion report renderer
- Agent recommendation과 administrator decision 분리
- Markdown checklist loader/version validation

### WP-04 Historical Cases

- 비식별/접근등급 검사
- stage-aware chunking
- Qwen3 embedding adapter
- Qdrant collection과 payload index
- hybrid retrieval, rerank, case aggregation
- corpus snapshot과 reindex
- Recall@k/nDCG@k evaluation
- stage/rubric별 similarity portion과 unavailable fail-closed policy

### WP-05 Model Gateway와 Agent

- OpenAI-compatible HTTP client
- Qwen3.5 primary profile
- capability probe: text, vision, tool calling, structured output
- canonical `OPENAI_API_KEY`/`OPENAI_BASE_URL`/`OPENAI_MODEL` deployment script
- provider alias와 exact checkpoint identity 분리; response model 미보고 시 fail-closed
- explicit `json_schema`/`json_object` dialect와 output token limit; silent fallback 금지
- raw output와 hidden reasoning을 보존하지 않는 capability report
- timeout, retry, concurrency, token/latency logging
- single/panel/adjudicated runner
- optional Deep Agents adapter

### WP-06 Async, Batch, API

현재 local Alpha evidence: sync/async executor, bounded JSONL batch, Alpha CLI, fail-closed FastAPI
catalog/run/status/cancel, principal-bound project register/read/registration/completion decision replay, 교육
program 조회·self enrollment·milestone/reviewer/project sync·completion decision과 generated runtime
OpenAPI, exact queued grant의 202와 single-host durable queue/one-job Worker. approved OIDC/RBAC·교육
배정 원장, immutable upload service, distributed broker/heartbeat, SSE와 full workflow parity는 아직 남아
있다.

- sync/async parity
- bounded concurrency와 cancellation
- JSONL batch manifest, idempotency, checkpoint/resume
- versioned total workflow registry와 branch/wait-human/resume runner
- FastAPI OpenAPI 3.1
- OpenAPI 3.1.0 artifact-first contract, JSON Schema 2020-12와 generated client parity
- allowlisted per-request options, bearer auth/RBAC boundary와 Problem Details
- project owner/admin principal·scope·organization·revision binding과 no-path staged artifact hash contract
- owner/admin project read scope와 URI/free-text redaction, principal/resource/payload-bound decision replay
- learner/mentor/instructor/administrator resource scope·organization·program hash·revision binding
- OpenAPI 3.2/TOML 1.1 toolchain compatibility spike
- typed/hash-bound local worker queue, oldest-available lease/reclaim, retryable-only bounded retry와 terminal replay
- queued 202/Location/Retry-After, authorized poll/cancel과 독립 queue status
- distributed worker port, heartbeat/dead-letter/metrics와 운영 adapter

### WP-07 Web Review

- task portfolio와 stage board
- dossier detail/editor
- registration/completion review workbench
- evidence viewer와 source locator
- model disagreement/calibration view
- reviewer decision과 audit timeline
- role/permission UI

### WP-08 Pilot and Calibration

- 비식별 paired dataset
- expert baseline과 boundary cases
- parser/retrieval/assessment/calibration metrics
- subgroup·rubric version별 오류 분석
- Go/No-Go 및 운영 전환 조건

### 8.1 모든 WP의 공통 납품 순서

각 capability는 domain schema/port → 요소 모듈과 unit test → 국소 pipeline과 in-memory
integration test → 실행 가능한 synthetic Python script → test/eval → CLI/API/worker 노출 순으로
진행한다. script나 route에 domain 로직을 먼저 작성한 뒤 library로 옮기는 방식을 사용하지 않는다.

module 상태가 바뀌면 `module-delivery-plan.md` control board, `workflow-blueprint.md` 구조도,
`PROJECT_STATE.md`와 요구 추적표를 같은 change set에서 갱신한다. 날짜 기반 진척률 대신
선행조건과 Exit Evidence로 다음 Wave 진입 여부를 판단한다.

전체 workflow는 검증된 local pipeline id/version만 registry에서 조합한다. MVP에서는 arbitrary
YAML graph, 임의 import path 또는 expression 실행을 허용하지 않는다. 상세 계획은
`docs/architecture/composable-pipeline-plan.md`를 따른다.

## 9. 기술 스택 Target

정확한 버전은 scaffold 시 호환성 spike 후 pyproject와 lockfile에 고정한다.

| 계층 | 기본 선택 | 이유와 경계 |
|---|---|---|
| Runtime | Python 3.12+ | 기존 WORK_SPEC과 on-prem 생태계 정렬 |
| Packaging | uv + hatchling | library-first, 빠른 재현 환경 |
| Domain schema | Pydantic v2 | validation과 JSON Schema 2020-12 export |
| Dossier format | YAML 1.2 + JSON Schema | 사람 편집성과 기계 검증 |
| YAML adapter | ruamel.yaml | 안정적 round-trip과 명시적 formatting |
| CLI | Typer + Rich | type 기반 명령과 PowerShell 친화 출력 |
| API | FastAPI | Pydantic 공유, OpenAPI 3.1.0 artifact-first 계약 |
| API/config schema | JSON Schema Draft 2020-12 / TOML 1.0 범위 | generator와 Python 3.12 stdlib 호환 |
| HTTP/Async | HTTPX + AnyIO | sync/async parity와 bounded concurrency |
| Retry | Tenacity | transient error 정책 분리 |
| Parsing | Docling optional extra | PPTX 포함 unified document model과 local 실행 |
| Slide visual | LibreOffice render + VLM adapter | 구조 추출과 시각 해석을 분리 |
| Embedding | Qwen3-Embedding-0.6B 후보 | on-prem multilingual baseline, 평가 후 승격 |
| Reranker | Qwen3-Reranker-0.6B 후보 | 동일 계열의 on-prem ranking baseline, labeled set으로 검증 |
| Vector store | Qdrant | metadata filter, dense/sparse hybrid, self-host |
| Metadata DB | SQLite dev / PostgreSQL pilot | 로컬 단순성, 운영 transaction/audit |
| ORM/Migration | SQLAlchemy + Alembic | service 단계의 schema 관리 |
| Artifact store | filesystem dev / S3-compatible MinIO pilot | 대용량 원문과 파생물 분리 |
| Model serving | vLLM 또는 승인된 OpenAI-compatible server | BASE_URL 기반 교체 |
| Default evaluator | Qwen3.5 logical profile | multimodal on-prem 기본, 실제 ID는 config |
| Agent | Deep Agents optional extra | 비정형 탐색에만 사용, core 비의존 |
| Test | pytest + Hypothesis | fixture 회귀와 state/schema property test |
| Quality | Ruff + Pyright | 빠른 lint/format과 strict typing |
| Observability | structlog + OpenTelemetry | run/model/retrieval trace 연계 |
| Frontend | Open; React + Vite + React Router Data Mode 권장 | 사용자 디자인/stack 선택 후 확정 |
| UI foundation | CSS tokens + Tailwind + Radix primitives | LG token 적용과 접근성 |
| Data fetch | generated OpenAPI client + TanStack Query | backend contract 일원화 |
| Visualization | ECharts | pipeline, model variance, calibration 차트 |

## 10. 모델 Target

### 10.1 Profile 계약

도메인 코드에는 Qwen 모델명을 직접 쓰지 않고 logical profile만 전달한다.

~~~yaml
profiles:
  primary:
    provider: openai_compatible
    model: $AXCALIB_PRIMARY_MODEL
    base_url: $AXCALIB_PRIMARY_BASE_URL
    api_key_env: AXCALIB_PRIMARY_API_KEY
    capabilities: [text, vision, structured_output, tool_calling]
  secondary:
    provider: openai_compatible
    model: $AXCALIB_SECONDARY_MODEL
    base_url: $AXCALIB_SECONDARY_BASE_URL
    api_key_env: AXCALIB_SECONDARY_API_KEY
    capabilities: [text, structured_output]
~~~

초기 on-prem served model ID는 사용자 계획에 따라 `Qwen3.5-397B-A17B`를 사용한다. hardware,
한국어, PPTX slide 이해, structured output, tool calling 평가를 통과하기 전 운영 기본모델로
승격하지 않는다. 외부 endpoint에서 `OPENAI_MODEL`이 없으면 reference adapter는 `gpt-5.5`를
기본값으로 사용한다.

### 10.2 실행 모드

- single: primary 한 모델로 초안 생성
- panel: 2개 이상 모델이 서로의 결과를 보지 않고 독립 평가
- adjudicated: disagreement가 threshold를 넘으면 별도 모델 또는 사람이 재검토
- repeatability: 같은 모델을 seed/temperature profile별로 반복하여 intra-model 분산 측정

다중 모델 합의는 오류가 상쇄된다는 가정이 아니다. criterion별 분산, 누락 근거, 방향성 편향을 사람에게 보여 주는 것이 우선이다.

## 11. 과거 사례 Vector DB Target

### 11.1 Ingestion

~~~text
원본 등록
→ 접근등급/비식별 검사
→ Docling/전용 parser
→ 공통 evidence schema
→ registration/completion별 semantic section
→ chunk + metadata + provenance
→ dense/sparse embedding
→ Qdrant upsert
→ corpus manifest와 evaluation
~~~

### 11.2 필수 metadata

- case_id, project_id_pseudonymized
- review_stage
- project_type, domain, organization_group
- rubric_id, rubric_version
- criterion_ids
- outcome_class와 boundary_flag
- source_revision, source_hash
- parser_version, chunker_version
- embedding_model, embedding_dimension
- access_classification
- corpus_snapshot_id

### 11.3 Query

- registration은 목표, 문제정의, 수행계획, KPI 타당성을 중심으로 검색한다.
- completion은 약속 대비 수행증거, KPI 결과, 산출물, 변경사유를 중심으로 검색한다.
- metadata filter 후 lexical+dense top 20, rerank top 8, case aggregate top 5를 초기값으로 둔다.
- 리포트는 유사점과 차이점, score, source locator, 적용 한계를 함께 표시한다.
- historical outcome을 새 과제의 label로 복사하지 않는다.

## 12. 계획된 공개 인터페이스

### Python

~~~python
from axcalib import AXCalib, Dossier

client = AXCalib.from_profile("onprem")
dossier = Dossier.load("AXC-<uuid>.axc.yaml")

registration = client.evaluate_registration(dossier, mode="panel")
completion = await client.aevaluate_completion(dossier, mode="adjudicated")
~~~

`AXCalib`은 편의 facade다. 내부에서는 allowlisted pipeline/workflow registry에 위임한다. 세부
조합이 필요한 library 사용자는 `runtime.pipelines.<name>.run/arun`과
`runtime.workflows.start/resume`을 사용하되 동일 request/result schema를 공유한다.

### CLI

~~~powershell
axcalib dossier init --title "과제명"
axcalib dossier validate .\AXC-<uuid>.axc.yaml
axcalib submit registration .\AXC-<uuid>.axc.yaml
axcalib evaluate registration .\AXC-<uuid>.axc.yaml --mode panel
axcalib dossier update .\AXC-<uuid>.axc.yaml --patch .\progress.yaml
axcalib submit completion .\AXC-<uuid>.axc.yaml
axcalib evaluate completion .\AXC-<uuid>.axc.yaml --mode panel
axcalib cases index .\cases --corpus ax-projects-v1
axcalib batch run .\batch.jsonl --resume
~~~

### API

- POST /v1/projects
- GET/PATCH /v1/projects/{project_id}/dossier
- POST /v1/projects/{project_id}/snapshots
- POST /v1/projects/{project_id}/registration-evaluations
- POST /v1/projects/{project_id}/completion-evaluations
- POST /v1/projects/{project_id}/review-decisions
- POST /v1/cases/ingestion-jobs
- POST /v1/similarity-searches
- POST /v1/batches
- GET /v1/runs/{run_id}
- GET /v1/reports/{report_id}

mutating endpoint는 expected_revision과 Idempotency-Key를 요구한다.

## 13. 제안 디렉터리 Target

~~~text
src/axcalib/
  core/           # ID, clock, errors, protocols
  schemas/        # dossier, rubric, evidence, result
  dossier/        # repository, state machine, snapshot
  ingest/         # Docling and format adapters
  retrieval/      # chunk, embed, index, query, rerank
  evaluation/     # checklist and model evaluator
  calibration/    # panel, disagreement, metrics
  models/         # gateway and provider adapters
  pipelines/      # typed local application pipelines
  workflows/      # versioned total workflow composition
  runtime/        # dependency container and profiles
  reports/        # Markdown/JSON/PDF render ports
  audit/          # run manifest and provenance
  cli/            # Typer
  api/            # optional FastAPI
scripts/pipelines/ # thin executable pipeline examples
~~~

core, schemas, dossier는 ingest/retrieval/models/api를 import하지 않는다. pipelines가 domain
module과 port를 조합하고 workflows는 검증된 pipeline만 연결한다. 외부 구현은 runtime profile의
dependency injection으로 전달한다.

## 14. 주요 위험과 대응

| 위험 | 대응 |
|---|---|
| 하나의 파일에 모든 것을 넣어 충돌·비대화 | dossier에는 구조와 참조만, 원문은 content-addressed artifact로 분리 |
| 평가 중 dossier 변경 | revision freeze, optimistic concurrency, stale result 격리 |
| 과거 편향을 정답처럼 재사용 | similarity와 decision 분리, outcome blind evaluation, 사람 검토 |
| 관리자 알림 누락 | HITL 전이 전 notification 필수, outbox/retry |
| mentor 승인 우회 | mentor_ref 존재 시 completion submission guard |
| similarity portion 과대 설정 | 기본 0, 0.25 초과 warning과 Evaluation Owner 승인 |
| PPTX 텍스트만 읽어 시각 의미 누락 | Docling + slide rendering + VLM, extraction quality 표시 |
| 모델별 점수 평균이 오류를 은폐 | criterion별 독립결과와 disagreement 우선 표시 |
| Qwen3.5 endpoint별 기능 차이 | startup capability probe와 contract test |
| Deep Agents가 상태기계를 우회 | optional adapter, domain command만 tool로 노출 |
| batch 재시도로 중복 평가 | idempotency key, snapshot hash, checkpoint |
| 브랜드 오용 | 공식 LG 자산과 라이선스 승인 전 token 기반 internal prototype만 |
| AX Level 정책 미정 | rubric/policy registry로 외부화, 인증 확정은 Gate로 보류 |
| 국소 pipeline 폭증과 경계 혼란 | 독립 업무결과와 재사용자가 있을 때만 pipeline으로 승격 |
| script/API별 로직 복제 | thin adapter와 동일 fixture interface-parity contract test |
| 범용 workflow engine 조기개발 | 명시적 Python composition과 allowlisted registry부터 시작 |
| GitHub/GitLab Wiki와 코드 문서 drift | main `wiki/` 단일 원본, ledger mirror, manifest와 dual-target parity validation |

## 15. Open Decisions

P0 이후 다음 결정이 필요하다.

1. 첫 실제 AX 과제 유형과 담당 Product Owner
2. 등록심의·완료평가 rubric 원본과 version owner
3. AX Level 이름, 필수역량, 합격선, 재평가 정책
4. 실제 PPTX/원시트 template과 허용 파일형식
5. on-prem GPU와 Qwen3.5 serving endpoint 사양
6. 과거 사례 데이터의 이용근거, 비식별 수준, 보존기간
7. PostgreSQL/Qdrant/MinIO 운영 주체와 backup
8. SSO/RBAC와 reviewer 승인권한
9. 공식 LG design asset 접근권한
10. 내부 전용/오픈소스 license와 package registry
11. 운영 승인요청 수단: GitLab Merge Request, email 또는 둘 다
12. registration/completion similarity portion 기본값과 승인 상한
13. mentor가 없는 완료 제출의 최종 확인 역할
14. Web frontend stack과 주 디자인 선택
15. pre-development baseline과 WP-01 synthetic-only slice 승인
16. 교육 program publish/retire/version owner와 기존 enrollment migration 정책
17. 과정 완료와 공식 credential 발급을 분리하는 권한·유효기간·재인증 정책
18. 수업 이수, 점수, 면제, 재수강, 기한을 확인할 trusted source system과 역할
19. GitHub/GitLab Wiki CI runner·deploy credential Owner와 team-owned page 보존 정책

이 결정이 없어도 WP-01~03 synthetic/offline 작업은 진행할 수 있다. 실제 데이터, 모델 품질
확정, 운영 알림, 인증 정책, 운영 배포는 해당 결정 전에는 진행하지 않는다.

## 16. P0 완료조건

- [x] 공식 이름과 library-first 원칙 정의
- [x] 두 단계 상태 흐름 정의
- [x] 단일 dossier와 immutable snapshot 원칙 정의
- [x] on-prem/different-model 전략 정의
- [x] Vector DB와 embedding 계획 정의
- [x] async/batch/API/Web App 확장계획 정의
- [x] AGENTS.md 작업 계약 작성
- [x] DESIGN.md architecture/UX baseline 작성
- [x] WORK_SPEC.md를 AXCalib v0.3으로 정렬
- [ ] Product Owner가 제안 Target과 수치를 승인
- [x] P1 Harness 구현 시작 승인
- [x] executable prep/status/validate/test/eval 구축
- [x] 관리자 HITL/notification/mentor reference workflow 구축
- [x] composable local pipeline과 total workflow 구현계획 확정
- [x] workflow 구조도·SVG 인포그래픽·module별 상세 작업계획 작성
- [x] 사람 권한 중심 제품 브리프와 Excalibur 기억 장치 정렬
- [x] minimal facade, expert TOML, runtime schema, OpenAPI 3.1 계약
- [x] quickstart, 권한 diagram, 6컷 tutorial과 개발 준비 감사
- [x] supplied-PPTX two-gate local pipeline, script, report와 offline eval
- [x] hash-bound review policy registry와 사람 reviewer adjustment 감사계약
- [x] optional Docling PPTX adapter와 zero-text parser manifest contract
- [x] supplied image-only PPTX의 deterministic 16-slide render manifest와 13-locator evidence-quality baseline
- [x] OpenAI-compatible structured evaluator와 on-prem Qwen3.5 환경계약
- [x] SkillBoss Qwen3.5 Plus proxy의 structured text/vision capability와 exact-ID 분리 contract
- [x] SkillBoss Qwen Plus full registration의 JSON-object HTTP 500 원인복구와 HITL pending smoke
- [x] model-independent multimodal probe와 GPT-4o proxy text/vision 대조; GLM vision 실패 경계
- [x] project dossier/audit transaction journal과 3개 write-boundary crash/reconcile reference
- [x] education enrollment/audit transaction과 stale-lock/orphan quarantine·journal archive
- [ ] report/outbox producer 자체와 database/distributed worker transaction recovery
- [ ] exact on-prem `Qwen3.5-397B-A17B` capability 및 full two-gate quality 검증
- [x] synthetic stage-aware retrieval baseline과 제한된 live registration smoke
- [x] 사용자 최신 지시로 local/offline slice 구현 범위 승인
- [x] full PipelineContext/checkpoint/cancel과 독립 dossier.freeze/update pipeline 구현
- [x] strict JSONL batch, Alpha Typer CLI와 clean-wheel actual-PPTX quickstart
- [x] single-host durable 202 queue, restart/reclaim/retry/cancel과 one-job Worker local contract
- [x] GitHub/GitLab 공통 Wiki 원본, 개발원장 mirror, export/parity와 opt-in CI contract
- [ ] Product/Evaluation Owner의 rubric·운영 baseline 정식 sign-off

## 17. 기술 근거

- [Qwen3.5 모델 문서](https://huggingface.co/docs/transformers/model_doc/qwen3_5)
- [Qwen3.5-9B 공식 모델 카드](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Qwen3 Embedding 공식 모델](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [Qwen3 Reranker 공식 모델](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- [vLLM OpenAI-compatible server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/)
- [Deep Agents model configuration](https://docs.langchain.com/oss/python/deepagents/models)
- [Docling supported formats](https://docling-project.github.io/docling/usage/supported_formats/)
- [Qdrant hybrid search](https://qdrant.tech/documentation/search/text-search/hybrid-search/)
- [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)
