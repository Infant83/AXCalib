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
| `config/review_profiles/*.yaml` | version/hash-bound 등록·완료 심사기준 |
| `docs/schemas/runtime-config.schema.json` | 허용 키·타입·범위 |
| `docs/api/openapi.v1alpha1.json` | full evaluation/HITL API 목표 계약, pre-implementation |
| `docs/api/openapi.runtime.v1alpha1.json` | 실제 runtime + principal-bound project·education API local Alpha 계약 |

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

## 현재 구현된 Runtime OpenAPI

- `GET /v1/pipelines`: deployment가 exact grant로 공개한 pipeline catalog
- `POST /v1/pipelines/{pipeline_id}/versions/{version}/runs`: 같은 Library pipeline 동기 실행
- `GET /v1/runs/{run_id}`: owner/admin/scope 기반 hash-verified 결과 조회
- `POST /v1/runs/{run_id}/cancel`: cooperative cancellation marker
- `POST /v1/projects`와 두 `/decisions/{stage}`: staged hash 등록과 관리자 HITL
- `GET /v1/programs/{id}/versions/{version}`와 `POST .../enrollments`: exact program 조회·self 가입
- `/v1/enrollments/{id}/milestones/...`: learner 시작, 배정 reviewer 확인/점수, project bind/sync
- `POST /v1/enrollments/{id}/completion-decisions`: 관리자 과정 완료 승인/보완반려

verifier와 pipeline grant 기본값은 모두 닫혀 있다. generic payload의 actor/admin decision은
거부하며 교육 runtime은 generic grant 자체를 허용하지 않는다. bearer token과 local checkpoint,
dossier, enrollment URI는 결과나 OpenAPI에 기록하지 않는다.

## 향후 제품 OpenAPI 목표

- `POST /v1/projects/{project_id}/evaluations/{stage}`: revision을 고정하고 평가 실행 요청
- `GET /v1/runs/{run_id}`: 상태, report reference, allowed command 조회
- `POST /v1/runs/{run_id}/commands`: 권한 있는 사람이 wait 상태를 재개
- `GET /v1/capabilities`: 서버가 허용한 profile과 limit 조회

`202 Accepted`는 인증 승인이 아니라 실행 요청 접수다. 현재 runtime/project/education API는
synchronous local Alpha이며 actor 없는 전용 resource route가 principal·scope·organization·revision을
검사한다. full evaluation route와 OIDC/RBAC·실제 교육 배정/immutable upload/worker는 WP-06 후속
범위다. 오류는
현재 구현에서도 redacted RFC 9457-shaped Problem code로 구분한다.
