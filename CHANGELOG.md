# AXCalib 변경 이력

이 문서는 사용자와 개발자가 제품의 큰 변화를 빠르게 확인하기 위한 기록이다. 세부 작업 순서와
검증 이력은 `PROJECT_STATE.md`, 설계 결정은 `DECISIONS.md`와 `docs/adr/`를 기준으로 한다.

## Unreleased

### 추가

- project create/update의 dossier와 audit를 묶는 append-only hash-chain transaction journal
- `project.transaction.reconcile@v1alpha1` library pipeline과 thin recovery script
- prepare, dossier, audit 직후 synthetic crash 3종과 반복 reconciliation evaluation
- education enrollment/audit용 append-only transaction journal과
  `education.transaction.reconcile@v1alpha1`
- request/context/result hash, per-run lease, sync/async, cooperative cancel과 replay를 보존하는 local
  pipeline executor
- strict JSONL manifest hash, item별 checkpoint/부분실패와 bounded concurrency를 가진 local batch
- report-only 기본 stale artifact 검사와 quarantine/archive를 제공하는
  `workspace.maintenance@v1alpha1`
- optional `cli` extra의 Typer/Rich Alpha CLI와 실제 PPTX 등록심의 quickstart
- local Library MVP/Alpha 고정 evaluation
- optional `api` extra의 fail-closed FastAPI factory와 pipeline catalog/run/status/cancel route
- deployment-owned bearer `TokenVerifier`, exact `ApiPipelineGrant`, run owner/scope authorization
- 실제 route에서 생성한 `openapi.runtime.v1alpha1.json`과 API contract regression
- principal-bound project registration과 registration/completion administrator decision endpoint
- local path를 받지 않는 `StagedArtifactResolver`, media/size/SHA-256 verification과 API threat model
- principal-bound program 조회/self enrollment, milestone start/manual/score/project bind·sync와
  education completion decision endpoint
- learner/mentor/instructor/administrator별 resource assignment scope, organization, program hash와
  enrollment revision contract
- owner/admin scope와 organization을 검사하는 URI/free-text redacted project current-state GET
- principal/resource/stage/revision/payload에 고정된 registration/completion decision semantic replay
- exact delivery grant별 inline/queued mode와 HTTP 202 `Location`/`Retry-After`
- validated 1 MiB 이하 hash-bound job envelope, oldest-available lease/reclaim와 one-job local Worker
- retryable-only bounded backoff, terminal replay, 독립 execution/queue poll status와 worker script
- GitHub/GitLab Wiki에 공통 배포하는 platform-neutral `wiki/` 사용자 매뉴얼과 실습 page
- `PROJECT_STATE.md`를 `Development-Ledger.md`로 mirror하는 manifest 기반 Wiki export
- remote env, dry-run 기본, dirty/origin guard와 managed-file prune를 가진 Wiki publisher
- opt-in GitHub Action과 GitLab Self-Managed CI Wiki validation/publication 계약

### 변경

- 등록·완료 HITL dossier 상태를 적용하기 전에 report JSON/Markdown과 recorded outbox hash를 고정한다.
- audit event append를 event ID 기준 idempotent operation으로 강화했다.
- Windows PID 확인은 `os.kill(pid, 0)` 대신 비파괴 Win32 process query를 사용한다.
- 기본 `prep test`에서 optional Docling contract를 분리하고 `prep.ps1 docling`으로 명시 실행한다.
- terminal/cancelled pipeline run은 재실행하지 않고, retryable failure만 같은 run ID에서 재시도한다.
- persisted pipeline result path/SHA-256과 batch manifest SHA-256이 바뀌면 fail-closed한다.
- Library registry 등록과 HTTP 공개 grant를 분리하고 generic actor/admin decision payload를 거부한다.
- API idempotency body/header, semantic default와 typed revision context를 같은 run checkpoint에 고정한다.
- project 등록 audit와 HITL decision actor를 verified bearer principal에 bind하고 role·scope·organization·
  expected revision을 domain mutation 전에 확인한다.
- project create idempotency replay는 stable principal/key project ID의 request/hash/context/creation audit가
  모두 일치할 때만 허용한다.
- education runtime은 generic pipeline grant를 금지하고 request actor/learner/org 대신 verified
  principal을 audit actor로 사용한다. 같은 idempotency key의 동일 성공 명령은 replay한다.
- project milestone bind와 sync는 dossier의 program/version/enrollment/milestone/learner/organization
  context를 매번 다시 확인한다.
- API decision은 `verified_api_principal` authority context를 domain record에 남기고 exact successful
  retry만 revision/audit 증가 없이 재생한다. 같은 key의 다른 actor/resource/payload는 409로 닫힌다.
- queued API는 domain pipeline을 inline 실행하지 않고 prepared checkpoint와 job을 기록한다. generic
  HTTP output의 local path/URI field도 재귀적으로 제거한다.
- 공개 API·workflow·설정·보안·프로젝트 구조가 바뀌면 관련 `wiki/` page를 같은 change set에서
  갱신하고 dual-target parity를 검증하도록 작업 완료 계약을 강화했다.

### 현재 검증

- 단계 종료 전체 수치는 `PROJECT_STATE.md`의 최신 history와 검증 표에 고정한다. Wiki targeted 6/6,
  dual-target parity 1/1, full 136 tests(unit 86/integration 31/contract 19), 10 eval groups, Ruff와
  Pyright 0/0이 통과했다. 직전 API+Worker combined contract 27/27 evidence도 유지한다.
- WP-00.D2는 GitHub main commit `b2c6e48`로 배포됐고 Actions run `30014678127`의 validation이
  통과했다. 최초 Home 전의 Wiki remote는 404이므로 실제 Wiki publication은 아직 완료되지 않았다.
- clean core wheel은 FastAPI 없이 import되고 clean `[api]` wheel은 generated OpenAPI 3.1/17 paths를
  구성하며 local Worker prepared→succeeded를 실행한다. actual-PPTX quickstart는 이전 Alpha checkpoint
  evidence를 유지한다.
- project/education local state recovery, stale artifact maintenance와 single-host local Worker는 검증했지만
  report/outbox producer, database/distributed worker/heartbeat, OIDC/RBAC와 운영 provider는 아직 진행 전이다.
- Wiki source/target export와 local bare-repository publication은 검증했지만 GitHub 최초 Home과 사내
  GitLab runner/credential/live Wiki push는 아직 수행하지 않았다.

### 다음 변경 후보

- G4: immutable upload service와 approved OIDC/RBAC·education assignment source
- distributed worker/heartbeat/dead-letter, poll event와 optional SSE
- report/outbox producer와 database/distributed transaction hardening
- exact on-prem `Qwen3.5-397B-A17B` registration/completion 검증
- 승인된 rubric과 사람 gold label 기반 품질 평가
- full product CLI, evaluation/HITL API, worker, review Web App

## 0.1.0a0 development snapshot - 2026-07-22

### 추가

- project별 단일 dossier, revision/SHA-256 snapshot, 상태 전이와 두 단계 HITL 흐름
- 등록심의 → 수행 → 완료평가를 연결하는 `two-gate-pptx@v1alpha1` reference pipeline
- immutable 교육 프로그램, 학습자 enrollment, milestone별 프로젝트 연결과 과정 완료 HITL
- 제한된 image-only PPTX용 embedded-image renderer와 16-slide hash manifest
- 실제 제공 PPTX용 13개 evidence locator gold fixture와 품질 evaluation
- lexical retrieval, deterministic fake dense/vector contract와 stage leakage 방지
- OpenAI-compatible structured evaluator와 Qwen/GPT-4o/GLM 공통 multimodal capability probe
- durable local notification outbox, idempotency store, filesystem CAS와 dossier schema migration
- P/WP/G Gantt, Gate Control Board와 append-only 작업 이력을 가진 `PROJECT_STATE.md`
- workflow Mermaid, SVG 인포그래픽, M00~M13 Module Control Board와 교육 lifecycle 예제

### 변경

- 첫 사용 인터페이스를 library-first `AXCalib.evaluate/aevaluate`로 유지하고 script/API/Web이 같은
  application service를 재사용하도록 계약을 고정했다.
- 모델 설정은 제품 코드에서 SkillBoss에 의존하지 않고 `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
  `OPENAI_MODEL` OpenAI-compatible 환경변수를 사용한다.
- provider alias capability와 exact deployment checkpoint 검증을 분리했다.
- 교육 과정 전체 완료는 모든 milestone 충족 뒤에도 관리자 알림과 HITL을 거쳐야 한다.
- 문서, schema, module 상태와 다이어그램의 drift를 `prep.ps1 validate`가 검사하도록 강화했다.

### 수정

- `json_object` 요청에 literal `JSON`이 없어 upstream 400이 발생하고 SkillBoss가 HTTP 500으로
  포장하던 문제를 gateway-level JSON/Schema contract 주입으로 복구했다.
- wrapped upstream 오류에서 원문이나 민감한 내용을 노출하지 않고 status/type/code만 남기도록 했다.
- 근거 locator가 없거나 존재하지 않는 model 판정을 성공으로 보지 않고 fail-closed 처리했다.
- notification 기록 실패 시 HITL pending 전이를 완료하지 않도록 유지했다.

### 검증된 범위

- offline test: 79 passed
- evaluation harness: 8 groups passed
- workspace validation: 0 errors, 0 warnings
- Ruff passed, Pyright 0 errors/0 warnings
- Qwen3.5 Plus provider proxy: structured text/vision과 supplied-fixture registration 통과
- GPT-4o provider proxy: structured text/vision과 같은 registration 통과

### 아직 검증되지 않은 범위

- exact on-prem `Qwen3.5-397B-A17B`와 실제 운영 endpoint
- 공식 rubric, 실제 사용자 데이터, 사람 agreement와 calibration 품질
- embedding/Qdrant 운영 검색 품질
- cross-file transaction recovery, 운영 GitLab/email 알림, RBAC, CLI/API/Web
- 자동 인증: 지원하지 않으며 관리자가 항상 최종 결정한다.

## 이전 기준점

- 2026-07-16: G3 Intelligence reference pipeline
- 2026-07-16: supplied PPTX two-gate offline MVP
- 2026-07-15: planning harness와 architecture deck
- 2026-07-13: 제품명, 철학과 개발 specification baseline
