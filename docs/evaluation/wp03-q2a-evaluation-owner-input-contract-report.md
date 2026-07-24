---
document_type: development_evaluation_report
work_package: WP-03.Q2a
gate: G3 Intelligence quality input contract
date: 2026-07-24
status: local_contract_verified_official_benchmark_blocked
---

# WP-03.Q2a Evaluation Owner 입력계약 개발리포트

## 1. 결론

Evaluation Owner가 제공할 자료를 Markdown 하나가 아니라 다음 네 파일로 분리했다.

1. 사람이 검토·승인하는 `OWNER_APPROVAL.md`
2. 실행 가능한 두 Gate `review-policy.yaml`
3. project-stage별 criterion 정답인 `gold-labels.jsonl`
4. 위 세 파일의 version/hash와 threshold를 묶는 `benchmark-manifest.yaml`

draft package의 구조·hash는 실행 가능하지만 공식 품질 pass/fail은 만들지 않는다. 공식
`approved` package는 published policy, 숨겨 둔 test split의 registration/completion label, Owner threshold,
두 reviewer vote와 adjudication을 모두 요구한다. 따라서 현재 Q2a 입력·metric contract는
구현됐지만 실제 G3 quality benchmark는 Evaluation Owner 자료가 없어 계속 blocked다.

## 2. 산출물

| 구분 | 경로 | 역할 |
|---|---|---|
| 복사용 패키지 | `docs/evaluation/templates/evaluation-owner-package/` | Owner 작성 시작점 |
| Library | `src/axcalib/calibration/gold_benchmark.py` | schema, loader, hash/approval guard와 metric |
| Validator | `scripts/pipelines/validate_evaluation_owner_package.py` | draft/approved 검증과 hash 계산 |
| Runner | `scripts/pipelines/run_gold_benchmark.py` | immutable EvaluationReport JSON 비교 |
| JSON Schema | `docs/schemas/axcalib.gold-*.schema.json` 등 4종 | Draft 2020-12 계약 |
| Tests | `tests/unit/test_gold_benchmark.py`, integration owner-package test | drift/guard/metric 회귀 |

metric은 criterion assessment와 Agent recommendation accuracy, evidence locator precision/recall,
insufficient-evidence와 required-risk-flag recall, adjudication 전 reviewer agreement, 위험한
`pass`/`accept`와 unsupported-claim rate다. 이는 Agent 초안의 품질이며 사람 최종 인증결정이 아니다.
공식 리포트는 manifest가 고정한 `test` split만 계산해 development/validation label의 노출이
품질 통과값에 섞이지 않게 한다.

## 3. Evaluation Owner가 채워야 할 내용

### 3.1 Markdown

Markdown에는 적용 사업·과정·과제 유형, 제외범위, 데이터 등급, 외부전송 허용, 편향 위험,
reviewer/adjudicator와 승인 참조를 기록한다. YAML frontmatter는 package loader가 검증한다.

### 3.2 Review policy YAML

등록과 완료 criterion ID, critical/blocking 의미, required evidence tag, follow-up,
recommendation vocabulary와 reference hash를 선언한다. 공식 package에서는 status가 `published`이고
`approval_ref`가 있어야 한다.

### 3.3 Gold JSONL

비식별 `project_id + stage`마다 policy criterion을 정확히 한 번 포함한다. substantive assessment는
`pptx://slide/{n}`, report 또는 artifact hash locator를 사용한다. 공식 label은 두 명 이상의
pre-adjudication vote와 `adjudication_ref`를 가진다. final administrator certification command가
아니라 기대 Agent finding을 label한다.

### 3.4 Manifest

policy canonical hash, labels/approval byte hash, case count와 Owner threshold를 기록한다. 작성
순서는 policy → labels → approval → manifest다. `--hashes-only`는 수정 중인 package의 현재 hash를
계산하고, 최종 validator는 manifest와 실제 파일이 일치해야 통과한다.

## 4. Gold benchmark 진행 가능 여부

**가능하지만 지금 공식 결과를 만들 수는 없다.**

- 지금 가능한 것: template 복사, draft validation, synthetic metric 회귀, report runner 준비
- Owner 자료 후 가능한 것: approved package validation, model별 양 Gate report 비교, defect 분석
- 아직 금지: example policy를 공식 rubric으로 승격, 구현자가 threshold/정답 생성, test split을
  prompt 선택에 사용, provider alias 결과를 exact deployment 품질로 기록

첫 공식 실행은 최소한 registration/completion, 긍정·비긍정·insufficient 경계와 위험한 자동 긍정
사례를 포함해야 한다. 표본 수와 class balance는 실제 업무 위험과 가용 label을 Owner가 확인한 뒤
별도 baseline으로 고정한다.

## 5. Docling을 Q1 closeout에서 재실행하지 않은 이유

Q1은 Case/readability와 example 표준화 변경이었고 parser code를 바꾸지 않았다. Docling은 이미
제공 image-only PPTX에서 2.113.0, 16 page, text page 0이라는 별도 contract 증거가 있었다. 기본
회귀에 포함하면 이전 세션처럼 저메모리 환경에서 Python/Docling/Pyright가 함께 메모리를 사용해
전체 검증이 중단될 수 있어 lazy optional adapter와 별도 `prep.ps1 docling` 원칙을 유지했다.

이번 실행에서는 Docling 2.113.0 설치를 확인했지만 가용 물리 메모리가 1,368MB였다. 새 2,048MB
preflight가 실제 파싱 전에 `BLOCKED_RESOURCE`로 종료했다. 이는 Docling 미설치나 parser assertion
실패가 아니다. harness에는 300초 watchdog도 추가했다. 메모리 확보 후 같은 격리 명령을 다시
실행하면 된다.

## 6. SkillBoss/Qwen 현재 진단

### 6.1 확인 결과

| 항목 | 결과 |
|---|---|
| API key | `skb whoami` valid; 값은 저장소·리포트에 기록하지 않음 |
| npm CLI | 설치 0.1.4, npm latest 0.1.4 |
| CLI 표시 | source에 0.1.0 hard-code가 있어 표시 불일치 |
| 공개 skill pack | 공식 GitHub main `5e3dc200...`; 설치 SKILL hash가 기존 검증값과 동일 |
| updater | 공개 repository와 설치본 모두 `install/update.sh` 없음 |
| catalog | `bailian/qwen3.5-plus`, `bailian/qwen3.5-flash`; exact 397B 없음 |
| live smoke | Plus synthetic JSON 성공, response model `qwen3.5-plus` |
| call 규모 | 42 prompt, 467 completion, 509 total tokens; USD 0.00133 |
| account | CLI `/api/me/balance` 경로 HTTP 404 |
| update metadata | server는 current unknown/latest 1.1.0과 존재하지 않는 updater 경로를 반환 |

live smoke의 content JSON은 정상이고 provider 접근 제한은 해소됐다. raw CLI 응답에는
`reasoning_content`가 포함됐지만 비식별 합성 요청이며 repository artifact에는 저장하지 않았다.
AXCalib product probe는 기존대로 reasoning을 report에 보존하지 않는다.

### 6.2 해결·남은 경계

- **해결됨:** authentication, dynamic catalog와 Qwen3.5 Plus model call은 정상이다.
- **우회 확정:** broken `account/update` command는 품질실행 경로에서 사용하지 않는다.
- **공급자 수정 필요:** public latest보다 높은 1.1.0 skill metadata, updater 부재와 account 404는
  로컬 재설치로 해결할 수 없다. 실제 npm/public repository는 이미 최신이다.
- **제품 독립성:** AXCalib와 on-prem script는 계속 `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
  `OPENAI_MODEL`만 사용한다.
- **미해결:** SkillBoss에는 exact `Qwen3.5-397B-A17B`가 없으므로 해당 checkpoint 품질은 사내
  on-prem endpoint에서만 검증할 수 있다.

## 7. 품질 주장 경계

이번 slice는 Owner 입력·hash·metric 계산 계약과 Qwen proxy connectivity를 검증했다. 공식 rubric,
Owner gold label, exact on-prem Qwen, 일반 PPTX semantic parsing/VLM 정확도, retrieval 또는 실제
사내 인증 품질을 검증한 것은 아니다. 관리자 HITL은 계속 필수다.

## 8. 코드리뷰와 검증

코드리뷰에서 label의 split 값은 존재하지만 공식 계산 split이 고정되지 않은 결함을 발견했다.
manifest에 `evaluation_split`을 추가하고 approved package는 `test`만 허용했으며, runner도 해당
split의 두 Gate report만 정확히 받도록 수정했다. 또한 WORK_SPEC의 중복 FR-060을 FR-060~062로
정정하고 report directory의 symlink 입력을 거부했다.

| 검증 | 결과 |
|---|---|
| draft validator + hash 출력 | valid, label 2, official executable false |
| synthetic approved package + test split/zero-denominator/resource guard | targeted 총 16 passed |
| split full test | 189 passed: unit 131, integration 37(9/22/6), contract 21 |
| offline eval | 10 groups passed |
| generated JSON Schema | drift 없음 |
| Ruff | repository lint 통과; 변경 Python 9개 format 통과 |
| Pyright | 0 errors, 0 warnings |
| workspace validate | 0 errors, 0 warnings |
| workflow SVG | 1,600×1,100 PNG 렌더 육안 검토; clipping 없음 |
| Docling current run | 1,368MB < 2,048MB, parse 전 `BLOCKED_RESOURCE` |
| SkillBoss live | Qwen3.5 Plus synthetic JSON 성공; exact 397B 아님 |

## 9. 다음 단계

Evaluation Owner가 template을 복사해 published policy, 승인 Markdown, threshold와 숨겨 둔 test split의
adjudicated registration/completion label을 제공하면 Q2b를 시작한다. 같은 snapshot/policy에서 만든
exact on-prem Qwen 및 비교 model EvaluationReport를 runner에 넣고 criterion confusion, 위험한
긍정, unsupported claim과 locator failure를 분석한다. 자료가 오기 전에는 공식 G3 quality
pass/fail을 생성하지 않는다.
