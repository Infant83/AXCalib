# AXCalib

**AX Certification Agent Library**

AXCalib는 하나의 과제 dossier에 등록심의, 수행기록, 멘토링, 산출물, KPI, 완료평가를
연결하고, 평가기준·과거 유사사례·다중 모델 분석을 근거로 사람의 AX 인증 판단을
지원하는 Library다.

> **근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다.**
>
> Evidence qualifies. Calibration aligns. Authorized humans certify.

## 현재 상태

현재는 제공된 image-only PPTX를 대상으로 **G3 Intelligence reference baseline 검증 완료**,
**WP-02.Q1 actual-PPT evidence-quality baseline 검증 완료**, **WP-05.Q1 Qwen capability proxy 검증**,
**WP-05.Q2 structured-output provider 호환성 복구** 및 **교육 프로그램 composition offline
reference**, **WP-01.R1.2 Library MVP/Alpha local 검증 완료**, **WP-06.I1 runtime API와 WP-06.I2a
principal-bound project API local Alpha** 단계다. Python Library, local pipeline,
Alpha CLI와 working script가 dossier·snapshot·평가초안·HITL
결정·audit 결과를 만들며, hash-bound 심사정책·Docling manifest·synthetic retrieval baseline·
OpenAI-compatible structured evaluator가 같은 흐름에 연결된다. 이것은 T1 전체나 운영 제품,
공식 평가품질 완료를 뜻하지 않는다.

- Python 3.12 `src/axcalib` package와 `AXCalib` facade가 실행된다.
- `prep.ps1 status|next|validate|test|eval|docling`이 실행 가능하다.
- 두 Gate의 관리자 승인·필수 알림·선택적 멘토 흐름을 persisted dossier와 연결했다.
- immutable 교육 프로그램, 가입별 목표 생성, prerequisite, 수업 확인·점수·과제 인증
  마일스톤과 과정 완료 관리자 Gate를 연결했다.
- 교육 project milestone은 program version·enrollment·milestone·learner가 모두 일치하는 dossier의
  저장된 `completion_accepted` 상태만 근거로 사용한다.
- allowlisted `two-gate-pptx@v1alpha1` pipeline은 sync/async로 같은 결과 의미를 제공한다.
- `dossier.initialize/update/freeze`와 `education-program-runtime@v1alpha1`도 allowlisted typed
  pipeline으로 실행된다.
- `PipelineContext`와 local executor가 request/context identity, run lease, result hash, sync/async,
  cooperative cancel과 terminal/retryable replay를 checkpoint한다.
- project/education transaction reconcile과 report-only 기본 workspace maintenance가 같은 registry에
  등록되며, stale lock/orphan은 삭제 대신 quarantine하고 committed journal만 archive한다.
- strict JSONL batch는 manifest hash와 item별 checkpoint/부분실패를 보존하며 기본 CLI concurrency는
  1로 안전하게 시작한다.
- optional `cli` extra의 Typer/Rich CLI가 pipeline list/run, run status/cancel, batch와 maintenance를
  Library 구현에 직접 위임한다.
- optional `api` extra의 FastAPI factory가 explicit delivery grant, injected bearer verifier,
  owner/scope guard 아래 같은 registry와 checkpoint를 catalog/run/status/cancel route로 노출한다.
  기본 verifier와 pipeline grant는 모두 fail closed다.
- project 등록 API는 verified owner/admin의 subject와 organization을 dossier/audit에 bind하고 local
  path 대신 opaque staged artifact ID·size·SHA-256을 받는다. 등록·완료 HITL endpoint는 관리자 role,
  scope, organization과 expected revision을 확인한 뒤 principal subject만 decision actor로 기록한다.
- 전체 workflow 구조도와 M00~M13 module control board가 architecture 문서로 관리된다.
- 최소 Library facade, default/expert TOML, runtime schema와 OpenAPI 3.1 계약이 문서화됐다.
- 권한 모델 일러스트, 정확한 SVG와 6컷 튜토리얼이 사용자 매뉴얼로 연결된다.
- 두 Gate, module map, RAG 도입단계와 다음 slice를 정리한 12-slide PowerPoint가 있다.
- synthetic fixture와 lexical retrieval만 사용한다.
- YAML dossier, snapshot, 제한된 PPTX ingest, deterministic evaluator와 JSON/Markdown report를
  구현했다.
- dossier schema는 `v1alpha2`이며 기존 `v1alpha1`은 allowlisted migration으로 읽는다.
- version/hash가 고정되는 review policy registry, criterion별 reviewer adjustment 감사계약을
  구현했다. 조직·사업·인증등급 context는 자동 점수나 prompt에 사용하지 않는다.
- Docling optional adapter를 실제 제공 PPTX에 실행해 16쪽·추출 text 0인 image-only 결과를
  명시적으로 기록했다.
- 제한형 local renderer가 같은 PPTX의 16/16 slide를 13개 visual·3개 blank PNG로 고정하고,
  source/image SHA-256과 재현 가능한 render manifest를 만든다. 합성 slide는 fail-closed다.
- hash-bound gold fixture와 품질 eval에서 reviewed locator 13/13, reference field 12/12,
  criterion traceability 13/13, unsupported claim 0건을 검증했다. 의미평가 정확도 주장은 아니다.
- 작은 synthetic lexical dataset에서 stage leakage 0, Recall@5/nDCG@5 회귀를 실행한다. 이는
  embedding/Vector DB 또는 실제 retrieval 품질 주장이 아니다.
- OpenAI Responses와 on-prem Chat Completions dialect를 지원하는 strict structured-output
  evaluator를 구현했고, 사용자 승인 범위의 비식별 fixture로 live 등록심의 1회를 확인했다.
- canonical `OPENAI_*`만 사용하는 Qwen3.5 capability script에서 SkillBoss `qwen3.5-plus`의
  structured text/vision과 supplied-fixture registration은 통과했다. HTTP 500은 JSON-object keyword/
  schema contract 누락과 upstream 400 wrapping 조합으로 원인확정·복구했다. exact
  `Qwen3.5-397B-A17B` identity와 completion/gold 품질은 미검증이라 deployment-ready가 아니다.
- model-independent multimodal probe에서 GPT-4o proxy text/vision과 registration은 통과했고 GLM
  4.5V는 text만 통과했다. 이는 대체 호환성 자료이며 Qwen 동등성·운영 승격 근거가 아니다.
- local durable notification outbox, filesystem lock, idempotency result store와 secret-free
  effective-config manifest를 reference 수준으로 구현했다.
- project create/update와 education enrollment/update는 hash-chained append-only journal로 domain
  file/audit를 복구한다. HITL report/outbox가 바뀌면 차단하고 reconcile은 알림을 재전송하지 않는다.
- Vector DB/Qdrant, 실제 embedding 품질, multi-model calibration, full product CLI, education/full
  evaluation API·OIDC/JWKS·immutable upload·Web, report/outbox producer transaction과 distributed worker는 아직
  구현되지 않았다.
- 실제 사내 데이터와 GitLab/메일 발송은 사용하지 않았다.
- Git 저장소는 `main`이 `origin/main`을 추적한다.

## 기준 문서

| 문서 | 역할 |
|---|---|
| [AXCalib_Concept_Overview.md](AXCalib_Concept_Overview.md) | 이름의 의미와 장기 제품개념 |
| [제품 브리프](docs/product/product-brief.md) | 사람 권한 중심 철학, 사용자 약속, MVP 경계 |
| [사용 안내서](docs/manuals/README.md) | Excalibur 비유, 5분 시작, 설정/API, 6컷 튜토리얼 |
| [심사 프로필·모델 endpoint](docs/manuals/04-review-profiles-and-model-endpoints.md) | 사업별 기준 주입, OpenAI/on-prem 환경변수와 사람 수정 |
| [API 계약](docs/api/README.md) | OpenAPI 3.1 JSON, typed options와 예제 |
| [WP-06.I1 Runtime API 리포트](docs/evaluation/wp06-i1-minimal-api-parity-report.md) | FastAPI parity, fail-closed auth/grant와 contract test |
| [WP-06.I2a Project API 리포트](docs/evaluation/wp06-i2a-principal-bound-project-api-report.md) | principal binding, staged artifact, scope/org/revision guard와 코드리뷰 |
| [API Alpha 위협 모델](docs/security/api-alpha-threat-model.md) | 현재 공격면, 통제와 운영 NO-GO 조건 |
| [개발 준비 감사](docs/readiness/development-readiness-audit.md) | offline slice 검증과 운영 NO-GO 조건 |
| [G3 Intelligence 개발 리포트](docs/evaluation/g3-intelligence-development-report.md) | 구현, live probe, 코드리뷰, 검증과 남은 위험 |
| [교육 프로그램/WP-01 개발 리포트](docs/evaluation/education-program-wp01-development-report.md) | 실제 PPT 예제, 교육 composition, hardening과 코드리뷰 |
| [Qwen3.5 capability 검증 리포트](docs/evaluation/qwen35-capability-validation-report.md) | SkillBoss proxy, exact checkpoint 경계, on-prem 실행 계약과 코드리뷰 |
| [WP-05.Q2 HTTP 500 복구 리포트](docs/evaluation/wp05-q2-skillboss-http500-recovery-report.md) | SkillBoss update, JSON-mode 원인, Qwen/GPT-4o/GLM 비교와 코드리뷰 |
| [WP-01.R1.1 Transaction Recovery 리포트](docs/evaluation/wp01-r1-transaction-recovery-report.md) | project journal, crash injection, idempotent reconcile과 남은 범위 |
| [WP-01.R1.2 Library MVP/Alpha 리포트](docs/evaluation/wp01-r1-2-library-mvp-alpha-report.md) | pipeline checkpoint, education recovery, maintenance, CLI/batch, clean wheel과 코드리뷰 |
| [CHANGELOG.md](CHANGELOG.md) | 사용자 관점의 주요 변경, 검증된 범위와 알려진 한계 |
| [인수인계 안내](docs/HANDOFF.md) | 쉬운 용어로 정리한 현재 상태, 실행법과 다음 작업 |
| [Memory Bank](.memory-bank/README.md) | 다음 작업자가 문맥을 빠르게 복구하기 위한 비권위 요약 캐시 |
| [WORK_SPEC.md](WORK_SPEC.md) | 제품·기능·비기능·데이터 요구사항 |
| [GOAL.md](GOAL.md) | 첫 Target, 기술선택, 단계별 Gate와 수용기준 |
| [DESIGN.md](DESIGN.md) | dossier, workflow, retrieval, model, backend/frontend 설계 |
| [AGENTS.md](AGENTS.md) | 사람과 coding Agent가 지킬 작업계약 |
| [two_gate_pipeline.md](docs/workflows/two_gate_pipeline.md) | 등록·수행·완료·HITL 실행 지침 |
| [education_project_lifecycle.md](docs/workflows/education_project_lifecycle.md) | 과정 설계→가입→과제 인증→과정 완료 HITL 실행 지침 |
| [architecture/README.md](docs/architecture/README.md) | 구조도·작업계획·인포그래픽 문서 지도 |
| [AXCalib Visual Guide](docs/architecture/axcalib-visual-guide.md) | 철학·Workflow Library 활용법·API/Web/App 예상 적용 사례 |
| [workflow-blueprint.md](docs/architecture/workflow-blueprint.md) | 계층·두 Gate·sequence·실패/재개·module dependency 구조도 |
| [module-delivery-plan.md](docs/architecture/module-delivery-plan.md) | M00~M13 module별 상태·의존성·검증·완료증거 |
| [composable-pipeline-plan.md](docs/architecture/composable-pipeline-plan.md) | 요소 모듈·국소 pipeline·전체 workflow 구현계획 |
| [AXCalib_Workflow_Architecture_v0.3-p1.pptx](docs/presentations/AXCalib_Workflow_Architecture_v0.3-p1.pptx) | 두 Gate·모듈·로드맵 stakeholder review deck |
| [PROJECT_STATE.md](PROJECT_STATE.md) | P/WP/G dependency Gantt, 현재 Active Slice, 일정·검증·특이사항과 append-only 작업 이력을 관리하는 단일 실행 원장 |

## 핵심 결정

- **Library first**: Core Library → CLI/Evaluation Harness → API/Batch → Web App 순서
- **Human authority**: Agent는 근거 있는 제안을 만들고 승인된 사람만 최종 상태를 확정
- **Minimal first**: `AXCalib.evaluate/aevaluate`에서 시작해 expert TOML/OpenAPI JSON으로 확장
- **Protected invariants**: HITL·알림·사람결정·stale/mentor guard는 설정으로 끌 수 없음
- **Composable pipelines**: 요소 모듈 → 국소 pipeline → versioned total workflow 순서로 조합
- **Thin interfaces**: working script, CLI, API, worker, Web은 같은 library pipeline을 사용
- **Visual control**: workflow 구조도와 module control board를 구현상태와 함께 갱신
- **Two gates**: 등록심의와 완료평가를 분리
- **Mandatory HITL**: Agent 제안 뒤 관리자만 최종 승인·반려
- **Mandatory notification**: 두 HITL Gate 진입 시 GitLab MR/email/recording adapter event 필수
- **Optional mentor**: 멘토 없이 수행 가능, 배정된 경우 완료 제출 전 mentor 승인 필수
- **One dossier**: project_id별 `AXC-{uuid}.axc.yaml` 한 파일을 지속 갱신
- **Immutable evaluation**: 평가 요청 시 revision과 SHA-256 snapshot을 고정
- **Evidence first**: criterion별 원문 locator 또는 판단불가 기록
- **Stage-aware retrieval**: registration/completion corpus 분리, provider adapter 교체 가능
- **Configurable similarity**: similarity portion은 stage별 설정하되 raw similarity가 자동판정하지 않음
- **On-prem first**: model/base URL/API key는 설정으로 주입

## 첫 구현 Target

실제 데이터와 network 없이 synthetic dossier로 다음 흐름을 관통한다.

~~~text
dossier 생성
→ 등록심의 snapshot/평가초안/관리자 알림·HITL
→ 승인 시 선택적 mentor 배정과 수행기록 갱신
→ 완료 제출 승인/등록
→ 완료평가 snapshot/등록 baseline 비교/평가초안
→ 관리자 알림·HITL/최종 완료판정
→ Markdown·JSON report
~~~

등록과 완료 평가 모두 같은 stage의 synthetic historical case를 lexical retrieval할 수 있다.
embedding model과 승인 corpus가 생기기 전 similarity portion 기본값은 `0.0`이다.

## 작업 하네스

최초 1회 또는 lockfile이 변경된 뒤 개발환경을 동기화한다.

~~~powershell
uv sync --locked --dev
~~~

이후 하네스는 `.venv`의 Python을 우선 사용하고, 가상환경이 없을 때만 시스템 Python으로
fallback한다.

~~~powershell
.\prep.ps1 status
.\prep.ps1 next
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 eval
.\prep.ps1 docling  # optional, 메모리 여유가 있을 때 별도 실행
~~~

`status`와 `validate`는 read-only다. 기본 test/eval은 network, GPU, API key를 사용하지 않는다.
기본 test는 저메모리 안전을 위해 optional Docling contract를 제외하며 `prep.ps1 docling`에서 별도
실행한다.

## Library MVP/Alpha 빠른 시작

개발환경과 CLI extra를 설치한다.

~~~powershell
uv sync --locked --dev --extra cli
uv run --no-sync axcalib pipeline list --workspace output/alpha-cli
~~~

제공된 실제 PPTX를 등록하고 등록심의 Agent 초안을 만든 뒤 관리자 HITL에서 멈추는 최소 예제다.
Docling을 강제로 불러오지 않고 OOXML 안전검사와 source hash에 고정된 reviewed sidecar를 사용한다.

~~~powershell
uv run --no-sync python examples/library_mvp_alpha_quickstart.py `
  --workspace output/library-mvp-alpha
~~~

예상 핵심 결과는 `pipeline_status=waiting_human`, `status=registration_hitl_pending`과
`allowed_commands=[approve,reject]`다. 이 출력은 Agent의 최종 승인이나 공식 심의결과가 아니다.

CLI는 같은 Library registry를 직접 호출한다.

~~~powershell
uv run --no-sync axcalib pipeline list --workspace output/alpha-cli
uv run --no-sync axcalib workspace maintain --workspace output/alpha-cli
uv run --no-sync axcalib batch run examples/batch-maintenance.jsonl `
  --workspace output/alpha-cli --max-concurrency 1
~~~

`workspace maintain`은 기본 report-only다. `--apply`를 명시해도 삭제하지 않고 quarantine/archive한다.
현재 Alpha CLI는 generic pipeline/runtime 도구이며 최종 목표인 전체 `dossier/evaluate/cases/verify`
명령 트리는 G4에서 확장한다.

## Runtime API local Alpha

~~~powershell
uv sync --locked --dev --extra api
uv run --no-sync pytest tests/contract/test_runtime_api_contract.py -q
~~~

`axcalib.api.create_app(runtime, token_verifier=..., pipeline_grants=...)`은 같은 Library registry와
checkpoint를 사용한다. verifier를 생략하면 모든 bearer token을 거부하고 grant를 생략하면 HTTP로
실행 가능한 pipeline이 0개다. 구현된 OpenAPI는
`docs/api/openapi.runtime.v1alpha1.json`, 향후 project evaluation/HITL 목표 계약은 별도
`docs/api/openapi.v1alpha1.json`이다. 현재는 in-process local Alpha이며 운영 server나 OIDC/RBAC
완료를 뜻하지 않는다.

## 제공 PPTX로 두 Gate 실행

관리자 결정을 주지 않으면 등록심의 초안과 알림을 만든 뒤 `registration_hitl_pending`에서
멈춘다.

~~~powershell
uv run --no-sync python scripts/pipelines/run_two_gate_pptx.py `
  tests/sources/oled_qc_project_outline.pptx `
  --proposal-sidecar tests/sources/oled_qc_project_outline.axcalib.json `
  --title "OLED QC 분자설계 과제" `
  --workspace output/pptx-review
~~~

동일 파일을 최종안으로 간주하는 전체 회귀 demo는 관리자 결정을 **명시적으로** 전달한다.
Agent의 등록 제안은 `needs_changes`, 완료 제안은 동일 hash와 수행증거 부족 때문에
`not_accept`가 예상된다.

현재 local script는 actor identity를 인증하지 않으므로 이 입력은
`authority_context=offline_unverified_actor`로 기록되며 실제 관리자 승인으로 간주하지 않는다.

~~~powershell
uv run --no-sync python scripts/pipelines/run_two_gate_pptx.py `
  tests/sources/oled_qc_project_outline.pptx `
  --proposal-sidecar tests/sources/oled_qc_project_outline.axcalib.json `
  --title "OLED QC 분자설계 과제" `
  --workspace output/pptx-two-gate-demo `
  --registration-decision approve `
  --registration-rationale "보완점을 확인했으며 offline 실패경로 검증에 한해 등록한다." `
  --completion-decision not_accept `
  --completion-rationale "제안서와 최종안 hash가 같고 수행증거가 없어 수용하지 않는다."
~~~

입력이 image-only인 동안 sidecar는 원본 SHA-256이 일치해야 한다. sidecar가 없으면 시각 내용을
추론하지 않고 근거 부족으로 처리한다. 결과 해설은
[PPTX demo 기록](docs/evaluation/oled-qc-pptx-demo.md)에 있다.

동일 fixture의 visual provenance와 근거 연결 회귀는 다음 명령으로 실행한다.

~~~powershell
uv run --no-sync python evals/evidence_quality.py
uv run --no-sync python evals/evidence_quality.py --with-docling
~~~

측정 범위와 코드리뷰 경계는
[WP-02.Q1 근거 품질 리포트](docs/evaluation/wp02-actual-ppt-evidence-quality-report.md)에 있다.

## 실제 PPT 기반 교육 프로그램 예제

다음 예제는 사용자가 넣어 둔 제안 PPTX를 프로젝트 등록자료로 사용하고, 별도 synthetic 완료
PPTX를 제출한다. 과정 가입으로 세 개 목표를 만들고, 오리엔테이션 확인 → 프로젝트 두 Gate →
성찰 점수 → 과정 완료 관리자 HITL을 모두 Library 호출로 실행한다. 관리자 입력은 local
`offline_unverified_actor`이며 공식 교육 인증이 아니다.

~~~powershell
uv run --no-sync python examples/education_project_lifecycle/run_full_lifecycle.py `
  --workspace output/education-project-lifecycle
~~~

과정 정의는
[`program.yaml`](fixtures/synthetic/education_project_lifecycle/program.yaml), 전체 호출 순서는
[`run_full_lifecycle.py`](examples/education_project_lifecycle/run_full_lifecycle.py)에 있다.

Docling과 명시적 live model을 붙이려면 optional dependency와 승인된 비식별 입력이 필요하다.
기본 `prep.ps1 test|eval`은 외부 endpoint를 호출하지 않으며 Docling contract도 별도 명령으로
격리한다. 제공 image-only PPTX의 최근 Docling 증거는 16 page/0 text이며 의미 추출 성공을 뜻하지
않는다.

~~~powershell
uv sync --locked --dev --extra docling
.\prep.ps1 docling
uv run --no-sync python scripts/pipelines/run_two_gate_pptx.py `
  tests/sources/oled_qc_project_outline.pptx `
  --proposal-sidecar tests/sources/oled_qc_project_outline.axcalib.json `
  --title "G3 비식별 fixture" `
  --workspace output/g3-review `
  --docling `
  --live-model
~~~

## 다음 단계

1. G4 첫 slice에서 현재 Library registry/run checkpoint를 호출하는 minimal FastAPI adapter와 실제
   OpenAPI 3.1 implementation parity를 구축한다.
2. Alpha CLI를 목표 `dossier/evaluate/cases/batch/report/verify` 명령 UX로 점진 확장한다.
3. report/outbox producer transaction과 database/distributed worker lease를 별도 hardening한다.
4. exact on-prem `Qwen3.5-397B-A17B`에서 registration/completion과 serving fingerprint를 검증한다.
5. Product/Evaluation Owner가 실제 rubric, context→profile mapping과 합격선을 승인한다.
6. 다른 실제 제안/완료 template과 Qdrant·embedding·multi-model 품질 fixture를 추가한다.
7. program rollout/retire/migration, 운영 notification/RBAC와 Web은 책임자 승인 뒤 진행한다.

실제 데이터 반입, 추가 live model, 운영 알림과 배포는 별도 승인 전 진행하지 않는다. 현재 통과한
것은 G3 reference contract와 제한된 live smoke이며 실제 모델·retrieval 품질 검증이 아니다.
