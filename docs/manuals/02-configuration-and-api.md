# 설정과 API 제어

## 원칙

일반 사용자는 작은 기본값을 사용하고, 전문 사용자만 TOML profile과 typed JSON options를
연다. 비밀 값은 파일에 넣지 않고 환경변수 **이름만** 적는다.

```text
보호 불변조건
  > package safe defaults
  > config.toml profile
  > environment secret/endpoint
  > allowlisted request options
  > policy guard reject/clamp
```

실제 적용값은 secret을 제거한 hash와 source map으로 감사기록에 연결한다.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `config/axcalib.toml` | 작은 offline 기본값 |
| `config/axcalib.expert.example.toml` | on-prem adapter 구성 예시 |
| `docs/schemas/runtime-config.schema.json` | 허용 키·타입·범위 |
| `docs/api/openapi.v1alpha1.json` | 요청별 JSON과 상태 계약 |

지원하는 작성 문법은 Python 3.12 `tomllib`과 맞는 TOML 1.0 범위다. unknown key는 경고 후
무시하지 않고 validation error로 처리한다.

## 요청별 JSON 예시

```json
{
  "expected_revision": 3,
  "options": {
    "evaluation_mode": "single",
    "retrieval": {
      "profile": "registration_lexical",
      "similarity_portion": 0.0,
      "top_k": 5
    },
    "reports": {
      "formats": ["json", "markdown"],
      "locale": "ko-KR"
    }
  }
}
```

요청에는 `auto_certify`, `skip_hitl`, `final_decision`, `admin_approval_required` 같은 필드가
존재하지 않는다. 임의 graph, Python import path, expression도 허용하지 않는다.

## OpenAPI 동작

- `POST /v1/projects/{project_id}/evaluations/{stage}`: revision을 고정하고 평가 실행 요청
- `GET /v1/runs/{run_id}`: 상태, report reference, allowed command 조회
- `POST /v1/runs/{run_id}/commands`: 권한 있는 사람이 wait 상태를 재개
- `GET /v1/capabilities`: 서버가 허용한 profile과 limit 조회

`202 Accepted`는 인증 승인이 아니라 실행 요청 접수다. 오류는 RFC 9457 계열 Problem Details
모양으로 발전시키며, 인증·인가 정책은 WP-06 threat model과 함께 확정한다.
