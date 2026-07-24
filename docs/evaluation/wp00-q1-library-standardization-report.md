# WP-00.Q1 Library Standardization and Example Audit

- 기준일: 2026-07-24
- 범위: local/synthetic Library Alpha
- 판정: `standardized_local_alpha`
- 품질 경계: `quality_pending`
- 운영 판정: `operational_no_go`

## 1. 결론

현재 AXCalib는 첫 사용자가 `AXCalib → Case → evaluate → 사람 결정 → status/summary`로 이해할 수
있는 local Library 골격을 갖췄다. 기존 `ReportRenderer`는 한 번의 불변 Agent 평가초안을 계속
담당하고, 새 `Case` read facade가 project_id로 최신 dossier와 두 report, 별도 사람 결정·criterion
보정을 연결한다. 새 workflow나 상태전이를 추가하지 않았다.

변경 규모는 **중간**으로 산정했고 실제로 다음 경계 안에서 끝냈다.

- public handle 1개: `Case`
- typed read model: `CaseStatus`, `CaseSummary`와 하위 projection
- 순수 renderer 1개: object를 읽기 쉬운 Markdown으로 변환
- 기존 `register_case(...)`의 Alpha 반환형을 initial dossier snapshot에서 live `Case`로 정리
- raw snapshot 호환: `create_project(...)`, 최신 raw dossier: `case.dossier`
- 정상 사용자 예제 2개와 EX-01~EX-12 machine-readable catalog

이 판정은 실제 rubric 품질, exact on-prem Qwen, embedding/Qdrant, remote identity/upload, 분산
worker 또는 Web이 준비됐다는 뜻이 아니다.

## 2. 첫 사용자 Walkthrough

```python
from axcalib import AXCalib

ax = AXCalib("output/review")
case = ax.register_case(
    "proposal.pptx",
    title="검토할 과제",
    sidecar_path="proposal.axcalib.json",
)
ax.submit_registration(case.project_id)
ax.evaluate(case.project_id, "registration")

status = case.get_current_status()                  # CaseStatus
status_md = case.get_current_status(format="md")
summary_json = case.get_summary(format="json")
summary_md = case.get_summary(format="md", verbose=True)
```

`get_current_status`는 “지금 어디이고 누가 무엇을 해야 하는가”에 답한다. `get_summary`는
등록심의·수행·완료평가에서 Agent가 무엇을 제안했고 사람이 무엇을 결정·보정했는지 연결한다.
각 호출은 최신 dossier revision을 다시 읽으므로 앞서 만든 Python handle을 버릴 필요가 없다.
`aget_current_status/aget_summary`는 같은 result/error 의미의 async 대응 함수다.

`next_actions`는 현재 domain state에서 가능한 조치 안내다. 현재 caller가 실제 권한을 가졌다는
뜻은 아니며 remote API는 기존 principal/resource authorization을 별도로 통과해야 한다.

## 3. 정보 흐름과 책임 경계

```text
Case(project_id)
→ latest AXC-{project_id}.axc.yaml reload
→ report path가 workspace/reports 아래인지 확인
→ active/archive committed transaction journal의 report SHA-256 확인
→ project/stage/report/snapshot/policy/artifact hash 일치 확인
→ Agent assessment 원본 + 별도 HumanDecision/ReviewerAdjustment 결합
→ typed object | JSON | Markdown
```

사람의 보정은 `effective_assessment`에 반영되지만 `agent_assessment`와 report 파일은 바뀌지 않는다.
기본 출력은 local dossier/report URI, criterion 원문과 사람 actor/rationale를 제외한다.
`verbose=True`에서만 local 사용자가 criterion 근거와 사람 결정 상세를 요청한다. evidence locator의
storage path는 `artifact:<artifact_id>#<fragment>`로 치환한다.

remote API/Web은 verbose Library object를 그대로 직렬화하면 안 된다. 현재 principal-bound
`ProjectResourceView`처럼 property-level authorization과 redaction을 적용해야 한다.

## 4. GOAL Trace Matrix

| Target / WP | Code 상태 | Test / Example | 판정과 미완료 |
|---|---|---|---|
| T1 Offline Evidence-to-Review | dossier, two-gate pipeline, `Case` read facade | EX-01/02, PPTX integration | local vertical slice verified; 운영 품질 아님 |
| WP-00 Harness | prep, ledger, Wiki, schema/secret validation, example catalog | harness/Wiki contract, catalog test | verified local |
| WP-01 Dossier/State | YAML CAS, snapshot, state machine, project journal | EX-03~06, dossier/transaction tests | local Alpha; producer/DB transaction 남음 |
| WP-01E Education | immutable program/enrollment/project binding | EX-11, education integration/API | offline reference; credential/rollout 남음 |
| WP-02 Evidence | safe OOXML, sidecar, optional Docling, restricted slide render | EX-01/02, evidence-quality eval | supplied image-only fixture 한정; general OCR/VLM 남음 |
| WP-03 Evaluation/Report | policy registry, deterministic/structured evaluator, immutable report, Case renderer | EX-01/02/08, Case integrity tests | offline reference; 공식 rubric/gold 남음 |
| WP-04 Historical Cases | Null/Lexical, stage filter, similarity policy | EX-07, retrieval unit/eval | embedding/Qdrant/labeled benchmark pending |
| WP-05 Model/Calibration | OpenAI-compatible gateway, structured output, capability probes | EX-08, Qwen/GPT-4o proxy evidence | exact Qwen, panel/calibration pending |
| WP-06 Interfaces | CLI/batch, in-process API, local queue/worker, OIDC/JWKS reference | EX-09/10/12, contract tests | remote IdP/upload/distributed worker/SSE pending |
| WP-07 Web Review | UX/design/architecture 문서 | 실행 예제 없음 | `blocked_policy`; FE/RBAC 선택과 G5 E2E 필요 |
| WP-08 Pilot | 계획·metric target만 존재 | 실행 예제 없음 | 승인된 비식별 50쌍과 Owner 결정 필요 |

### Gate 추적

| Gate | 현재 근거 | 판정 |
|---|---|---|
| G0 Alignment | WORK_SPEC/GOAL/DESIGN와 trace matrix | `reference_ready`; Owner sign-off 남음 |
| G1 Harness | prep validate/test/eval, ledger/Wiki/catalog | `verified_local` |
| G2 Domain MVP | dossier/state/snapshot/recovery/Case examples | `verified_local_alpha` |
| G3 Intelligence | restricted PPTX, lexical, structured evaluator/report | `reference_verified_quality_pending` |
| G4 Interfaces | CLI/API/local Worker/OIDC signed reference | `in_progress`; remote 운영 증거 남음 |
| G5 Web Review | 설계 문서만 존재 | `blocked_policy` |
| G6 Pilot | 없음 | `not_started` |
| G7 Go/No-Go | Sponsor 결정 없음 | `not_started` |
| G8 Integration | 운영 API/SSO/backup/rollback 없음 | `not_started` |

orphan 또는 과대 완료 표시는 발견하지 않았다. 다만 WP-07/08과 G5~G8은 계획만 존재하므로
executable example을 억지로 만들지 않고 pending으로 유지했다.

## 5. Public API Review

### 유지할 첫 경로

- `AXCalib(workspace)` 또는 `AXCalib.from_toml(...)`
- `register_case(...) -> Case`
- `submit_registration(...)`
- `evaluate/aevaluate(...)`
- 명시적 `decide_registration/decide_completion(...)`
- `case.get_current_status/aget_current_status(...)`
- `case.get_summary/aget_summary(...)`

### 고급 경로로 분리할 것

- `execute_pipeline`, `enqueue_pipeline`, `create_worker`, `run_batch`
- program/enrollment composition
- review profile registry, model/retrieval/runtime adapter 조립
- transaction reconciliation과 workspace maintenance

첫 quickstart에는 고급 registry/port를 노출하지 않는다. `format`은 `object|json|md`,
`verbose`는 boolean 하나만 사용하며 unknown 값은 실패한다.

### 명칭과 호환 판단

| 항목 | 판단 |
|---|---|
| `register_case` | 사용자 의도와 일치; live `Case` 반환으로 정리 |
| `create_project` | 기존 raw initial `ProjectDossier` 반환 호환 API로 유지 |
| `case.dossier` | 최신 raw dossier를 명시적으로 요청하는 escape hatch |
| `ReportRenderer` | 단일 Agent report renderer로 유지; dossier load/state 의미를 넣지 않음 |
| `CaseViewRenderer` | pure formatting만 수행; file read/state mutation 없음 |
| `get_current_status` vs `get_summary` | operational now와 lifecycle digest로 책임 분리 |

## 6. Script Inventory

| Script | Library/Port 호출 | Domain 로직 복제 | 판단 |
|---|---|---:|---|
| `scripts/pipelines/run_two_gate_pptx.py` | `AXCalib.from_toml` + `run_pptx` | 없음 | thin working script |
| `run_dossier_freeze.py` | allowlisted `DossierFreezePipeline` | 없음 | thin |
| `run_transaction_reconciliation.py` | `AXCalib.reconcile_transactions` | 없음 | thin |
| `run_local_worker_once.py` | `AXCalib.create_worker` | 없음 | thin; exit code만 mapping |
| `export_runtime_openapi.py` | API app factory/OpenAPI | 없음 | contract export |
| `export_schemas.py` | schema export helper | 없음 | contract export |
| `probe_qwen35_capabilities.py` | model adapter capability port | 없음 | opt-in live adapter diagnostic |
| `probe_multimodal_capabilities.py` | generic model capability port | 없음 | opt-in live adapter diagnostic |
| `scripts/fixtures/generate_education_completion_pptx.py` | fixture authoring | 해당 없음 | synthetic fixture generator |
| `scripts/wiki/sync_wiki.py` | Wiki harness | 해당 없음 | docs delivery adapter |

두 live probe는 domain 평가 workflow가 아니라 provider adapter contract 도구다. canonical
`OPENAI_*`가 없으면 실행하지 않고 raw prompt/output/reasoning을 저장하지 않는다. 기본
test/eval/example catalog에서 호출되지 않는다.

## 7. EX-01~EX-12 Coverage

기준정보는 `examples/catalog.yaml`이다.

| ID | 범주 | 기대 결과 | 실행 증거 |
|---|---|---|---|
| EX-01 | 정상 + 사람 대기 | registration HITL pending, 자동 승인 없음 | quickstart + PPTX integration |
| EX-02 | 정상 two-gate | pass/approve → 수행 → accept/accept, readable summary | `case_lifecycle` integration |
| EX-03 | 반려 | registration terminal, 수행 진입 거부 | Case unit |
| EX-04 | mentor guard | 배정 후 mentor 이외 완료 승인 거부 | workflow unit |
| EX-05 | stale | snapshot/병합 없이 stale 반환 | dossier pipeline unit |
| EX-06 | notification | HITL pending 전이 fail closed | PPTX integration |
| EX-07 | retrieval | 양수 portion + adapter 없음 오류 | retrieval unit |
| EX-08 | model/evidence | 잘못된 locator 거부, unsupported 판정 하향 | model integration |
| EX-09 | identity | valid만 principal; invalid 401/key provider 503 | identity unit/contract |
| EX-10 | worker | retryable bounded retry, terminal/restart replay | worker unit |
| EX-11 | education context | version/learner/milestone/org mismatch 거부 | education contract |
| EX-12 | batch | 부분 실패 노출, 성공 item 재실행 없음 | executor unit |

사용자 문서에는 EX-01/02만 먼저 보이고, 나머지는 문제 상황별 catalog에서 찾게 해 progressive
disclosure를 유지했다.

## 8. Code, Security, Reliability Review

확인하고 보강한 항목:

- Case는 mutable 상태를 cache하지 않고 매 호출 최신 dossier를 읽는다.
- report는 `workspace/reports` 밖 경로, 10 MiB 초과, 잘못된 filename/schema를 거부한다.
- active 또는 non-destructively archived committed journal의 SHA-256 anchor가 없거나 다르면
  fail closed한다.
- report project/stage/report/snapshot/policy/artifact hash와 HumanDecision report/stage/command,
  ReviewerAdjustment criterion/base assessment를 다시 확인한다.
- 기본 JSON/Markdown은 local URI, raw artifact path, actor/rationale와 criterion excerpt를 제외한다.
- verbose evidence locator도 storage path를 노출하지 않는다.
- Markdown projection은 title·model/human text의 HTML과 image/link control 문자를 escape한다.
- Agent report 파일은 사람 결정 뒤 byte-for-byte 불변이다.
- 등록 반려는 terminal이고 이후 수행 전이가 거부된다.
- Pydantic model은 `extra=forbid`, 출력은 typed object에서만 만든다.
- 실제 endpoint/data/account/upload는 추가하지 않았고 API key를 읽지 않았다.
- checkout에서 실행하는 모든 `scripts/pipelines/*.py`와 두 사용자 예제가 installed editable
  metadata에 의존하지 않고 `src`를 먼저 bootstrap하는지 회귀한다.
- Wiki export의 atomic replace는 Windows transient lock만 짧고 제한적으로 재시도하며 마지막
  실패를 숨기지 않는다.

잔여 위험:

| ID | Severity | 내용 | 조치 |
|---|---|---|---|
| Q1-R01 | Medium | public 예외가 module별 `ValueError/RuntimeError` 계열로 분산 | G4 CLI/SDK 전에 stable top-level taxonomy 설계 |
| Q1-R02 | Medium | Case projection은 local file repository용; remote async repository/auth view가 아님 | API route는 principal-bound safe projection을 별도 조립 |
| Q1-R03 | Low | report hash anchor 탐색이 local journal 수에 선형 | pilot DB/read index 설계에서 report index 추가 |
| Q1-R04 | High | EX-02 pass는 축소 example policy이며 공식 rubric 품질이 아님 | Owner-approved rubric/gold 전 quality pending 유지 |
| Q1-R05 | High | exact Qwen/Vector DB/panel/pilot 품질 없음 | WP-03/04/05/08 Gate를 그대로 유지 |
| Q1-R06 | High | remote identity/upload/distributed infra 정책 미승인 | G4 operational no-go 유지 |

## 9. Defect Log

| Defect | 기존 영향 | 조치 | 상태 |
|---|---|---|---|
| Q1-D01 | 문서 변수는 `case`지만 반환형은 frozen dossier snapshot | live Case 반환 + `create_project` 호환 분리 | Closed |
| Q1-D02 | current state와 두 Gate 결과를 한 호출로 읽기 어려움 | typed status/summary와 MD/JSON 추가 | Closed |
| Q1-D03 | 사람 보정 반영 시 Agent 원본과 섞일 위험 | agent/effective assessment를 나란히 표시 | Closed |
| Q1-D04 | locator/URI와 결정 사유가 편의 출력에서 새어 나갈 위험 | safe default, verbose 분리, locator path redaction | Closed local |
| Q1-D05 | report content 변조가 schema/identity만 유지하면 탐지되지 않음 | committed active/archive journal SHA-256 재검증 | Closed local |
| Q1-D06 | 자연스러운 pass/accept 읽기 예제가 없음 | example-only policy + actual/synthetic PPT lifecycle | Closed with quality boundary |
| Q1-D07 | EX-01~12가 계획표뿐이고 명령/cleanup 기준정보가 없음 | machine-readable catalog + validation test | Closed |
| Q1-D08 | unified public exception/target CLI 명칭 미완료 | 잔여 위험과 후속 Gate에 명시 | Open, non-blocking for local Alpha |
| Q1-D09 | checkout 예제와 transaction/OpenAPI script가 불완전 editable install에서 import 실패 | `src` bootstrap과 전체 pipeline-script 순서 회귀 | Closed |
| Q1-D10 | 최소 quickstart JSON이 local dossier/report 절대경로를 노출 | `report_id`와 safe Case status만 반환 | Closed |
| Q1-D11 | Wiki export atomic replace가 Windows transient lock 1회에 실패 | bounded retry와 synthetic lock 회귀 | Closed local |
| Q1-D12 | Case Markdown의 title/model/human text가 active Markdown/HTML로 해석될 여지 | HTML·image/link control escape와 악성 title 회귀 | Closed local |

## 10. 검증

최종 closeout은 다음을 독립 process로 실행했다.

```powershell
.\prep.ps1 test unit
.\prep.ps1 test integration-core
.\prep.ps1 test integration-eval
.\prep.ps1 test integration-ops
.\prep.ps1 test contract
.\prep.ps1 eval
.\prep.ps1 validate
uv run --no-sync ruff check .
uv run --no-sync pyright
```

추가로 EX-01~EX-12 catalog node를 묶어 실행하고, 실제 PPT 기반 readable example, core/cli/api/
identity clean wheel과 Wiki validate/export parity를 확인한다. Docling과 live model은 저메모리·외부
호출 분리 원칙에 따라 이번 기본 회귀에서 실행하지 않는다.

### 10.1 결과

| 검증 | 결과 |
|---|---|
| Unit | 118 passed |
| Integration | 34 passed: core 9, eval 19, ops 6 |
| Contract | 21 passed |
| 전체 offline test | 173 passed |
| EX-01~EX-12 대표 node | 16 passed: unit 7, integration 5, identity/contract 4 |
| Offline eval | 10 groups passed |
| 실제 PPT quickstart | registration HITL pending, local URI 출력 0 |
| 실제 PPT readable lifecycle | completion accepted, pass/approve와 accept/accept Markdown/JSON 생성 |
| Clean core wheel | `Case` import와 actual-PPT registration HITL 통과; FastAPI/Docling core 유입 0 |
| Clean interface wheel | cli/api/identity import, OpenAPI 3.1과 installed CLI catalog 통과 |
| Docling packaging | wheel optional-extra metadata 확인; parser는 이번 closeout에서 미실행 |
| Static/schema | Ruff all passed, changed-format passed, Pyright 0/0, generated schema parity passed |
| Workspace/Wiki | `prep validate` 0/0; Wiki validate 0, GitHub/GitLab 각 17 managed files, CI parity 1 passed |

첫 monolithic `prep test integration`은 assertion이 아니라 64초 도구 timeout으로 종료되고 닫힌
stdout에서 `OSError 22`가 발생했다. 이후 `integration-core`, `integration-eval`, `integration-ops`
shard를 하네스에 추가해 각각 9/19/6으로 통과했다. clean CLI의 첫 진단에서도 존재하지 않는
import 경로와 잘못된 option, 조기 종료 pipe를 사용한 명령 작성 오류가 있었으며 공개
`axcalib.api.oidc`, `--json-output`과 비파이프 실행으로 바로 교정해 통과했다. 제품 결함이나
endpoint 실패로 확대 기록하지 않는다.
