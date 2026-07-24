# On-prem Qwen 실행 검증

이 문서는 사내 OpenAI-compatible gateway에서 `Qwen3.5-397B-A17B`를 AXCalib와 연결할 때의
최소 검증 절차다. SkillBoss나 외부 provider SDK를 제품 실행경로에 사용하지 않는다.

첫 실행은 회사 문서가 아니라 저장소의 비식별 테스트 PPTX와 합성 text/image만 사용한다.

## 확인 범위

아래 순서로 실패 원인을 분리한다.

1. 저장소·의존성·offline contract
2. exact Qwen route, structured output와 synthetic vision
3. 테스트 PPTX 등록심의와 관리자 HITL 대기
4. 충분한 메모리가 있을 때 optional Docling

이 검증은 endpoint transport와 AXCalib workflow 연결을 확인한다. 공식 rubric 일치도, 환각률,
사람 평가자 agreement 또는 과제 심사 품질을 증명하지 않는다.

## 1. 저장소와 기준선

처음 받는 경우 다음처럼 clone한다. 사내 GitLab mirror를 사용한다면 첫 URL만 사내 주소로 바꾸고
`git rev-parse HEAD` 결과를 함께 기록한다.

```powershell
git clone https://github.com/Infant83/AXCalib.git
cd AXCalib
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
python --version
uv --version
```

Python 3.12 이상과 `uv`가 필요하다. 사내망에서 외부 package index를 쓸 수 없다면 승인된 Python
mirror를 먼저 설정한다.

```powershell
uv sync --locked --dev --extra cli
uv run --no-sync python -m harness.prep validate
uv run --no-sync python -m harness.prep test integration-eval
```

긴 전체 test보다 관련 shard를 먼저 실행한다. 이 단계는 network, GPU 또는 API key를 사용하지 않는다.

## 2. 환경변수

표준 이름은 `OPENAI_*`다. `OPENAPI_*` 호환 alias보다 표준 이름을 우선한다.

PowerShell:

```powershell
$env:OPENAI_API_KEY = "<사내 게이트웨이 키>"
$env:OPENAI_BASE_URL = "https://<사내-Qwen-gateway>/v1"
$env:OPENAI_MODEL = "Qwen3.5-397B-A17B"
$env:OPENAI_API_MODE = "chat_completions"
$env:OPENAI_STRUCTURED_OUTPUT_MODE = "json_schema"
$env:OPENAI_MAX_OUTPUT_TOKENS = "8192"
```

Linux/Bash:

```bash
export OPENAI_API_KEY='<사내 게이트웨이 키>'
export OPENAI_BASE_URL='https://<사내-Qwen-gateway>/v1'
export OPENAI_MODEL='Qwen3.5-397B-A17B'
export OPENAI_API_MODE='chat_completions'
export OPENAI_STRUCTURED_OUTPUT_MODE='json_schema'
export OPENAI_MAX_OUTPUT_TOKENS='8192'
```

API key 값은 command line argument, dossier, report, fixture, Git 또는 공유 로그에 넣지 않는다.
인증이 없는 내부 endpoint도 운영자가 승인한 경우에만 server가 무시하는 non-secret placeholder를
사용한다. AXCalib는 빈 key를 허용하지 않는다.

## 3. exact Qwen capability

권장 CLI는 다음과 같다.

```powershell
uv run --no-sync axcalib verify qwen `
  --expected-checkpoint Qwen3.5-397B-A17B `
  --scope deployment `
  --output output/onprem/qwen35-capability.json
```

같은 Library service를 사용하는 script entrypoint도 유지한다.

```powershell
uv run --no-sync python scripts/pipelines/probe_qwen35_capabilities.py `
  --expected-checkpoint Qwen3.5-397B-A17B `
  --scope deployment `
  --output output/onprem/qwen35-capability.json
```

합성 text와 빨강/파랑 두 panel PNG만 전송한다. raw prompt, image, model output와 hidden reasoning은
report에 남기지 않고 request/response hash, latency와 safe failure kind만 기록한다.

### 성공 기준

명령 exit code가 `0`이고 다음 필드가 모두 `true`여야 한다.

```json
{
  "route_identity_confirmed": true,
  "checkpoint_identity_confirmed": true,
  "structured_text_passed": true,
  "structured_vision_passed": true,
  "scope_passed": true,
  "deployment_ready": true,
  "hidden_reasoning_retained": false
}
```

exit code 의미는 다음과 같다.

| Exit | 의미 |
|---:|---|
| `0` | 선택한 scope의 capability와 identity 확인 |
| `1` | report는 생성됐지만 capability 또는 identity 기준 미충족 |
| `2` | 필수 환경변수나 Qwen route 설정 오류 |

`--text-only`는 진단용이다. vision을 생략하므로 `deployment_ready`는 `false`다.

### structured output 호환성

먼저 `json_schema`를 사용한다. endpoint가 response-format dialect를 지원하지 않는다는 명확한
증거가 있을 때만 첫 오류를 보존하고 다음처럼 한 번 분리 재실행한다.

```powershell
$env:OPENAI_STRUCTURED_OUTPUT_MODE = "json_object"
```

```bash
export OPENAI_STRUCTURED_OUTPUT_MODE='json_object'
```

출력은 `qwen35-json-object.json`처럼 다른 파일에 보존한다. AXCalib는 provider 오류 뒤 dialect나
model을 조용히 바꾸지 않으며 어느 mode에서도 결과를 Pydantic schema로 다시 검증한다.

## 4. 테스트 PPTX 등록심의

capability가 통과한 뒤 저장소의 테스트 자료로 registration workflow를 확인한다.

```powershell
uv run --no-sync python scripts/pipelines/run_two_gate_pptx.py `
  tests/sources/oled_qc_project_outline.pptx `
  --proposal-sidecar tests/sources/oled_qc_project_outline.axcalib.json `
  --title "On-prem Qwen 등록심의 Smoke Test" `
  --workspace output/onprem/qwen-registration `
  --project-id onprem-qwen-registration-001 `
  --config config/axcalib.toml `
  --live-model
```

첫 실행에는 `config/axcalib.toml`을 사용한다. expert example의 hybrid retrieval은 목표 설정이며
현재 즉시 실행 가능한 dense/Qdrant 품질 경로가 아니다.

정상 결과:

- `final_status`: `registration_hitl_pending`
- `notification_count`: `1`
- `registration_decision`: `null`
- `dossier_uri`, `registration_report_uri`, `audit_uri` 생성
- Agent가 자동 승인하지 않고 관리자 검토 대기

`registration_report_uri`의 Markdown은 criterion별 평가, 근거 위치, Agent 제안과 한계를 사람이 읽는
결과물이다. 현재 full evaluator는 추출된 evidence text를 모델에 전달한다. capability probe의
synthetic vision 성공이 PPTX slide pixel의 직접 VLM 심사를 뜻하지는 않는다.

## 5. Docling 분리 실행

Qwen 검증과 동시에 실행하지 않는다. 가용 메모리가 최소 2,048MB 이상일 때 optional extra와 별도
process contract를 확인한다.

```powershell
uv sync --locked --dev --extra cli --extra docling
uv run --no-sync python -m harness.prep docling
```

기준 미달의 `BLOCKED_RESOURCE`는 설치 실패나 Qwen 실패가 아니다. Docling이 통과한 뒤에만 새
workspace와 project ID로 등록심의 명령에 `--docling`을 추가한다.

## 6. 실패 분류

| 현상 | 먼저 확인할 항목 |
|---|---|
| HTTP 401/403 | key와 model route 권한 |
| HTTP 404 | `OPENAI_BASE_URL`과 `/v1/chat/completions` 경로 |
| HTTP 400/500 response-format 오류 | 최초 오류 보존 후 `json_object` 명시 재검증 |
| text 성공, vision 실패 | multimodal route와 image data URL 지원 |
| `checkpoint_identity_confirmed=false` | response model alias·오배포; 운영 model mapping 증거 |
| 약 120초 timeout | 단일 요청 지연; 반복 호출 대신 오류와 latency 보존 |
| capability 성공, 등록심의 실패 | full evaluation schema/rubric 응답 호환성 |

endpoint가 marketing alias만 반환하면 expected checkpoint 값을 편의상 alias로 바꾸어 통과시키지
않는다. model card, serving revision 또는 deployment fingerprint를 운영자에게 확인한다.

## 7. 결과 전달

다음 자료만 개발 검토에 전달한다.

1. `git rev-parse HEAD`
2. `output/onprem/qwen35-capability.json`
3. 등록심의 command가 출력한 summary JSON
4. Docling을 실행했다면 pass 또는 `BLOCKED_RESOURCE`
5. 실패 시 key·내부 URL·원문을 제거한 HTTP status와 failure kind

API key, Authorization header, 실제 사내 원문과 숨은 reasoning은 전달하지 않는다.

이 결과 다음에는 [개발 프로세스](Development-Process)의 exact-model report와 Evaluation Owner gold
benchmark를 연결한다. 최종 승인 책임과 HITL 규칙은 [보안과 HITL](Security-and-HITL)을 따른다.
