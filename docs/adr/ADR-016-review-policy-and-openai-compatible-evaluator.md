# ADR-016: Hash-bound review policy와 OpenAI-compatible evaluator

- Status: Accepted for the G3 reference implementation
- Date: 2026-07-16
- Decision owners: AXCalib product/evaluation owners pending formal rubric approval

## Context

등록심의와 완료평가의 기준은 사업 목적, 사업부, 제안자 소속, 인증 level에 따라 달라질 수
있다. 이 변동성을 Python 분기나 prompt 안에 숨기면 어떤 기준이 적용됐는지 재현하기 어렵고,
소속정보가 모델 판정에 직접 들어가 편향을 만들 수 있다. 동시에 첫 Library interface는
`register_case`와 `evaluate` 정도로 작아야 한다.

향후 on-prem Qwen3.5와 현재 외부 OpenAI API를 같은 application service에서 사용할 수 있어야
하지만, 모델은 HITL과 상태기계를 대체할 수 없다. 제공 PPTX는 image-only이므로 parser가
추출하지 못한 내용을 모델이 추측해서도 안 된다.

## Decision

1. 심사기준은 allowlisted `ReviewPolicyPack`으로 주입한다. selector는
   `policy_id@semver`이고 canonical validated JSON의 SHA-256을 dossier와 report에 고정한다.
2. 등록/완료 criterion, recommendation vocabulary, checklist와 reference metadata를 하나의
   policy pack에 넣는다. published 상태는 `approval_ref`가 없으면 로드하지 않는다.
3. 현재 `axcalib.default@1.0.0`은 `offline_reference`이며 운영 rubric이 아니다. 연결된 Markdown
   checklist도 content hash로 고정한다.
4. `ReviewContext`는 program/business unit/proposer organization/certification level을 감사용으로
   보존한다. G3에서는 context로 정책을 자동 선택하거나 model prompt에 넣지 않는다. 호출자가
   승인된 selector를 명시하거나 runtime default를 사용한다.
5. 사람 수정은 Agent report를 덮어쓰지 않고 `ReviewerAdjustment`로 별도 저장한다. criterion,
   원 판정, 수정 판정, 이유와 사람이 추가한 근거를 기록한다.
6. model evaluator는 strict structured output을 받고 policy criterion을 정확히 한 번씩 요구한다.
   존재하지 않는 slide locator는 terminal validation error다. locator 없는 met/partially_met/not_met
   판정은 `insufficient_evidence`로 하향하고 risk flag를 남긴다.
7. transport는 provider SDK에 종속되지 않는 작은 OpenAI-compatible adapter로 둔다. 환경변수
   우선순위는 `OPENAI_*` 후 호환 alias `OPENAPI_*`다. model 미지정 시 외부 기본값은
   `gpt-5.5`, on-prem expert 예시는 `Qwen3.5-397B-A17B`다.
8. OpenAI 공식 endpoint는 Responses API, 그 밖의 OpenAI-compatible base URL은 기본적으로
   Chat Completions structured-output dialect를 사용한다. 필요하면 `OPENAI_API_MODE`로 명시한다.
9. Docling은 optional extra다. parser run은 version, status, source hash, page/text coverage와 warning을
   report에 연결한다. zero-text 결과는 성공적인 의미 추출로 취급하지 않는다.
10. live model 호출은 기본 `prep.ps1 test|eval`에 포함하지 않는다. 사용자가 명시적으로 허용한
    비식별 fixture에서만 별도 opt-in으로 실행한다.

## Consequences

- 기준 변경은 새 version 또는 새 hash로 드러나며, 기존 dossier는 hash가 맞지 않으면 fail closed한다.
- 사업부/소속이 평가기준에 영향을 주는 경우 정책 책임자가 매핑 규칙과 차별 위험을 먼저 승인해야
  한다. G3 구현은 이 규칙을 암묵적으로 만들지 않는다.
- 외부 모델은 의미평가 초안을 만들 수 있지만, 관리자 알림과 HITL pending을 우회하지 못한다.
- 현재 adapter에는 retry, concurrency limiter, endpoint allowlist, usage/cost manifest와 capability
  probe가 없다. on-prem 운영 전 보강한다.
- 현재 lexical dataset은 작은 synthetic 회귀용이다. Vector DB, embedding과 실제 retrieval 품질을
  증명하지 않는다.

## Verification

- policy collision/status/hash/checklist drift unit tests와 workspace validation
- mock Responses/Chat Completions structured-output contract tests
- 두 Gate fake-model integration test와 관리자 결정 분리
- 제공 PPTX Docling contract test와 zero-text manifest
- 사용자 승인 하 비식별 fixture의 단일 live registration probe
