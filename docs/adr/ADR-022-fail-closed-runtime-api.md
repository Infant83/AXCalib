# ADR-022: Fail-closed Runtime API and Split OpenAPI Contracts

- Status: Accepted
- Date: 2026-07-22
- Scope: WP-06.I1 Minimal API Parity

## Context

Library/CLI Alpha의 registry와 local run checkpoint를 HTTP에서도 같은 의미로 사용해야 한다. 그러나
registry에 등록된 일부 pipeline request는 local file path나 `actor_id`, administrator decision을
포함한다. registry allowlist를 그대로 원격 실행 allowlist로 취급하면 인증된 operator가 payload로
다른 사람을 가장하거나 사람 Gate를 우회할 수 있다. 또한 기존 `openapi.v1alpha1.json`은 아직
구현되지 않은 project evaluation/HITL 목표까지 포함하므로, 구현된 route와 혼합하면 진행상태를
과장하게 된다.

## Decision

1. FastAPI는 optional `api` extra이며 `axcalib.api`를 import할 때만 로드한다. Core/Domain은
   FastAPI를 import하지 않는다.
2. `create_app(AXCalib(...))`은 같은 `PipelineRegistry`와 `LocalPipelineExecutor`를 직접 호출한다.
   script subprocess나 HTTP 전용 domain 판단을 만들지 않는다.
3. bearer token 검증은 deployment-owned `TokenVerifier` port로 주입한다. 기본 verifier는 모든
   token을 거부하고 token 값을 checkpoint, 응답, schema에 기록하지 않는다.
4. Library registry allowlist와 HTTP delivery allowlist를 분리한다. exact `ApiPipelineGrant`가 없는
   pipeline은 catalog에도 보이지 않고 실행도 404로 거부한다. 기본 grant 집합은 비어 있다.
5. generic request payload의 알려진 authority field를 재귀적으로 거부한다. 사람 결정 command는
   인증 principal을 request actor와 bind하는 전용 endpoint 전에는 공개하지 않는다.
6. run 조회와 취소는 owner, administrator 또는 explicit cross-run scope에 한한다. transport role은
   domain HITL 최종결정 권한을 대체하지 않는다.
7. `openapi.v1alpha1.json`은 pre-implementation 제품 목표로 보존하고,
   `openapi.runtime.v1alpha1.json`을 실제 FastAPI-generated OpenAPI 3.1/Draft 2020-12 계약으로 둔다.
8. HTTP 응답에서는 local checkpoint URI를 제거하고 validation input 값은 problem response에
   되돌려주지 않는다. unknown pipeline, auth/role, validation, conflict와 integrity failure를
   machine-readable code로 구분한다.

## Consequences

- 인증 설정을 빼먹거나 pipeline grant를 누락하면 기능이 열리는 대신 닫힌 상태로 실패한다.
- local API E2E는 실제 Library run/checkpoint와 parity를 갖지만, 운영 OIDC/JWKS, tenant/project
  authorization, rate limit, upload/staging, 202 worker/SSE는 아직 검증되지 않았다.
- actor field를 가진 education/two-gate command는 generic endpoint로 실행할 수 없다. 후속 전용
  resource/command endpoint가 principal binding과 domain authorization을 명시해야 한다.
- 두 OpenAPI artifact를 유지해야 하지만 target과 implemented 상태를 혼동하지 않고 drift를 각각
  검증할 수 있다.
