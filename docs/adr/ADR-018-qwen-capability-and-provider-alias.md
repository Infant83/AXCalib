# ADR-018: Qwen capability와 provider alias 경계

- 상태: Accepted
- 날짜: 2026-07-21
- 관련 결정: D-021, D-022, D-031
- 관련 WP: WP-05.Q1

## Context

실제 on-prem 실행은 `Qwen3.5-397B-A17B`를 사용할 예정이지만 개인 개발환경의 SkillBoss는
`bailian/qwen3.5-plus` route만 노출한다. marketing/service alias를 exact checkpoint와 동일시하면
검증 대상이 바뀌고도 deployment-ready로 잘못 승격될 수 있다. 또한 provider별 structured-output
dialect 지원 범위가 다르며 응답에는 보존해서는 안 되는 `reasoning_content`가 포함될 수 있다.

## Decision

1. AXCalib 제품과 on-prem script는 SkillBoss에 의존하지 않고 OpenAI-compatible port와 canonical
   `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`을 사용한다.
2. `provider_proxy` capability와 `deployment` validation scope를 분리한다.
3. exact checkpoint 확인은 요청 model, endpoint가 실제 반환한 response model, expected checkpoint가
   명시적 identifier 비교를 모두 통과할 때만 true다. 알려지지 않은 alias mapping은 추측하지 않는다.
4. `json_schema`와 `json_object` dialect, output token limit는 명시적으로 선택·기록한다. 실패 후
   조용한 dialect/model fallback은 허용하지 않는다.
5. probe report에는 raw prompt/image/output, API key, 숨은 reasoning을 저장하지 않는다. hash,
   identity metadata, latency, safe failure kind와 validation status만 보존한다.
6. capability 성공은 task quality나 사람 승인과 별개다. full rubric/gold/HITL Gate를 우회하지 않는다.

## Consequences

- SkillBoss는 개발자의 선택적 외부 검증 경로로 사용할 수 있지만 on-prem 설치 요구사항이 아니다.
- `qwen3.5-plus` 성공은 `Qwen3.5-397B-A17B` 성공으로 보고되지 않는다.
- endpoint가 response model을 생략하면 client가 requested model을 fallback display하더라도 identity는
  unconfirmed다.
- exact on-prem endpoint가 준비되기 전에는 WP-05 deployment quality와 G3 quality Gate가 pending이다.
- provider payload 실패는 성공으로 변환하지 않고 후속 telemetry/reconciliation에서 safe audit한다.

