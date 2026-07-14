# AXCalib

**AX Certification Agent Library**

AXCalib는 하나의 과제 dossier에 등록심의, 수행기록, 멘토링, 산출물, KPI, 완료평가를
연결하고, 평가기준·과거 유사사례·다중 모델 분석을 근거로 사람의 AX 인증 판단을
지원하는 Library다.

> Calibrate Assessment. Certify AX.

## 현재 상태

현재는 **P1 실행 하네스 구축 완료, G1 검토 및 WP-01 Domain MVP 착수 전** 단계다.

- Python 3.12 `src/axcalib` package scaffold가 있다.
- `prep.ps1 status|next|validate|test|eval`이 실행 가능하다.
- 두 Gate의 관리자 승인·필수 알림·선택적 멘토 흐름을 reference state machine으로 검증한다.
- 요소 모듈·국소 pipeline·total workflow 구현방식은 설계됐지만 Pipeline kernel은 아직 없다.
- 전체 workflow 구조도와 M00~M13 module control board가 architecture 문서로 관리된다.
- 두 Gate, module map, RAG 도입단계와 다음 slice를 정리한 12-slide PowerPoint가 있다.
- synthetic fixture와 lexical retrieval만 사용한다.
- dossier schema·영속 저장·실제 report/model/Vector DB/API/Web은 아직 구현되지 않았다.
- 실제 사내 데이터, live model, GitLab/메일 발송은 사용하지 않았다.
- Git 저장소는 `main`이 `origin/main`을 추적한다.

## 기준 문서

| 문서 | 역할 |
|---|---|
| [AXCalib_Concept_Overview.md](AXCalib_Concept_Overview.md) | 이름의 의미와 장기 제품개념 |
| [WORK_SPEC.md](WORK_SPEC.md) | 제품·기능·비기능·데이터 요구사항 |
| [GOAL.md](GOAL.md) | 첫 Target, 기술선택, 단계별 Gate와 수용기준 |
| [DESIGN.md](DESIGN.md) | dossier, workflow, retrieval, model, backend/frontend 설계 |
| [AGENTS.md](AGENTS.md) | 사람과 coding Agent가 지킬 작업계약 |
| [two_gate_pipeline.md](docs/workflows/two_gate_pipeline.md) | 등록·수행·완료·HITL 실행 지침 |
| [architecture/README.md](docs/architecture/README.md) | 구조도·작업계획·인포그래픽 문서 지도 |
| [workflow-blueprint.md](docs/architecture/workflow-blueprint.md) | 계층·두 Gate·sequence·실패/재개·module dependency 구조도 |
| [module-delivery-plan.md](docs/architecture/module-delivery-plan.md) | M00~M13 module별 상태·의존성·검증·완료증거 |
| [composable-pipeline-plan.md](docs/architecture/composable-pipeline-plan.md) | 요소 모듈·국소 pipeline·전체 workflow 구현계획 |
| [AXCalib_Workflow_Architecture_v0.3-p1.pptx](docs/presentations/AXCalib_Workflow_Architecture_v0.3-p1.pptx) | 두 Gate·모듈·로드맵 stakeholder review deck |
| [PROJECT_STATE.md](PROJECT_STATE.md) | 현재 Gate, 차단요인, 다음 작업 |

## 핵심 결정

- **Library first**: Core Library → CLI/Evaluation Harness → API/Batch → Web App 순서
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

## 다음 단계

1. G1 하네스 baseline을 검토한다.
2. WP-01에서 typed PipelineContext/Result/Registry 최소계약을 먼저 만든다.
3. dossier schema, revision, snapshot, atomic write를 `dossier.freeze` 국소 pipeline으로 연결한다.
4. 실제 실행되는 Python script로 검증하고 이후 CLI/API가 같은 pipeline을 호출하게 한다.
5. review request와 notification outbox를 dossier mutation과 원자적으로 저장한다.
6. WP-02 이후 evidence parser, vector/model adapter를 독립 모듈과 pipeline으로 추가한다.

실제 데이터 반입, live model, 운영 알림, 배포, commit/push는 별도 승인 전 진행하지 않는다.
