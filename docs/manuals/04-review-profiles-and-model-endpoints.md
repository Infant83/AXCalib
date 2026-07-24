# 심사 프로필과 모델 endpoint 사용법

AXCalib의 기본 사용 흐름은 작게 유지한다. 과제를 등록할 때 적용할 심사 프로필을 고정하고,
평가할 때는 project ID만 전달한다.

```python
from axcalib import AXCalib

axcalib = AXCalib.from_toml(
    "config/axcalib.toml",
    workspace="output/review",
)
case = axcalib.register_case(
    "proposal.pptx",
    title="AX 과제 제안",
    review_profile="axcalib.default@1.0.0",
)
axcalib.submit_registration(case.project_id)
draft = axcalib.evaluate(case.project_id, "registration")
```

`register_case(...)`는 최신 revision을 읽는 `Case`를 반환하는 권장 명칭이다. raw dossier snapshot이
필요한 기존 코드만 `create_project(...)` 또는 `case.dossier`를 명시적으로 사용한다.
기본 프로필은 synthetic/offline reference이므로 공식 합격선이나 AX 인증기준으로 사용하지 않는다.

## 사업별 기준 주입

전문 사용자는 `config/review_profiles`에 versioned policy YAML을 두고 runtime default 또는
`register_case(..., review_profile="policy.id@1.2.0")`로 명시한다. ID/version을 재사용해 내용을
바꾸면 registry가 hash collision으로 거부한다.

```python
from axcalib.schemas import ReviewContext

case = axcalib.register_case(
    "proposal.pptx",
    title="제조 AX 과제",
    review_profile="manufacturing.ax@2.1.0",
    review_context=ReviewContext(
        program_id="program-2026",
        business_unit_id="bu-manufacturing",
        certification_level="level-2",
    ),
)
```

`ReviewContext`는 감사와 명시적 정책 선택을 위한 metadata다. 현재는 소속·사업부·level을 prompt에
보내거나 자동으로 점수를 바꾸지 않는다. 자동 매핑이 필요하면 정책 owner가 별도의 versioned
mapping과 편향 검토를 승인해야 한다.

## 외부 OpenAI와 on-prem 호환 설정

live model은 명시적 opt-in이다.

```powershell
$env:OPENAI_API_KEY = "<secret>"
$env:OPENAI_MODEL = "gpt-5.5"  # 생략 시 이 외부 기본값
uv run --no-sync python scripts/pipelines/run_two_gate_pptx.py `
  tests/sources/oled_qc_project_outline.pptx `
  --proposal-sidecar tests/sources/oled_qc_project_outline.axcalib.json `
  --title "비식별 fixture 평가" `
  --workspace output/live-review `
  --docling `
  --live-model
```

on-prem OpenAI-compatible server는 같은 표면을 사용한다.

```powershell
$env:OPENAI_API_KEY = "<on-prem-secret-or-placeholder>"
$env:OPENAI_BASE_URL = "https://approved-model-gateway.example/v1"
$env:OPENAI_MODEL = "Qwen3.5-397B-A17B"
$env:OPENAI_API_MODE = "chat_completions"
$env:OPENAI_STRUCTURED_OUTPUT_MODE = "json_schema"
$env:OPENAI_MAX_OUTPUT_TOKENS = "8192"
```

사용자가 제안한 `OPENAPI_API_KEY`, `OPENAPI_BASE_URL`도 호환 alias로 읽지만 표준
`OPENAI_*`가 우선한다. API key 값은 dossier, report, log, fixture에 저장하지 않는다. base URL이
없으면 OpenAI 공식 endpoint와 Responses API를 사용하고, custom base URL은 기본적으로
Chat Completions dialect를 사용한다.

`OPENAI_STRUCTURED_OUTPUT_MODE`은 `json_schema` 또는 `json_object`를 명시한다. provider 오류가 나도
다른 dialect나 model로 자동 대체하지 않는다. 어느 mode에서도 model text는 Pydantic으로 다시
검증한다. `OPENAI_MAX_OUTPUT_TOKENS`는 긴 rubric 응답의 명시적 생성 한도이며 선택값과 실제 값은
secret이 아닌 run metadata로 남긴다.

`json_object`는 provider가 schema를 직접 강제하지 않는 dialect다. AXCalib gateway는 literal `JSON`,
contract name과 compact JSON Schema를 system instructions에 포함한 뒤에도 Pydantic/domain guard로
재검증한다. 이 계약이 없으면 일부 OpenAI-compatible endpoint는 upstream 400을 반환하고 proxy가
이를 500으로 감쌀 수 있다. 자세한 원인과 회귀는
[WP-05.Q2 복구 리포트](../evaluation/wp05-q2-skillboss-http500-recovery-report.md)를 따른다.

## Qwen3.5 배포 전 capability probe

on-prem 배포 전에는 실제 과제 대신 합성 text/image로 route를 검증한다.

```powershell
uv run --no-sync python scripts/pipelines/probe_qwen35_capabilities.py `
  --expected-checkpoint Qwen3.5-397B-A17B `
  --scope deployment `
  --output output/evaluation/qwen35-onprem-capability.json
```

`deployment_ready=true`가 되려면 structured text/vision뿐 아니라 endpoint가 반환한 model metadata도
exact checkpoint와 일치해야 한다. model metadata가 없거나 `qwen3.5-plus` 같은 alias이면 capability가
성공해도 deployment-ready가 아니다.

개인환경에서 SkillBoss를 사용할 때도 같은 script를 쓰되 일시적으로 SkillBoss key/base URL을
canonical 환경변수에 연결하고 `--scope provider_proxy`를 사용한다. 이 방식은 사전 호환성 확인일 뿐
제품 의존성이나 exact on-prem 검증이 아니다. 2026-07-21 상세 결과와 제한은
[Qwen3.5 capability validation report](../evaluation/qwen35-capability-validation-report.md)를 따른다.

## 대체 multimodal route 비교 probe

Qwen route 장애와 model-independent contract를 구분하려면 같은 canonical 환경변수로 공통 probe를
실행한다. 기본 `provider_proxy` scope는 text/vision이 모두 통과해도 운영 배포 승인을 뜻하지 않는다.

```powershell
$env:OPENAI_API_KEY = "<approved-proxy-secret>"
$env:OPENAI_BASE_URL = "https://approved-proxy.example/v1"
$env:OPENAI_MODEL = "<approved-multimodal-route>"
$env:OPENAI_API_MODE = "chat_completions"
$env:OPENAI_STRUCTURED_OUTPUT_MODE = "json_object"

uv run --no-sync python scripts/pipelines/probe_multimodal_capabilities.py `
  --scope provider_proxy `
  --output output/evaluation/multimodal-proxy-capability.json
```

실제 on-prem deployment 검증은 `--scope deployment --expected-model <exact-served-model-id>`를 함께
지정해야 한다. 대체 model 결과를 Qwen checkpoint identity 또는 평가품질 동등성으로 환산하지 않는다.

## 사람 수정 기록

관리자는 Agent report를 수정하지 않고 결정 시 criterion별 adjustment를 추가한다.

```python
from axcalib.schemas import Assessment, ReviewerAdjustment

axcalib.decide_registration(
    case.project_id,
    command="approve",
    actor_id="admin:reviewer-01",
    rationale="원문 근거와 보완자료를 사람이 재확인했다.",
    adjustments=(
        ReviewerAdjustment(
            criterion_id="REG-KPI",
            from_assessment=Assessment.INSUFFICIENT_EVIDENCE,
            to_assessment=Assessment.PARTIALLY_MET,
            reason="별도 승인된 KPI 산정표를 확인했다.",
        ),
    ),
)
```

실제 승인에서는 인증된 관리자 identity, 추가 근거 locator와 운영 RBAC가 필요하다. local actor는
`offline_unverified_actor`로 기록되며 공식 승인이 아니다.
