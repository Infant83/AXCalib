# ADR-019: JSON object contract와 model-independent multimodal probe

- 상태: Accepted
- 날짜: 2026-07-22
- 관련 결정: D-021, D-022, D-031, D-032
- 관련 WP: WP-05.Q2

## Context

SkillBoss의 `qwen3.5-plus` OpenAI-compatible route에서 AXCalib full registration 요청이 HTTP 500으로
실패했다. 같은 endpoint의 짧은 structured text와 vision probe는 성공했다. 최소 재현 결과,
`response_format.type=json_object`인데 message 어디에도 literal `JSON`이 없을 때 upstream은
HTTP 400 `invalid_parameter_error`를 반환했고 SkillBoss가 이를 HTTP 500으로 감쌌다.

`JSON` 단어만 추가하면 transport는 성공했지만, `json_object` dialect는 JSON Schema를 직접 강제하지
않으므로 model이 AXCalib와 다른 field name을 반환했다. transport 성공을 structured-output 성공으로
간주할 수 없었다. Qwen 외 model을 비교할 때도 provider alias를 exact deployment로 오인하지 않는
공통 probe가 필요했다.

## Decision

1. `json_schema`와 `json_object` 선택은 계속 명시적이며 실패 시 다른 dialect/model로 조용히
   fallback하지 않는다.
2. `json_object` mode의 gateway는 system instructions에 literal `JSON`, contract name과 compact
   canonical JSON Schema를 자동 포함한다. Markdown wrapper와 schema 밖 property를 금지한다.
3. 모든 model output은 dialect와 무관하게 Pydantic으로 재검증한다. field 누락·추가, criterion set,
   locator 위반은 성공으로 바꾸지 않는다.
4. proxy가 `detail="Failed: <status> {...}"` 형태로 upstream 오류를 감싸면 status/type/code/param처럼
   allowlisted identifier만 추출한다. server message, evidence, prompt와 secret은 예외에 포함하지 않는다.
5. 공통 `MultimodalCapabilityProbe`와 canonical-env script를 제공한다. 기본 scope는
   `provider_proxy`이며 이 scope는 exact model name이 일치해도 `deployment_ready=false`다.
6. Qwen 전용 entrypoint는 `Qwen35CapabilityProbe` compatibility name과 exact checkpoint guard를
   유지한다. 대체 model 성공은 Qwen deployment 증거가 아니다.

## Consequences

- SkillBoss Qwen Plus의 supplied-fixture registration은 strict output validation, report, notification과
  `registration_hitl_pending`까지 실행된다.
- `json_object` request는 schema text만큼 커지지만 provider validation requirement와 output contract가
  명시적이다.
- GPT-4o proxy text/vision과 registration 성공은 대체 검증 경로의 증거일 뿐 on-prem 운영 승인이나
  model 품질 동등성을 의미하지 않는다.
- GLM 4.5V proxy는 text만 통과하고 vision gateway가 실패했으므로 multimodal fallback으로 승격하지
  않는다.
- exact `Qwen3.5-397B-A17B`, completion full rubric, approved gold/human agreement는 계속 pending이다.

