# WP-05.Q2 SkillBoss HTTP 500 복구·멀티모달 비교 개발리포트

- 날짜: 2026-07-22
- 범위: SkillBoss update, Qwen proxy HTTP 500 원인분석, structured-output 복구, 대체 multimodal probe
- Gate 경계: G3 Intelligence quality evidence 일부; exact on-prem·공식 평가품질은 미완료

## 1. 결론

HTTP 500의 직접 원인은 payload 크기나 한국어, 7개 criterion이 아니었다. AXCalib가
`response_format={"type":"json_object"}`를 사용하면서 message에 literal `JSON`을 넣지 않았고,
upstream이 반환한 400 `invalid_parameter_error`를 SkillBoss가 500으로 wrapping했다.

gateway가 JSON keyword와 compact schema contract를 주입하도록 고친 뒤 같은 supplied PPTX의 Qwen
registration은 85.4초에 성공했다. 7개 criterion을 검증하고 report와 notification 1건을 만든 다음
사람 결정을 기다리는 `registration_hitl_pending`에서 멈췄다. Agent가 승인 상태를 확정하지 않았다.

## 2. SkillBoss 업데이트 결과

| 항목 | 결과 |
|---|---|
| CLI package | 공식 npm 최신 `@skillboss/cli 0.1.4` 재설치 |
| CLI 표시 | `skb --version`은 코드에 고정된 `v0.1.0`을 계속 표시; package metadata와 불일치 |
| skill pack | `SkillBoss-AI/skillboss-skills` main SHA `5e3dc20026722d9d8fb1d8fd81dfac2e52e29269` |
| installed SKILL SHA-256 | `578511c82eb5013e8e22c2403bf99d7ddd219ea8ca39173b92f256e435934bf7` |
| rollback | 기존 pack은 사용자 skill root의 dated backup으로 보존 |
| updater defect | server가 안내하는 `skillboss/install/update.sh`는 최신 공식 repository에도 없음 |
| warning defect | CLI/direct HTTP가 skill version header를 보내지 않아 server는 최신 pack 설치 뒤에도 `current: unknown` 표시 |

API key 값, raw prompt/image/output와 model reasoning은 이 저장소·report에 기록하지 않았다.

## 3. 원인 분리 증거

| 대조군 | 요청 | 결과 | 해석 |
|---|---:|---|---|
| simple text | 99 bytes | HTTP 200 | route/auth 정상 |
| AX shape, 1 synthetic criterion | 416 bytes | HTTP 200 | content array와 `json_object` 자체 정상 |
| 7 criteria + 13 synthetic slides | 3,286 bytes | HTTP 200, 90.2s | criterion 수·기본 크기 원인 아님 |
| actual fixture ACK | 2,973 bytes | HTTP 200, 17.8s | supplied evidence 내용 차단 아님 |
| 최소 실패 | 248 bytes, `json_object`, JSON keyword 없음 | HTTP 500, 2.9s | 크기와 무관 |
| 최소 실패의 wrapped detail | upstream 400, `invalid_request_error` / `invalid_parameter_error` | 확인 | message에 `json` 요구 |
| actual 1 criterion + explicit JSON | transport HTTP 200 | 임의 field로 Pydantic 실패 | keyword만으로 schema 품질은 해결 안 됨 |

## 4. 구현

### 4.1 JSON object dialect

`OpenAICompatibleClient`는 `json_object` mode일 때 다음을 system instructions에 붙인다.

- 정확히 하나의 JSON object 반환
- contract name
- canonical compact JSON Schema
- Markdown wrapper와 additional property 금지

model text는 계속 `ModelReviewOutput`과 domain locator guard로 검증된다. 유효하지 않은 응답을
repair하거나 성공으로 처리하지 않는다.

### 4.2 안전한 오류 진단

SkillBoss처럼 upstream JSON을 top-level `detail` string에 감싸는 응답을 파싱한다. 예외에는
`upstream_status`, `type`, `code`, `param` 중 안전한 identifier만 포함한다. server message와 evidence는
버린다.

### 4.3 모델 독립 multimodal probe

`MultimodalCapabilityProbe`와 `probe_multimodal_capabilities.py`를 추가했다. canonical
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`만 사용하며 기본 scope는 `provider_proxy`다.
deployment scope는 `--expected-model`을 필수로 요구한다.

## 5. Live 결과

| route | structured text | synthetic vision | supplied-fixture registration | 경계 |
|---|---|---|---|---|
| SkillBoss Qwen3.5 Plus | passed, 12,415ms | passed, 10,415ms | passed, model latency 77,724ms | alias; exact 397B 아님 |
| SkillBoss GPT-4o | passed, 2,650ms | passed, 2,460ms | passed, model latency 7,121ms | alternate provider proxy |
| SkillBoss GLM 4.5V | passed, 5,688ms | gateway error | 미실행 | text-only 비교 후보 |

Qwen과 GPT-4o registration은 모두 7 criteria, `needs_changes`, notification 1건,
`registration_hitl_pending`을 만들었다. assessment count가 같았다는 사실만 확인했으며 판단 문구·근거의
동등성, agreement 또는 품질 우위를 주장하지 않는다.

## 6. 코드리뷰

| 위험 | 검토 | 처리 |
|---|---|---|
| provider 전용 workaround | gateway dialect 계약으로 구현 | 특정 SkillBoss import 없음 |
| silent fallback | model/dialect 자동 교체 없음 | explicit config 유지 |
| invalid JSON 성공 처리 | Pydantic + criterion/locator guard | fail-closed 유지 |
| proxy를 deployment로 오인 | provider scope에서는 deployment false | unit/eval 회귀 추가 |
| raw reasoning/secret 보존 | report에는 hash·model·latency만 | raw field 없음 확인 |
| 실패 원인 노출 시 evidence leakage | allowlisted identifier만 추출 | wrapped message 미노출 test |

## 7. 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_model_gateway.py -q
.\.venv\Scripts\python.exe -m pytest tests\unit\test_model_capability.py tests\integration\test_qwen_capability_script.py -q
.\.venv\Scripts\python.exe evals\qwen_capability_contract.py
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 eval
```

Live 호출은 기본 test/eval에 포함하지 않는다. 실행 report는 `output/` 아래 ignore 대상이며 source control
산출물이 아니다.

최종 회귀 결과는 `prep test` 79 passed, `prep eval` 8 groups passed, `prep validate` 0 errors/0
warnings다. Ruff는 통과했고 Pyright는 0 errors/0 warnings였다. `git diff --check -- .`에는 whitespace
오류가 없었고 기존 CRLF 변환 안내만 있었다.

## 8. 남은 작업

1. exact on-prem `Qwen3.5-397B-A17B`에서 text/vision, registration/completion과 serving fingerprint 확인
2. approved gold/human label로 unsupported claim, agreement, latency/cost 평가
3. model failure safe audit event와 retry/journal reconciliation
4. SkillBoss CLI version 표시·updater path·upstream status mapping은 공급자 측 수정 필요
