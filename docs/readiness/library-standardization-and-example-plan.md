# Library Standardization and Example Self-check Plan

- 제안 Slice: `WP-00.Q1 goal-alignment-usability-example-audit`
- 착수조건: WP-06.I4.0-1 checkpoint 완료
- 목적: “기능 수”가 아니라 신뢰성, 안전성, 직관성과 재사용 가능성을 기준으로 Library를 표준화
- 범위 경계: 이 계획 자체는 기능 완료 또는 운영 품질 증거가 아니다.

## 실행 상태

- 2026-07-24: `WP-00.Q1` local closeout 완료
- 결과: `Case` read facade, GOAL/script trace, EX-01~EX-12 machine-readable catalog와 회귀 추가
- 판정 근거: `docs/evaluation/wp00-q1-library-standardization-report.md`
- 검증: 173 offline tests, 10 eval groups, clean core/interface wheel, Wiki/schema/static parity
- 경계: local/synthetic 표준화이며 실제 rubric·on-prem Qwen·Vector DB·운영 identity/upload 품질은
  계속 pending/no-go

## 1. 감사 질문

1. GOAL의 Target/WP/Gate 수용기준이 코드, test, example, 미완료 표기 중 하나에 연결되는가?
2. 첫 사용자는 `AXCalib` facade와 한두 개의 명확한 객체만으로 대표 흐름을 시작할 수 있는가?
3. script/CLI/API/worker가 domain 판단을 복제하지 않고 같은 pipeline/application service를 쓰는가?
4. 오류가 성공처럼 보이지 않고 `waiting_human`, `blocked`, `stale`, retryable/terminal failure로
   구분되는가?
5. 실제 모델·retrieval·identity·upload·운영 품질이 local fixture 결과와 섞여 설명되지 않는가?
6. secret, 원문, 개인정보, hidden reasoning과 사람 전용 결정을 Library가 안전하게 경계하는가?

## 2. 산출물

| 산출물 | 최소 내용 | Exit Evidence |
|---|---|---|
| GOAL trace matrix | T1, WP-00~08, G0~G8 → code/test/example/pending | orphan/overclaim 0 또는 명시적 issue |
| public API review | facade, Dossier, evaluate/aevaluate, config, error taxonomy | 5분 시작 사용자 walkthrough |
| script inventory | 각 script의 I/O와 호출 pipeline, domain logic 복제 여부 | thin-script static review |
| example catalog | persona, fixture, command, expected state/report, cleanup | offline repeat run |
| negative matrix | authority, stale, evidence, model, retrieval, identity, worker failure | expected failure assertion |
| packaging review | core/api/identity/docling/cli extra 독립성 | clean-environment smoke |
| security/reliability review | dependency, secret, path, concurrency, audit, recovery | review log와 residual risk |

## 3. Example matrix

| ID | 사례 | 반드시 확인할 결과 |
|---|---|---|
| EX-01 | 최소 synthetic project 등록심의 | report 생성 후 registration HITL 대기, 자동 승인 없음 |
| EX-02 | 제공 PPTX two-gate lifecycle | source hash/locator, 등록 승인, 수행 증거, 완료평가 연결 |
| EX-03 | 등록 반려 | 반려 report/audit 후 수행 단계 진입 거부 |
| EX-04 | mentor 선택/필수 guard | 미배정은 진행, 배정 시 mentor 승인 없이 완료 등록 거부 |
| EX-05 | stale revision/conflict | 원본 변경 뒤 평가/결정 자동 병합 금지 |
| EX-06 | notification 실패 | HITL pending 전이 fail closed |
| EX-07 | retrieval portion > 0 / corpus 없음 | 가중치 재분배 없이 blocked |
| EX-08 | malformed model output/locator | structured validation 실패 또는 insufficient evidence |
| EX-09 | OIDC valid/tampered/expired/wrong issuer-role-scope | valid만 principal, 나머지는 401; key source 장애 503 |
| EX-10 | queued worker retry/restart/replay | retryable만 재시도, terminal 중복 실행 없음 |
| EX-11 | 교육 program/enrollment/project context | version/hash/learner/milestone 불일치 연결 거부 |
| EX-12 | batch 일부 실패/resume | 항목별 상태와 idempotency 보존, 일부 실패 은폐 없음 |

각 example은 synthetic/offline 기본이며 실제 endpoint 호출은 별도 `live` 명령과 명시적 동의를
요구한다. README/Wiki의 첫 경로에는 EX-01/02만 노출하고 나머지는 “문제 상황별 예제” catalog로
분리해 초보자 인터페이스를 복잡하게 만들지 않는다.

## 4. 판정과 후속

- `standardized_local_alpha`: trace matrix, core examples, negative matrix, clean packaging과 문서가 통과
- `quality_pending`: 실제 rubric/gold, exact on-prem Qwen, embedding/Vector DB가 없어 품질 주장을 못함
- `operational_no_go`: approved identity/upload/assignment/distributed infrastructure가 없음

감사 결과의 defect는 severity와 영향 WP/Gate를 기록하고, 수정 뒤 같은 example ID로 회귀한다.
