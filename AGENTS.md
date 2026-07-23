# AXCalib 작업 하네스 계약

이 파일은 이 작업공간에서 사람과 코딩 Agent가 따라야 할 실행 규칙이다. 제품 요구사항은 WORK_SPEC.md, 목표와 단계별 수용기준은 GOAL.md, 기술·UX 설계는 DESIGN.md를 기준으로 한다.

## 1. 미션과 작업 범위

AXCalib는 **AX Certification Agent Library**다. 다양한 과제 증거를 구조화하고, 등록심의와 완료평가를 근거 중심으로 지원하며, 모델·평가자 간 편차를 보정하고, 향후 AX Level 판정과 인증으로 확장할 수 있는 라이브러리를 만든다.

초기 제품 순서는 다음과 같다.

1. Python Core Library
2. CLI와 Evaluation Harness
3. API와 비동기·배치 Worker
4. Human Review Web App
5. 기존 인증시스템 연동

현재 작업공간은 **G3 Intelligence reference baseline과 evidence Q1 검증 완료, Qwen3.5 Plus/GPT-4o
provider-proxy registration 검증 완료, Library/CLI/batch, fail-closed runtime API, WP-06.I2a/I2b/I2c
principal-bound resource API/read-replay, WP-06.I3 durable local 202 Worker Alpha와 WP-06.I4.1
provider-neutral OIDC/JWKS local signed reference 완료 단계**다.
dossier/snapshot, hash-bound review policy, 제한된 PPTX와 optional Docling manifest, synthetic
lexical retrieval, deterministic/structured model evaluator, report, recording notification, 두 HITL과
`two-gate-pptx@v1alpha1` working script가 존재한다. SkillBoss JSON-mode HTTP 500 원인은 복구했고
project/education append-only transaction journal, idempotent reconcile, stale artifact maintenance,
typed local executor/JSONL batch/Alpha CLI, authenticated FastAPI runtime과 principal-bound project
register/두 HITL command, education self enrollment/role별 milestone/completion command도 local reference로
검증했다. URI-redacted owner/admin project GET과 두 HITL decision의 principal-bound local semantic replay도
검증했다. exact queued grant의 202, typed/hash-bound local job, oldest-available lease/reclaim,
retryable-only bounded retry, terminal replay와 one-job Worker도 같은 executor로 검증했다. exact on-prem `Qwen3.5-397B-A17B`, full rubric,
report/outbox producer transaction, embedding/Vector DB, multi-model 품질, durable 운영 알림, full CLI,
full evaluation API, approved remote issuer/JWKS rotation/revocation·실제 교육 배정 원장, immutable
upload, distributed broker/worker heartbeat와 Web은 아직 완료되지 않았다. 이
reference slice를 제품 MVP 전체나 모델·retrieval·운영 API 품질 검증 완료로 기록하지 않는다.

## 2. 기준정보 우선순위

충돌이 있을 때 다음 순서로 판단한다.

1. 사용자의 최신 명시적 지시
2. 승인된 WORK_SPEC.md baseline
3. GOAL.md의 현재 Target과 Acceptance Criteria
4. PROJECT_STATE.md의 현재 P/WP/G, Active Slice와 append-only 작업 이력
5. DESIGN.md의 아키텍처·UI 결정
6. AXCalib_Concept_Overview.md의 명명 철학과 장기 개념
7. README.md의 현재 상태 요약
8. 코드, 테스트, evaluation 결과가 보여 주는 실제 동작

문서와 코드가 충돌하면 조용히 한쪽을 맞추지 않는다. 영향 범위를 확인하고, 기준 문서 또는 구현을 함께 갱신한다. 중요한 선택은 향후 docs/adr 아래 Architecture Decision Record로 남긴다.

## 3. 절대 유지할 제품 불변조건

### 3.1 제품 정체성

- 공식 이름은 **AXCalib**, 공식 확장명은 **AX Certification Agent Library**다.
- 배포 패키지명, Python import, CLI 명령은 원칙적으로 모두 axcalib를 사용한다.
- Calib는 Certification + Agent + Library와 Calibration의 이중 의미를 유지한다.
- Excalibur의 “권한 있는 사람만 칼을 뽑는다”는 이미지는 제품 철학의 기억 장치다. 공식 어원,
  제품명 변경 또는 자동 자격판정 알고리즘으로 설명하지 않는다.
- 제품 설명은 “근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다”를
  기준으로 하며, Agent가 아니라 승인된 사람이 최종결정한다는 경계를 모든 UI/문서에 표시한다.
- Core Library는 FastAPI, Next.js, Deep Agents, 특정 LLM 또는 특정 Vector DB에 의존하지 않는다.

### 3.2 두 단계 인증 흐름

- 인증 과제는 **등록심의**와 **완료평가**의 두 평가 Gate를 갖는다.
- 등록심의를 통과하기 전에는 수행 단계로 전이할 수 없다.
- 완료평가는 등록심의 당시의 목표·KPI·범위와 수행 중 누적된 증거를 함께 비교한다.
- 등록심의 결과와 완료평가 결과는 평가와 인증결정을 분리하여 기록한다.
- Agent는 등록과 완료에서 통과·미통과 **제안** 및 리포트만 생성한다.
- 등록 승인·반려와 완료 수용·미수용은 관리자 HITL 이후에만 확정한다.
- 멘토 배정은 선택이지만 배정된 경우 완료평가 제출 등록 전에 mentor 승인이 필요하다.

### 3.3 단일 과제 dossier

- 사용자 관점의 단일 기준 파일은 project_id별 AXCalib dossier 파일 하나다.
- 권장 파일명은 AXC-{project_id}.axc.yaml이다.
- 진행내용, 멘토 기록, 산출물, KPI, 두 평가 결과가 같은 dossier의 명시적 섹션에 누적된다.
- 대용량 PPTX·PDF·이미지·코드·로그는 dossier 안에 넣지 않고 content hash와 URI로 참조한다.
- 평가 실행은 현재 파일을 직접 읽는 것이 아니라 revision과 SHA-256으로 고정한 불변 스냅샷을 읽는다.
- 평가 도중 원본 revision이 바뀌면 결과를 자동 병합하지 않고 stale/conflict 상태로 반환한다.
- 과거 revision과 실행기록은 감사용으로 보존하되, 사용자가 편집하는 기준 파일은 하나로 유지한다.

### 3.3.1 교육 프로그램과 과제 인증의 경계

- 현재 AXCalib가 직접 심의·평가하는 인증 대상은 제출된 과제 project dossier다.
- 교육과정 기획자는 immutable `program_id@version`에 level, milestone, prerequisite, typed
  requirement와 allowlisted pipeline을 선언한다.
- 학습자 가입 시 해당 program version과 SHA-256을 고정한 enrollment를 만들고 단계별 목표를
  생성한다. 이미 가입한 enrollment는 새 program version으로 조용히 이동하지 않는다.
- project milestone은 같은 program version, enrollment, milestone, learner context를 가진 dossier만
  연결한다. 완료 조건은 caller가 전달한 문자열이 아니라 저장된 dossier 상태에서 계산한다.
- project `completion_accepted`는 교육 마일스톤의 근거일 뿐 과정 전체 인증을 자동 확정하지 않는다.
  필수 milestone 충족 뒤에도 관리자 completion HITL과 승인요청 알림을 거쳐야 한다.
- 과정 기획자의 유연성은 allowlisted milestone/condition/pipeline ID와 version 안에서 제공한다.
  TOML/YAML의 임의 Python import, expression 또는 사람 Gate 우회는 허용하지 않는다.

### 3.4 근거와 사람 책임

- 모델은 최종 합격·불합격 또는 인증을 단독 확정하지 않는다.
- 모든 criterion 판단은 원문 위치, 기준 버전, 사례 참조 또는 판단불가 이유를 가져야 한다.
- 근거가 없으면 추론으로 채우지 않고 insufficient_evidence 또는 판단불가로 기록한다.
- 모델의 숨은 chain-of-thought는 저장하거나 요구하지 않는다. 짧은 판단요약, 인용 근거, 구조화된 점검 결과만 보존한다.
- 과거 사례 유사도는 일관성 점검 자료이지 정답이나 자동 판정 근거가 아니다.
- 평가자 수정, 수용, 보류, 반려, 추가자료 요청은 모델 출력과 구분해 감사 이력에 남긴다.
- 관리자 HITL은 `docs/rubrics/hitl_review_checklist.md`로 hallucination, unsupported claim,
  편향, RAG leakage, 가중치 계산을 확인한다.
- 관리자 승인요청 알림이 기록 또는 전달되지 않으면 HITL pending 전이를 완료하지 않는다.

### 3.5 승인요청 알림

- 등록심의와 완료평가의 HITL 진입에는 각각 notification event가 필수다.
- 운영 adapter 후보는 GitLab Merge Request와 email이며 `NotificationPort` 뒤에 둔다.
- offline test는 외부 메시지를 보내지 않는 recording adapter만 사용한다.
- 알림에는 secret이나 원문 전체를 넣지 않고 project_id, stage, revision, report reference,
  요청 역할을 기록한다.
- 운영 구현은 idempotency, outbox, retry, delivery status와 감사 이력을 가져야 한다.

### 3.6 On-prem 및 공급자 독립성

- 기본 모델 프로필은 Qwen3.5 계열의 multimodal 배포를 가리키되 실제 model ID는 설정으로 주입한다.
- 모든 모델 연결은 base_url, api_key_env, model, capability로 표현한다.
- API key 값을 YAML, 로그, fixture, Git, 리포트에 기록하지 않는다.
- OpenAI-compatible HTTP adapter와 curl로 확인 가능한 최소 계약을 우선 제공한다.
- Deep Agents 연동은 optional extra다. deterministic pipeline과 domain state machine을 대체하지 않는다.
- 단일 모델, 다중 모델 독립평가, 합의, adjudication을 동일한 인터페이스로 선택할 수 있어야 한다.

### 3.7 재현성과 보안

- dossier schema, rubric, criterion, prompt template, parser, embedding model, corpus snapshot, evaluator model, code version을 실행기록에 연결한다.
- 실제 사내 데이터와 개인정보는 승인 전 fixtures/synthetic 밖에 두지 않는다.
- 외부 또는 승인되지 않은 endpoint로 원문을 보내는 live test는 기본 test 명령에 포함하지 않는다.
- 로그와 리포트에는 비밀정보·원문 전체·개인정보 대신 식별자와 허용된 발췌만 남긴다.

## 4. 작업 시작 절차

변경 전 다음을 수행한다.

1. README.md, WORK_SPEC.md, GOAL.md, DESIGN.md에서 현재 단계와 대상 WP를 확인한다.
2. git status --short -- . 로 이 폴더 안의 사용자 변경을 확인한다.
3. 구현하려는 요구사항과 수용기준을 한 문장으로 고정한다.
4. 실제 데이터, 외부 모델 호출, 시스템 설치, 배포, Git 초기화가 필요한지 확인한다.
5. 가장 작은 end-to-end slice와 검증 명령을 정한다.

사용자가 만든 변경은 보존한다. 이 폴더 밖의 파일을 수정하지 않는다. 관련 없는 변경을 정리하거나 되돌리지 않는다.

### 4.1 단일 작업 진행 원장

- `PROJECT_STATE.md`를 일정, 현재 P(Phase), WP(Work Package), G(Gate), Active Slice, 검증,
  특이사항과 작업 이력을 관리하는 단일 Project Execution Ledger로 사용한다.
- 작업 시작 전 원장의 Active Slice, 선행조건과 Exit Evidence를 현재 요청에 맞게 갱신한다.
- 작업 중 blocker, 실패, 범위변경과 중요한 판단을 원장의 특이사항에 기록한다.
- 단계 또는 slice가 끝나면 변경 파일, validation/test/eval 결과, 미검증 범위, 다음 작업과 Gate
  영향을 같은 change set에서 기록한다.
- 현재 상태 절은 갱신할 수 있지만 작업 이력 절은 append-only다. 과거 기록을 조용히 수정하지
  않고 정정 entry를 추가한다.
- 일정의 Owner·공수·목표일이 확정되지 않았으면 가짜 납기를 만들지 않고 dependency-only Gantt와
  `TBD`를 사용한다. calendar baseline 변경은 이유와 영향받는 WP/Gate를 이력에 남긴다.
- 상세 제품 요구·설계·결정·위험은 기존 기준 문서에 유지하고 원장에서는 링크와 실행 영향만
  기록한다.
- `prep.ps1 validate`가 frontmatter, P0~P9/G0~G8, Active Slice, Gantt, 마지막 history ID와
  `updated_at` 일치를 검사한다.

### 4.2 GitHub/GitLab Wiki 문서 전달

- 사용자용 Wiki의 단일 원본은 메인 저장소의 `wiki/`다. GitHub Wiki와 사내 GitLab Wiki는 별도
  Git 저장소지만 배포 target으로만 취급하고 웹 화면에서 따로 편집하지 않는다.
- Library 공개 API, workflow, config/on-prem, API/Worker/Web, 보안/HITL, 프로젝트 구조가 바뀌면
  관련 `wiki/*.md`를 같은 change set에서 갱신한다.
- 개발과정·진행이력은 `PROJECT_STATE.md`를 기준으로 하며 Wiki export가
  `Development-Ledger.md`로 자동 mirror한다. 별도의 수동 이력 사본을 기준으로 만들지 않는다.
- `wiki/wiki-manifest.json`에 page, mirror, asset과 sidebar를 allowlist한다. 임의 파일 복사나
  플랫폼별 서로 다른 본문을 만들지 않는다.
- GitHub `_Sidebar.md`와 GitLab `_sidebar.md` 차이는 target export에서만 변환한다.
  platform-neutral 상대 link와 committed asset만 사용한다.
- `prep.ps1 validate`, `python scripts/wiki/sync_wiki.py validate`와 dependency-free dual-target parity
  contract가 통과해야 문서 checkpoint를 완료로 기록한다.
- Wiki remote URL, token, SSH private key와 사내 hostname은 commit하지 않는다. remote는 승인된
  환경변수/CI secret으로만 주입하고 publish는 명시적 `--push` 없이는 전송하지 않는다.
- 과거 deployed manifest에 AXCalib 관리 파일로 기록된 항목만 prune한다. 다른 팀의 Wiki page를
  삭제하거나 강제 push하지 않는다.
- GitHub 최초 Home, GitLab project Wiki/runner/credential과 enable variable은 플랫폼 Owner 승인 뒤
  opt-in한다. local export 성공을 실제 Wiki publication 성공으로 기록하지 않는다.
- 상세 운영계약은 `docs/operations/wiki-publication.md`와 ADR-027을 따른다.

## 5. 구현 원칙

### 5.1 패키지와 의존성

- Python 3.12 이상을 baseline으로 하고 src/axcalib 레이아웃을 사용한다.
- pyproject.toml을 패키지·도구 설정의 기준으로 사용하고 lockfile을 함께 관리한다.
- core에는 표준 라이브러리와 Pydantic 중심의 작은 의존성만 둔다.
- docling, qdrant, postgres, deepagents, api, web 연동은 optional extra 또는 별도 adapter로 분리한다.
- 외부 시스템은 Protocol 또는 추상 interface 뒤에 둔다.
- schema 변경은 schema_version과 migration을 동반한다.

### 5.2 API 모양

- 첫 공개 진입점은 `AXCalib().evaluate(...)`와 같은 의미의 `aevaluate(...)`로 작게 유지한다.
  세부 pipeline/port는 고급 API이며 첫 사용 예제에 한꺼번에 노출하지 않는다.
- 기본 `config/axcalib.toml`은 offline-safe 최소 설정만 가진다. 전문 사용자는
  `config/axcalib.expert.example.toml`을 복사해 allowlisted profile을 구성한다.
- 설정 우선순위는 코드 소유 불변조건, 안전 기본값, TOML profile, 환경변수, allowlisted request
  option, policy guard 순이다. unknown key는 조용히 무시하지 않는다.
- 관리자 HITL, 승인요청 알림, 사람 최종결정, stale/revision guard와 mentor guard는 TOML 또는
  JSON으로 끄는 설정을 제공하지 않는다.
- HTTP 계약은 versioned OpenAPI 3.1 JSON과 JSON Schema Draft 2020-12를 기준으로 하고,
  요청별 파라미터는 `additionalProperties: false`인 typed option만 허용한다.
- 동기 API와 비동기 API의 의미가 같아야 한다. 비동기 함수는 a 접두어를 사용한다. 예: evaluate / aevaluate.
- library API가 기준이며 CLI, API, worker는 같은 application service를 호출한다.
- 공개 함수와 모델은 type annotation과 간결한 docstring을 갖는다.
- structured output은 Pydantic으로 검증하고 검증 실패를 성공 결과로 취급하지 않는다.
- 파일 갱신은 임시 파일 쓰기, fsync 가능 범위 확인, atomic replace 순으로 처리한다.
- batch 항목은 idempotency key와 개별 상태를 가져야 하며 일부 실패를 숨기지 않는다.

### 5.3 상태 전이

- 허용된 상태 전이는 domain state machine 한 곳에 정의한다.
- 평가 요청 시 revision을 먼저 freeze한 뒤 실행한다.
- 동일 idempotency key의 재시도는 새 평가를 중복 생성하지 않는다.
- 실패, 취소, stale 결과는 성공 상태로 승격하지 않는다.
- 사람 승인 없이 registration_approved, completion_accepted, certified로 전이하지 않는다.
- registration/completion 평가초안은 반드시 `*_hitl_pending`을 거치며 알림 실패 시 전이를
  fail closed한다.
- registration_rejected는 관리자 결정 뒤 해당 수행 프로세스를 종료한다.
- mentor가 배정됐다면 project owner가 mentor 승인 없이 completion_registered로 전이할 수 없다.

### 5.4 검색과 임베딩

- 원문 파일을 바로 embedding하지 않는다. 접근등급 확인, 파싱, 정규화, 비식별, semantic chunking을 먼저 수행한다.
- registration과 completion 사례는 stage metadata로 분리하고 rubric_version, outcome, project_type 등 필터를 적용한다.
- dense similarity 하나만 보고 유사 사례를 확정하지 않는다. lexical/dense 후보 검색, rerank, case-level aggregation을 분리한다.
- 결과에는 similarity score뿐 아니라 공통점, 차이점, 적용 한계, corpus snapshot을 기록한다.
- embedding model 또는 chunking version이 바뀌면 새 index namespace를 만들고 evaluation 후 승격한다.
- registration과 completion retrieval adapter와 corpus는 독립적으로 설정한다.
- similarity portion은 stage/rubric별 설정으로 노출하되 raw similarity를 직접 합격점수로
  사용하지 않는다.
- portion이 0보다 큰데 adapter/corpus가 없으면 가중치를 조용히 재분배하지 않는다.
- offline baseline은 lexical adapter와 portion 0.0이며 실제 retrieval 품질을 주장하지 않는다.

### 5.5 요소 모듈, 국소 Pipeline, 전체 Workflow

- 구현 순서는 domain schema/port → 요소 모듈 → 국소 pipeline class → 실행 가능한 synthetic
  Python script → test/eval → CLI/API/worker 노출 순으로 한다.
- 요소 모듈은 dossier, ingest, retrieval, evaluation처럼 한 capability를 제공하며 전체 업무
  순서를 결정하지 않는다.
- 국소 pipeline은 하나의 독립적인 업무 목적, typed input/output, 명시적 status와 audit
  metadata를 갖는 application service다.
- 전체 workflow는 versioned local pipeline, branch, human wait/resume, checkpoint를 연결하되
  domain state machine과 관리자 HITL 불변조건을 대체하거나 우회하지 않는다.
- working script는 argument/file 입출력과 library 호출만 담당한다. domain 판정, 상태전이,
  retry 규칙을 script에 복사하지 않는다.
- CLI, API, worker는 script를 subprocess로 호출하지 않고 같은 library pipeline/workflow를
  직접 호출한다. Web App은 API가 제공하는 상태와 allowed command를 소비한다.
- `run`/`arun` 또는 동등한 sync/async API는 같은 input/output/error 의미를 가져야 한다.
- pipeline result는 succeeded, waiting_human, blocked, stale, retryable/terminal failure,
  cancelled를 성공과 구분한다.
- workflow/pipeline은 allowlisted id와 version으로 registry에 등록한다. MVP에서 config로 임의
  Python import path, expression 또는 arbitrary graph를 실행하지 않는다.
- 상세 계약은 `docs/architecture/composable-pipeline-plan.md`와 ADR-013을 따른다.
- module/pipeline/state/dependency가 바뀌면 `workflow-blueprint.md`, `module-delivery-plan.md`,
  SVG 인포그래픽과 `PROJECT_STATE.md`를 같은 change set에서 갱신한다.
- Mermaid는 정확한 구조 기준, SVG는 이해관계자용 요약이다. 구현되지 않은 node를 완료색으로
  표시하지 않고 module 상태는 Exit Evidence가 있을 때만 승격한다.

## 6. 목표 디렉터리 계약

아래 구조는 구현 Target이다. 아직 없는 경로를 현재 구현으로 간주하지 않는다.

~~~text
AXCalib/
  AGENTS.md
  GOAL.md
  DESIGN.md
  README.md
  WORK_SPEC.md
  AXCalib_Concept_Overview.md
  PROJECT_STATE.md
  DECISIONS.md
  RISK_REGISTER.md
  pyproject.toml
  uv.lock
  prep.ps1
  config/
  harness/
  docs/
    architecture/
      diagrams/
    adr/
    operations/
    schemas/
    rubrics/
    evaluation/
    workflows/
  src/axcalib/
    core/
    schemas/
    dossier/
    ingest/
    retrieval/
    evaluation/
    calibration/
    models/
    workflows/
    reports/
    audit/
    notifications/
    programs/
    pipelines/
    runtime/
    cli/
    api/
  scripts/
    pipelines/
    wiki/
  apps/
    api/
    worker/
    web/
  fixtures/synthetic/
  examples/
  tests/
    unit/
    integration/
    contract/
  evals/
  wiki/
  output/
~~~

## 7. 명령 계약

### 7.1 작업 하네스

다음 명령은 WP-00에서 구현되어 있다. 새 명령이나 live 동작은 실제 구현·검증 전에는
실행 가능하다고 표시하지 않는다.

~~~powershell
.\prep.ps1 status
.\prep.ps1 next
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 test unit
.\prep.ps1 test integration
.\prep.ps1 test contract
.\prep.ps1 eval
.\prep.ps1 docling
~~~

- status: 파일을 바꾸지 않고 baseline, Gate, 차단요인, 다음 작업을 표시한다.
- next: 현재 Gate에서 가장 작은 실행 가능한 작업과 전제를 표시한다.
- validate: 문서, schema, 링크, 설정, secret, dossier 상태전이를 읽기 전용으로 검사한다.
- test: offline 단위·통합·계약 테스트를 격리된 저메모리 process group으로 순차 실행한다. 중단 복구나
  진단에는 `unit|integration|contract` group 하나만 지정한다.
- eval: 고정 fixture/dataset으로 parser, retrieval, 평가, 모델 편차 지표를 생성한다.
- docling: optional Docling PPTX contract를 별도 프로세스로 실행한다. 저메모리 환경의 기본 test에는
  포함하지 않는다.

Wiki 원본과 두 target export는 다음 명령으로 별도 확인한다. `publish`는 기본 dry-run이며 실제
commit/push에는 명시적 `--push`와 승인된 remote 환경변수가 필요하다.

~~~powershell
uv run --no-sync python scripts/wiki/sync_wiki.py validate
uv run --no-sync python scripts/wiki/sync_wiki.py export --target github --output output/wiki-preview/github
uv run --no-sync python scripts/wiki/sync_wiki.py export --target gitlab --output output/wiki-preview/gitlab
uv run --no-sync python tests/wiki_ci_contract.py
~~~

status와 validate는 항상 read-only다. 외부 모델을 쓰는 live evaluation은 별도 플래그와 명시적 동의가 필요하다.
기본 test는 lightweight parser/sidecar 경로를 검증하고 Docling contract는 `prep.ps1 docling`으로 분리한다.

### 7.2 제품 CLI

목표 CLI는 다음 범주를 제공한다.

~~~text
axcalib dossier init|show|validate|update|freeze
axcalib submit registration|completion
axcalib evaluate registration|completion
axcalib cases ingest|index|search
axcalib batch run|status|resume
axcalib report render
axcalib verify run
~~~

CLI와 API는 동일한 schema 및 application service를 사용해야 한다.

## 8. 테스트와 Evaluation 규칙

### 8.1 테스트 계층

- unit: 네트워크·GPU·DB 없이 schema, 상태전이, 계산, atomic update를 검증한다.
- integration: 임시 파일, mock model server, ephemeral vector store로 파이프라인을 검증한다.
- contract: OpenAI-compatible endpoint, model capability, Docling, Qdrant adapter 계약을 검증한다.
- live: 승인된 endpoint와 비식별 데이터만 사용하며 기본 test에서 제외한다.
- eval: 고정 dataset으로 품질과 편차를 측정하며 단순 pass/fail 테스트와 분리한다.

### 8.2 최소 회귀 항목

- dossier round-trip과 JSON Schema validation
- 금지된 상태 전이 거부
- revision freeze와 stale write 거부
- criterion별 evidence locator 보존
- 등록심의 결과와 완료평가 입력 연결
- Agent가 관리자 전용 최종 상태로 직접 전이하지 못함
- 두 HITL Gate의 승인요청 notification event
- mentor 배정 시 completion submission 승인 guard
- 비밀정보 redaction
- retrieval metadata filter와 corpus version
- registration/completion stage leakage 방지와 similarity portion validation
- 단일/다중 모델 structured output validation
- batch 일부 실패·재시도·resume
- 동일 fixture와 동일 mock 설정의 재현성
- architecture 문서의 local link, Mermaid 필수 view, SVG XML/title/desc와 M00~M13 control board
- 코드/상태 변경 시 workflow 구조도와 module 상태의 drift 방지
- portable Wiki 필수 page/link/asset, Development Ledger mirror와 GitHub/GitLab export parity

### 8.3 품질 지표

- parser required-field coverage
- evidence traceability와 unsupported-claim rate
- retrieval Recall@k, nDCG@k, rerank precision
- 사람 평가와의 agreement
- 모델별 판정 분포와 disagreement
- confidence calibration, 경계 사례 오류
- 위험한 자동 통과/탈락 제안
- 처리시간, GPU/API 비용, 재시도율

## 9. 완료 정의

작업을 완료했다고 말하려면 다음을 모두 제시한다.

1. 변경된 요구사항 또는 WP
2. 변경 파일
3. 실행한 validation/test/eval 명령
4. 핵심 결과와 실패 여부
5. 실행하지 못한 검증과 이유
6. 새로 생긴 결정, 위험, 후속 작업
7. 구조·상태·dependency를 바꿨다면 갱신한 diagram과 module control 항목
8. `PROJECT_STATE.md`에 갱신한 Active Slice, Gate, 검증 결과, 특이사항과 append-only 이력 ID
9. 사용자 인터페이스·운영법·프로젝트 구조가 바뀌었다면 갱신한 `wiki/` page와 dual-target 검증 결과

문서만 작성한 단계에서는 제품 기능이 완료됐다고 표현하지 않는다. 테스트가 없으면 없다고 말하고, live model을 호출하지 않았으면 모델 품질이 검증됐다고 말하지 않는다.

## 10. 반드시 멈추고 확인할 조건

다음 작업은 사용자 또는 책임자의 명시적 확인 없이 진행하지 않는다.

- 실제 임직원·수강생·과제 데이터 반입
- 외부 모델 endpoint로 원문 또는 개인정보 전송
- 인증 기준, 합격선, AX Level 정책의 확정
- 사람 검토 없는 자동 인증 활성화
- 운영 DB/API 변경, 배포, 계정·권한 생성
- 유료 모델 대량 호출 또는 대규모 embedding
- Git 초기화, 원격 저장소 생성, commit, push
- GitHub/GitLab Wiki 최초 page 생성, remote Wiki push, CI variable·deploy key·runner 설정
- 라이선스 또는 LG 브랜드 자산의 공식 사용 선언

불명확하지만 안전한 synthetic/offline 작업으로 진전할 수 있으면 그 범위에서 계속하고, 필요한 결정은 GOAL.md의 Open Decisions에 남긴다.
