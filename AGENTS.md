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

현재 작업공간은 **기획 baseline 수립 단계**다. 제품 패키지, prep.ps1, 테스트, 평가 데이터셋은 아직 구현되지 않았다. 존재하지 않는 명령이나 테스트를 실행된 것처럼 기록하지 않는다.

## 2. 기준정보 우선순위

충돌이 있을 때 다음 순서로 판단한다.

1. 사용자의 최신 명시적 지시
2. 승인된 WORK_SPEC.md baseline
3. GOAL.md의 현재 Target과 Acceptance Criteria
4. DESIGN.md의 아키텍처·UI 결정
5. AXCalib_Concept_Overview.md의 명명 철학과 장기 개념
6. README.md의 현재 상태 요약
7. 코드, 테스트, evaluation 결과가 보여 주는 실제 동작

문서와 코드가 충돌하면 조용히 한쪽을 맞추지 않는다. 영향 범위를 확인하고, 기준 문서 또는 구현을 함께 갱신한다. 중요한 선택은 향후 docs/adr 아래 Architecture Decision Record로 남긴다.

## 3. 절대 유지할 제품 불변조건

### 3.1 제품 정체성

- 공식 이름은 **AXCalib**, 공식 확장명은 **AX Certification Agent Library**다.
- 배포 패키지명, Python import, CLI 명령은 원칙적으로 모두 axcalib를 사용한다.
- Calib는 Certification + Agent + Library와 Calibration의 이중 의미를 유지한다.
- Core Library는 FastAPI, Next.js, Deep Agents, 특정 LLM 또는 특정 Vector DB에 의존하지 않는다.

### 3.2 두 단계 인증 흐름

- 인증 과제는 **등록심의**와 **완료평가**의 두 평가 Gate를 갖는다.
- 등록심의를 통과하기 전에는 수행 단계로 전이할 수 없다.
- 완료평가는 등록심의 당시의 목표·KPI·범위와 수행 중 누적된 증거를 함께 비교한다.
- 등록심의 결과와 완료평가 결과는 평가와 인증결정을 분리하여 기록한다.

### 3.3 단일 과제 dossier

- 사용자 관점의 단일 기준 파일은 project_id별 AXCalib dossier 파일 하나다.
- 권장 파일명은 AXC-{project_id}.axc.yaml이다.
- 진행내용, 멘토 기록, 산출물, KPI, 두 평가 결과가 같은 dossier의 명시적 섹션에 누적된다.
- 대용량 PPTX·PDF·이미지·코드·로그는 dossier 안에 넣지 않고 content hash와 URI로 참조한다.
- 평가 실행은 현재 파일을 직접 읽는 것이 아니라 revision과 SHA-256으로 고정한 불변 스냅샷을 읽는다.
- 평가 도중 원본 revision이 바뀌면 결과를 자동 병합하지 않고 stale/conflict 상태로 반환한다.
- 과거 revision과 실행기록은 감사용으로 보존하되, 사용자가 편집하는 기준 파일은 하나로 유지한다.

### 3.4 근거와 사람 책임

- 모델은 최종 합격·불합격 또는 인증을 단독 확정하지 않는다.
- 모든 criterion 판단은 원문 위치, 기준 버전, 사례 참조 또는 판단불가 이유를 가져야 한다.
- 근거가 없으면 추론으로 채우지 않고 insufficient_evidence 또는 판단불가로 기록한다.
- 모델의 숨은 chain-of-thought는 저장하거나 요구하지 않는다. 짧은 판단요약, 인용 근거, 구조화된 점검 결과만 보존한다.
- 과거 사례 유사도는 일관성 점검 자료이지 정답이나 자동 판정 근거가 아니다.
- 평가자 수정, 수용, 보류, 반려, 추가자료 요청은 모델 출력과 구분해 감사 이력에 남긴다.

### 3.5 On-prem 및 공급자 독립성

- 기본 모델 프로필은 Qwen3.5 계열의 multimodal 배포를 가리키되 실제 model ID는 설정으로 주입한다.
- 모든 모델 연결은 base_url, api_key_env, model, capability로 표현한다.
- API key 값을 YAML, 로그, fixture, Git, 리포트에 기록하지 않는다.
- OpenAI-compatible HTTP adapter와 curl로 확인 가능한 최소 계약을 우선 제공한다.
- Deep Agents 연동은 optional extra다. deterministic pipeline과 domain state machine을 대체하지 않는다.
- 단일 모델, 다중 모델 독립평가, 합의, adjudication을 동일한 인터페이스로 선택할 수 있어야 한다.

### 3.6 재현성과 보안

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

## 5. 구현 원칙

### 5.1 패키지와 의존성

- Python 3.12 이상을 baseline으로 하고 src/axcalib 레이아웃을 사용한다.
- pyproject.toml을 패키지·도구 설정의 기준으로 사용하고 lockfile을 함께 관리한다.
- core에는 표준 라이브러리와 Pydantic 중심의 작은 의존성만 둔다.
- docling, qdrant, postgres, deepagents, api, web 연동은 optional extra 또는 별도 adapter로 분리한다.
- 외부 시스템은 Protocol 또는 추상 interface 뒤에 둔다.
- schema 변경은 schema_version과 migration을 동반한다.

### 5.2 API 모양

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

### 5.4 검색과 임베딩

- 원문 파일을 바로 embedding하지 않는다. 접근등급 확인, 파싱, 정규화, 비식별, semantic chunking을 먼저 수행한다.
- registration과 completion 사례는 stage metadata로 분리하고 rubric_version, outcome, project_type 등 필터를 적용한다.
- dense similarity 하나만 보고 유사 사례를 확정하지 않는다. lexical/dense 후보 검색, rerank, case-level aggregation을 분리한다.
- 결과에는 similarity score뿐 아니라 공통점, 차이점, 적용 한계, corpus snapshot을 기록한다.
- embedding model 또는 chunking version이 바뀌면 새 index namespace를 만들고 evaluation 후 승격한다.

## 6. 목표 디렉터리 계약

아래 구조는 구현 Target이다. 아직 없는 경로를 현재 구현으로 간주하지 않는다.

~~~text
AX_Calib/
  AGENTS.md
  GOAL.md
  DESIGN.md
  README.md
  WORK_SPEC.md
  AXCalib_Concept_Overview.md
  pyproject.toml
  prep.ps1
  config/
  docs/
    adr/
    schemas/
    rubrics/
    evaluation/
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
    cli/
    api/
  fixtures/synthetic/
  tests/
    unit/
    integration/
    contract/
  evals/
  output/
~~~

## 7. 명령 계약

### 7.1 작업 하네스

다음 명령은 WP-00에서 구현할 계약이다. prep.ps1이 생기기 전에는 실행 가능하다고 표시하지 않는다.

~~~powershell
.\prep.ps1 status
.\prep.ps1 next
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 eval
~~~

- status: 파일을 바꾸지 않고 baseline, Gate, 차단요인, 다음 작업을 표시한다.
- next: 현재 Gate에서 가장 작은 실행 가능한 작업과 전제를 표시한다.
- validate: 문서, schema, 링크, 설정, secret, dossier 상태전이를 읽기 전용으로 검사한다.
- test: offline 단위·통합·계약 테스트를 실행한다.
- eval: 고정 fixture/dataset으로 parser, retrieval, 평가, 모델 편차 지표를 생성한다.

status와 validate는 항상 read-only다. 외부 모델을 쓰는 live evaluation은 별도 플래그와 명시적 동의가 필요하다.

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
- 비밀정보 redaction
- retrieval metadata filter와 corpus version
- 단일/다중 모델 structured output validation
- batch 일부 실패·재시도·resume
- 동일 fixture와 동일 mock 설정의 재현성

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
- 라이선스 또는 LG 브랜드 자산의 공식 사용 선언

불명확하지만 안전한 synthetic/offline 작업으로 진전할 수 있으면 그 범위에서 계속하고, 필요한 결정은 GOAL.md의 Open Decisions에 남긴다.
