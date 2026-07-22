# AXCalib API runtime

`axcalib.api.create_app(...)`은 Library의 allowlisted pipeline registry, durable run checkpoint와
single-host local job queue를 직접 호출하는 optional FastAPI adapter다. 현재 WP-06.I1~I3은
local/in-process Alpha이며 운영 서버, OIDC issuer 설정, 계정, distributed worker 또는 배포를 포함하지
않는다.

## 조립 계약

~~~python
from axcalib import AXCalib
from axcalib.api import ApiExecutionMode, ApiPipelineGrant, TokenVerifier, create_app

runtime = AXCalib("output/api-local")
approved_verifier: TokenVerifier = deployment_owned_verifier

app = create_app(
    runtime,
    token_verifier=approved_verifier,
    pipeline_grants=(
        ApiPipelineGrant(
            pipeline_id="workspace.maintenance",
            pipeline_version="v1alpha1",
            execution_mode=ApiExecutionMode.QUEUED,
        ),
    ),
)
~~~

`deployment_owned_verifier`는 예시 placeholder다. 실제 배포 계층이 OIDC 또는 사내 인증 결과를
`ApiPrincipal`로 변환해 주입해야 한다. AXCalib는 bearer token 값을 checkpoint, 로그 또는 OpenAPI
artifact에 기록하지 않는다.

안전 기본값은 다음과 같다.

- verifier를 주입하지 않으면 모든 token을 거부한다.
- `pipeline_grants`를 주입하지 않으면 catalog는 비어 있고 어떤 pipeline도 HTTP로 실행할 수 없다.
- generic payload의 `actor_id`, `actor_role`, 관리자 결정 필드는 거부한다. 사람 권한이 필요한
  command는 인증 principal을 명시적으로 bind하는 전용 endpoint가 생기기 전까지 노출하지 않는다.
- run 조회·취소는 owner, administrator 또는 명시적 `runs:*:any` scope만 허용한다.
- queued grant만 202를 반환하며 inline이 호환 기본값이다.
- HTTP 응답은 local checkpoint/result와 output 내부 path/URI field를 제거한다.

## 현재 구현 route

| Method | Path | 의미 |
|---|---|---|
| GET | `/v1/pipelines` | API delivery allowlist catalog |
| POST | `/v1/pipelines/{pipeline_id}/versions/{pipeline_version}/runs` | inline 200 또는 queued 202 + stable run reference |
| GET | `/v1/runs/{run_id}` | hash-verified result/status와 독립 `queue_status` 조회 |
| POST | `/v1/runs/{run_id}/cancel` | cooperative cancellation marker 기록 |

개발환경은 `uv sync --locked --dev --extra api`로 설치한다. 실제 socket server 실행은 이 slice의
검증범위가 아니다. in-process 검증과 구현 계약은
`tests/contract/test_runtime_api_contract.py`와
`docs/api/openapi.runtime.v1alpha1.json`을 기준으로 한다.
