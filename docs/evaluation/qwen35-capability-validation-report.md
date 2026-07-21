---
document_type: development_and_validation_report
work_package: WP-05.Q1
status: partial_proxy_verified_exact_checkpoint_pending
date: 2026-07-21
---

# Qwen3.5 capability validation report

## 1. 결론

AXCalib의 Qwen 검증 경로는 **SkillBoss 비의존 OpenAI-compatible script**로 구현했다. on-prem에서는
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`만 바꾸어 같은 script를 실행한다. 현재 개인환경의
SkillBoss 동적 catalog에는 exact `Qwen3.5-397B-A17B` ID가 없고
`bailian/qwen3.5-plus`만 확인되므로, 아래 live 결과는 **provider proxy capability evidence**이지
397B-A17B deployment 검증이 아니다.

공식 모델 카드는 `Qwen/Qwen3.5-397B-A17B`를 native multimodal image-text-to-text checkpoint로
명시한다. exact on-prem 검증은 endpoint가 요청·응답 metadata에 이 checkpoint ID를 명시하고 아래
deployment scope probe를 통과할 때만 완료로 승격한다.

## 2. 구현 계약

- 제품 코드는 SkillBoss package나 API key 이름을 import하지 않는다.
- live probe는 canonical `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`을 모두 명시해야 한다.
- `provider_proxy`와 `deployment` scope를 분리한다. alias capability 성공은
  `deployment_ready=false`다.
- endpoint가 response `model`을 실제로 반환해야 route identity를 확인한다. client fallback 문자열은
  identity 증거로 사용하지 않는다.
- 구조화 출력 dialect는 `json_schema` 또는 `json_object`를 명시적으로 선택한다. 실패 시 다른
  dialect로 자동 재시도하지 않는다.
- 응답 원문과 `reasoning_content`는 report에 저장하지 않고 request/response hash, model metadata,
  latency와 validation status만 보존한다.
- 합성 vision probe는 dependency-free red-left/blue-right PNG를 사용한다. 실제 제출자료나 개인정보를
  capability probe에 넣지 않는다.

주요 진입점은 다음과 같다.

- Library: `Qwen35CapabilityProbe`
- Script: `scripts/pipelines/probe_qwen35_capabilities.py`
- Offline eval: `evals/qwen_capability_contract.py`
- Contract test: `tests/integration/test_qwen_capability_script.py`

## 3. SkillBoss 개인환경 결과

### 3.1 catalog와 최소 smoke

| 항목 | 결과 |
|---|---|
| exact `Qwen3.5-397B-A17B` catalog ID | 찾지 못함 |
| 사용 가능한 route | `bailian/qwen3.5-plus` |
| `--no-fallback` 고정 JSON smoke | 성공 |
| endpoint response model | `qwen3.5-plus` |
| exact checkpoint identity | 미확인 |

### 3.2 AXCalib capability script

`provider_proxy` scope에서 structured text와 synthetic vision이 모두 통과했다.

| Check | 결과 | 관측 latency |
|---|---:|---:|
| structured text | passed | 20,628 ms |
| structured vision | passed | 9,436 ms |
| route identity | confirmed: `qwen3.5-plus` |
| expected checkpoint | not confirmed: `Qwen3.5-397B-A17B` |
| deployment ready | false |
| hidden reasoning retained | false |

machine report는 ignored local output
`output/evaluation/qwen35-skillboss-proxy-capability.json`에 생성했다. secret, prompt, image와 model
output 본문은 포함하지 않는다.

### 3.3 실제 등록심의 schema smoke

제공된 비식별 test PPTX의 hash-bound reviewed sidecar text로 등록심의 1 Gate를 시도했으나
SkillBoss OpenAI-compatible 경로는 다음 세 설정 모두 HTTP 500을 반환했다.

1. `json_schema`, output limit 미지정
2. `json_object`, output limit 미지정
3. `json_object`, `OPENAI_MAX_OUTPUT_TOKENS=8192`

로컬 request 계측은 `json_schema` 5,253 bytes, `json_object` 4,242 bytes, prompt 2,867자,
criterion 7개였다. 같은 endpoint의 짧은 한국어 `json_object` 요청은 40,483 ms에 성공했다. 따라서
접근 불가, 단순 request size, 한국어, 단순 output-limit 문제로 단정할 수 없으며, 현재 증거로는
SkillBoss route의 full rubric payload/provider 처리 실패로만 기록한다. 서버 원문 오류를 report에
노출하지 않았고 자동 fallback도 수행하지 않았다.

실패 실행은 관리자 HITL이나 승인 상태로 전이하지 않았지만, model invocation failure 자체를 audit
event로 남기지 않는 현재 gap도 확인했다. 이는 WP-01.R1 transaction/reconciliation과 WP-05 error
telemetry 후속 범위다.

### 3.4 2026-07-22 후속 원인확정과 복구

위 3.3은 당시 실패 관측 기록이다. 후속 최소 재현에서 `json_object` message에 literal `JSON`이
없으면 upstream이 400 `invalid_parameter_error`를 반환하고 SkillBoss가 이를 HTTP 500으로 감싸는
것을 확인했다. payload 크기나 한국어가 원인이 아니었다.

gateway가 JSON keyword와 compact schema contract를 자동 주입하도록 보강한 뒤 같은 supplied
fixture registration이 통과했다. 7개 criterion, report, notification 1건을 만들고
`registration_hitl_pending`에서 멈췄다. 상세 증거와 대체 model 비교는
[WP-05.Q2 복구 리포트](wp05-q2-skillboss-http500-recovery-report.md)에 있다.

## 4. on-prem 실행 계약

PowerShell 예시는 다음과 같다.

```powershell
$env:OPENAI_API_KEY = "<on-prem-secret-or-placeholder>"
$env:OPENAI_BASE_URL = "https://approved-qwen-gateway.example/v1"
$env:OPENAI_MODEL = "Qwen3.5-397B-A17B"
$env:OPENAI_API_MODE = "chat_completions"
$env:OPENAI_STRUCTURED_OUTPUT_MODE = "json_schema"
$env:OPENAI_MAX_OUTPUT_TOKENS = "8192"

uv run --no-sync python scripts/pipelines/probe_qwen35_capabilities.py `
  --expected-checkpoint Qwen3.5-397B-A17B `
  --scope deployment `
  --output output/evaluation/qwen35-onprem-capability.json
```

처음 세 환경변수는 필수다. 나머지는 endpoint capability에 맞춘 명시적 전문 설정이다.
`deployment_ready=true`는 exact model metadata와 text/vision structured contract를 뜻할 뿐, 과제
심사 품질을 뜻하지 않는다.

## 5. 코드리뷰와 남은 Gate

| 우선순위 | 발견사항 | 조치/상태 |
|---|---|---|
| High | exact 397B-A17B endpoint가 없어 실제 deployment 검증 불가 | on-prem endpoint 제공 후 deployment probe 필수 |
| Closed proxy / High deployment | SkillBoss proxy full registration이 JSON-mode contract 누락으로 HTTP 500 | WP-05.Q2에서 원인·복구; exact on-prem registration/completion은 계속 재검증 필요 |
| Medium | 현재 full evaluator는 sidecar/text를 보내며 slide pixel을 VLM에 연결하지 않음 | M03→M05 multimodal evidence bundle slice 필요 |
| Medium | 실패한 model invocation의 safe audit event가 없음 | WP-01.R1/WP-05 telemetry에 request hash·failure kind 기록 |
| Medium | response model string만으로 serving engine/model revision을 증명하기 어려움 | model card, serving engine/version, deployment fingerprint 추가 |
| Pass | canonical env, alias 분리, no-fallback, Pydantic validation, no-CoT retention | unit/integration/eval 회귀로 고정 |

WP-05.Q1의 **harness와 provider-proxy capability 부분은 완료**됐고 Q2에서 proxy registration도
복구했다. exact on-prem checkpoint와 full completion·gold 품질은 미완료다. G3 Intelligence quality
Gate는 계속 pending이다.

## 6. 품질 주장 경계

이 결과는 Qwen3.5 Plus provider route의 text/vision 최소 capability와 AXCalib transport contract를
보여 준다. `Qwen3.5-397B-A17B`의 정확도, 공식 심의 일치도, PPT 시각 이해, hallucination rate,
calibration, 처리량 또는 비용을 검증하지 않았다. Agent 결과는 어떤 경우에도 관리자 HITL을
대체하지 않는다.

## 7. 참고

- [Qwen/Qwen3.5-397B-A17B official model card](https://huggingface.co/Qwen/Qwen3.5-397B-A17B)
- [ADR-018: Qwen capability and provider alias boundary](../adr/ADR-018-qwen-capability-and-provider-alias.md)
