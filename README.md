# AXCalib

**AX Certification Agent Library**

AXCalib는 하나의 과제 dossier에 등록심의, 수행기록, 멘토링, 산출물, KPI, 완료평가를
연결하고, 평가기준·과거 유사사례·다중 모델 분석을 근거로 사람의 AX 인증 판단을
지원하는 Library다.

> **근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다.**
>
> Evidence qualifies. Calibration aligns. Authorized humans certify.

## 현재 상태

현재는 제공된 image-only PPTX를 두 Gate로 처리하는 **G2 offline vertical slice 검증 완료**
단계다. Python Library, local pipeline, working script가 실제 dossier·snapshot·평가초안·HITL
결정·audit 결과를 만든다. 이것은 T1 전체나 운영 제품 완료를 뜻하지 않는다.

- Python 3.12 `src/axcalib` package와 `AXCalib` facade가 실행된다.
- `prep.ps1 status|next|validate|test|eval`이 실행 가능하다.
- 두 Gate의 관리자 승인·필수 알림·선택적 멘토 흐름을 persisted dossier와 연결했다.
- allowlisted `two-gate-pptx@v1alpha1` pipeline은 sync/async로 같은 결과 의미를 제공한다.
- 전체 workflow 구조도와 M00~M13 module control board가 architecture 문서로 관리된다.
- 최소 Library facade, default/expert TOML, runtime schema와 OpenAPI 3.1 계약이 문서화됐다.
- 권한 모델 일러스트, 정확한 SVG와 6컷 튜토리얼이 사용자 매뉴얼로 연결된다.
- 두 Gate, module map, RAG 도입단계와 다음 slice를 정리한 12-slide PowerPoint가 있다.
- synthetic fixture와 lexical retrieval만 사용한다.
- YAML dossier, snapshot, 제한된 PPTX ingest, deterministic evaluator와 JSON/Markdown report를
  구현했다.
- 실제 evaluator model, Vector DB, durable outbox, CLI/API/Web은 아직 구현되지 않았다.
- 실제 사내 데이터, live model, GitLab/메일 발송은 사용하지 않았다.
- Git 저장소는 `main`이 `origin/main`을 추적한다.

## 기준 문서

| 문서 | 역할 |
|---|---|
| [AXCalib_Concept_Overview.md](AXCalib_Concept_Overview.md) | 이름의 의미와 장기 제품개념 |
| [제품 브리프](docs/product/product-brief.md) | 사람 권한 중심 철학, 사용자 약속, MVP 경계 |
| [사용 안내서](docs/manuals/README.md) | Excalibur 비유, 5분 시작, 설정/API, 6컷 튜토리얼 |
| [API 계약](docs/api/README.md) | OpenAPI 3.1 JSON, typed options와 예제 |
| [개발 준비 감사](docs/readiness/development-readiness-audit.md) | offline slice 검증과 운영 NO-GO 조건 |
| [WORK_SPEC.md](WORK_SPEC.md) | 제품·기능·비기능·데이터 요구사항 |
| [GOAL.md](GOAL.md) | 첫 Target, 기술선택, 단계별 Gate와 수용기준 |
| [DESIGN.md](DESIGN.md) | dossier, workflow, retrieval, model, backend/frontend 설계 |
| [AGENTS.md](AGENTS.md) | 사람과 coding Agent가 지킬 작업계약 |
| [two_gate_pipeline.md](docs/workflows/two_gate_pipeline.md) | 등록·수행·완료·HITL 실행 지침 |
| [architecture/README.md](docs/architecture/README.md) | 구조도·작업계획·인포그래픽 문서 지도 |
| [AXCalib Visual Guide](docs/architecture/axcalib-visual-guide.md) | 철학·Workflow Library 활용법·API/Web/App 예상 적용 사례 |
| [workflow-blueprint.md](docs/architecture/workflow-blueprint.md) | 계층·두 Gate·sequence·실패/재개·module dependency 구조도 |
| [module-delivery-plan.md](docs/architecture/module-delivery-plan.md) | M00~M13 module별 상태·의존성·검증·완료증거 |
| [composable-pipeline-plan.md](docs/architecture/composable-pipeline-plan.md) | 요소 모듈·국소 pipeline·전체 workflow 구현계획 |
| [AXCalib_Workflow_Architecture_v0.3-p1.pptx](docs/presentations/AXCalib_Workflow_Architecture_v0.3-p1.pptx) | 두 Gate·모듈·로드맵 stakeholder review deck |
| [PROJECT_STATE.md](PROJECT_STATE.md) | 현재 Gate, 차단요인, 다음 작업 |

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
~~~

`status`와 `validate`는 read-only다. 기본 test/eval은 network, GPU, API key를 사용하지 않는다.

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

## 다음 단계

1. 실제 사용할 제안/완료 template의 field와 locator 계약을 fixture로 고정한다.
2. dossier JSON Schema, idempotency, stale result와 durable outbox를 보강한다.
3. 구조화 rubric registry와 더 많은 golden dataset으로 evaluator를 검증한다.
4. template spike 뒤에만 Docling/slide-render/VLM adapter 범위를 결정한다.
5. Typer CLI parity를 먼저 완성하고 API/worker/Web은 별도 Gate에서 진행한다.

실제 데이터 반입, live model, 운영 알림, 배포, commit/push는 별도 승인 전 진행하지 않는다.
현재 통과한 것은 supplied-PPTX offline workflow 회귀뿐이며 모델·retrieval 품질 검증이 아니다.
