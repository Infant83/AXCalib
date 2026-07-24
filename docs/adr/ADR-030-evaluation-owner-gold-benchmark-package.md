# ADR-030: Evaluation Owner gold benchmark package

- Status: Accepted for WP-03.Q2 input contract
- Date: 2026-07-24
- Decision owner: AXCalib engineering; business thresholds and labels remain Evaluation Owner decisions

## Context

현재 offline review policy와 actual-PPT locator gold는 구조·근거 추적성을 검증하지만, Agent가
공식 심사자 판단과 얼마나 일치하는지는 증명하지 않는다. Markdown만 받으면 사람이 읽기는 쉽지만
criterion ID, 정답 label, source hash와 threshold를 자동 검증하기 어렵다. 반대로 JSON 하나에
모든 내용을 넣으면 정책 의도와 승인 책임을 검토하기 어렵다.

구현자가 임의 threshold나 기대 합격결과를 만들면 benchmark 자체가 편향되고 공식 심사정책을
대신 확정하는 문제가 생긴다.

## Decision

1. Owner 입력은 승인 Markdown, review-policy YAML, gold-label JSONL과 manifest YAML로 분리한다.
2. manifest는 policy의 canonical validated SHA-256과 labels/approval 원본 byte SHA-256을 고정한다.
3. `draft`, `offline_reference`, `approved`, `retired`를 구분한다. 기본 loader는 `approved`만
   benchmark 실행 대상으로 허용한다.
4. 공식 package는 published policy, Owner approval reference·시각, Owner threshold, registration과
   completion label, 두 reviewer 이상의 vote와 adjudication을 모두 요구한다.
5. 공식 pass/fail은 manifest에 고정한 숨겨진 `test` split만 계산한다. development/validation label을
   test quality 결정에 섞지 않는다.
6. substantive assessment는 안정적인 `pptx://slide/{n}`, report 또는 artifact hash locator를
   가져야 한다. 로컬 파일경로는 gold에 저장하지 않는다.
7. quality report는 assessment/recommendation agreement, locator precision/recall,
   insufficient-evidence 및 risk-flag recall, reviewer agreement, 위험한 긍정 제안과 unsupported
   claim을 측정한다. metric 분모를 기록하고 insufficient/risk/비긍정 사례가 0인 approved
   benchmark는 해당 threshold를 통과시키지 않는다.
8. non-approved package는 metric smoke를 명시적으로 실행할 수 있어도 공식 pass/fail을 반환하지
   않는다.
9. benchmark 결과는 Agent 평가초안 품질이며 관리자 최종 인증결정이 아니다.

## Consequences

- Evaluation Owner가 무엇을 제공해야 하는지 명확하고 복사 가능한 패키지가 생긴다.
- label 또는 policy 수정 뒤 hash를 갱신하지 않으면 실행이 닫힌다.
- official benchmark 이전에도 schema, validator와 metric 계산을 synthetic/offline으로 회귀할 수
  있다.
- 첫 공식 baseline은 아직 Owner rubric, threshold, 비식별 label과 exact-model report를 받아야
  하므로 G3 quality는 계속 pending이다.
- pre-adjudication vote를 보존하므로 gold 자체의 사람 간 일치도를 함께 감사할 수 있다.
