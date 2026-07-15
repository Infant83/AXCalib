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

`create_project(...)`는 호환 alias이고, 사용자 관점에서는 `register_case(...)`가 권장 명칭이다.
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
```

사용자가 제안한 `OPENAPI_API_KEY`, `OPENAPI_BASE_URL`도 호환 alias로 읽지만 표준
`OPENAI_*`가 우선한다. API key 값은 dossier, report, log, fixture에 저장하지 않는다. base URL이
없으면 OpenAI 공식 endpoint와 Responses API를 사용하고, custom base URL은 기본적으로
Chat Completions dialect를 사용한다.

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
