# AXCalib 변경 이력

이 문서는 사용자와 개발자가 제품의 큰 변화를 빠르게 확인하기 위한 기록이다. 세부 작업 순서와
검증 이력은 `PROJECT_STATE.md`, 설계 결정은 `DECISIONS.md`와 `docs/adr/`를 기준으로 한다.

## Unreleased

### 추가

- project create/update의 dossier와 audit를 묶는 append-only hash-chain transaction journal
- `project.transaction.reconcile@v1alpha1` library pipeline과 thin recovery script
- prepare, dossier, audit 직후 synthetic crash 3종과 반복 reconciliation evaluation

### 변경

- 등록·완료 HITL dossier 상태를 적용하기 전에 report JSON/Markdown과 recorded outbox hash를 고정한다.
- audit event append를 event ID 기준 idempotent operation으로 강화했다.

### 현재 검증

- offline tests 88 passed, evaluation 9 groups, validation 0 errors/0 warnings, Ruff/Pyright passed
- project dossier/audit recovery는 검증됐지만 education transaction, report/outbox producer와 stale-lock
  cleanup은 아직 진행 중이다.

### 다음 변경 후보

- WP-01.R1.2: education, report/outbox producer, stale lock과 orphan journal recovery
- exact on-prem `Qwen3.5-397B-A17B` registration/completion 검증
- 승인된 rubric과 사람 gold label 기반 품질 평가
- Typer CLI parity 이후 API, worker, review Web App

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
