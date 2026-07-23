# 설정과 On-prem 모델

## 설정 계층

설정 우선순위는 코드 소유 불변조건, 안전 기본값, TOML profile, 환경변수, allowlisted request option,
policy guard 순이다. 관리자 HITL, notification, 사람 최종결정, stale/revision guard와 mentor guard는
TOML이나 JSON으로 끌 수 없다.

- 기본 사용자: `config/axcalib.toml`
- 전문 사용자: `config/axcalib.expert.example.toml`을 복사해 allowlisted profile 구성
- unknown key: 조용히 무시하지 않고 validation error

## OpenAI-compatible 환경변수

외부 OpenAI 또는 사내 OpenAI-compatible gateway는 같은 환경변수 계약을 사용한다.

```powershell
$env:OPENAI_API_KEY = "<secret>"
$env:OPENAI_BASE_URL = "https://approved-endpoint.example/v1"
$env:OPENAI_MODEL = "Qwen3.5-397B-A17B"
```

사내 on-prem 목표 모델은 `Qwen3.5-397B-A17B`다. model ID는 코드에 고정하지 않고
`OPENAI_MODEL`로 주입한다. endpoint capability는 모델 이름으로 추정하지 않고 `/models`, 최소 text,
structured output, multimodal probe를 승인된 비식별 fixture로 확인한다.

## Live model opt-in

```python
from axcalib import AXCalib

client = AXCalib.from_toml(
    "config/axcalib.toml",
    workspace="output/onprem-probe",
    live_model=True,
)
```

`live_model=True`는 외부 전송 동의와 같은 뜻이 아니다. 호출 전 endpoint Owner, 데이터 등급, 원문
전송범위와 비용을 별도로 승인해야 한다. API key 값은 YAML, fixture, 로그, report, Git에 기록하지 않는다.

## Docling

Docling은 optional extra다. 기본 core import와 일반 test는 Docling을 강제로 로드하지 않는다.

```powershell
uv sync --frozen --extra docling
.\prep.ps1 docling
```

메모리 부족이나 parser 장애가 전체 Library를 중단시키지 않도록 별도 process contract로 검증한다.
필요하면 OOXML 기반 제한형 parser와 sidecar evidence를 offline fallback으로 사용하되 OCR/VLM 품질을
주장하지 않는다.

## Retrieval

offline baseline은 lexical adapter와 similarity portion `0.0`이다. portion이 0보다 큰데 adapter나
corpus가 없으면 다른 점수로 조용히 재분배하지 않는다. 실제 dense/Vector DB는 승인된 corpus,
embedding/chunk version, stage filter와 retrieval benchmark 뒤에 승격한다.

보안 설정은 [보안과 HITL](Security-and-HITL), 실제 코드 예제는 [예제와 Recipe](Examples-and-Recipes)를
참고한다.
