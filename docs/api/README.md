# AXCalib API 계약

API는 Library의 기능을 새로 구현하는 계층이 아니라 versioned pipeline/workflow facade를 HTTP로
노출하는 얇은 adapter다. 계약은 현재 두 층으로 명시적으로 분리한다.

- [전체 제품 목표 계약](openapi.v1alpha1.json): project evaluation/HITL까지 포함하는
  **pre-implementation target**
- [구현된 runtime 계약](openapi.runtime.v1alpha1.json): WP-06.I1의 pipeline catalog/run/status/cancel
  **implemented local Alpha**

목표 계약에만 존재하는 endpoint를 실행 가능하다고 간주하지 않는다. 구현 artifact는 FastAPI가
생성한 schema와 contract test에서 byte 의미 수준으로 비교한다.

## 표준 기준

- OpenAPI 문서는 FastAPI가 안정적으로 생성하는 `3.1.0`을 기준으로 한다.
- Schema dialect는 JSON Schema Draft 2020-12다.
- 문서는 JSON으로 보관해 YAML parser 차이를 없앤다.
- 모든 구현 endpoint는 bearer 인증을 요구한다. 실제 issuer와 claim mapping은 deployment가
  `TokenVerifier`로 주입하며 verifier가 없으면 fail closed한다.
- registry 등록은 HTTP 공개를 뜻하지 않는다. exact `ApiPipelineGrant`가 있어야 catalog와 run에
  노출된다.
- run 조회·취소는 owner, administrator 또는 명시적 cross-run scope만 허용한다. organization,
  project, access classification의 운영 RBAC mapping은 아직 미완료다.
- generic pipeline payload가 `actor_id`, `actor_role` 또는 관리자 결정을 전달하는 것은 거부한다.
  사람 권한 command는 인증 principal을 bind하는 전용 endpoint가 필요하다.
- OpenAPI 3.2는 최신 표준이지만 WP-06에서 code generator, Swagger UI, client 호환성을 spike한
  뒤 별도 ADR로 승격한다.

## Progressive disclosure

일반 사용자는 `profile`, `expected_revision`과 기본 options만 보낸다. 전문 사용자는
`options.retrieval`, `options.model`, `options.report`의 allowlisted field를 사용할 수 있다.
모르는 field는 `additionalProperties: false`로 거부한다.

다음 값은 JSON parameter나 TOML로 끌 수 없다.

- 관리자 HITL
- 승인요청 notification
- mentor가 배정된 경우의 mentor approval guard
- revision/snapshot/stale 검사
- final decision actor 권한
- auto certification

## 예시

- [등록심의 평가 요청](examples/registration-evaluation.request.json)
- [완료평가 평가 요청](examples/completion-evaluation.request.json)
- [202 응답](examples/run-accepted.response.json)

위 예시는 전체 제품 **target interface contract**다. 현재 실행 가능한 runtime route는 다음뿐이다.

| Method | Route | 현재 의미 |
|---|---|---|
| GET | `/v1/pipelines` | deployment가 허용한 pipeline catalog |
| POST | `/v1/pipelines/{pipeline_id}/versions/{pipeline_version}/runs` | Library async entrypoint를 호출하고 local checkpoint 결과 반환 |
| GET | `/v1/runs/{run_id}` | result path/hash를 검증한 status/output 조회 |
| POST | `/v1/runs/{run_id}/cancel` | process kill이 아닌 cooperative marker |

구현 artifact 재생성:

~~~powershell
uv run --no-sync python scripts/pipelines/export_runtime_openapi.py
~~~

TestClient 계약은 실제 socket이나 외부 인증 endpoint를 열지 않는다. 운영 server, OIDC/JWKS,
rate limit, tenant/project authorization, worker/202/SSE는 후속 WP-06 범위다.

## 교육 프로그램 확장 경계

`EducationProgram`, `EducationEnrollment`과 `education-program-runtime@v1alpha1` typed command는
현재 Python Library에서 실행된다. program/enrollment JSON Schema Draft 2020-12 artifact도
생성되지만 이 v1alpha1 OpenAPI 문서에는 아직 endpoint를 추가하지 않았다. WP-06에서 다음
resource/command를 같은 schema와 idempotency 의미로 노출한다.

- immutable program publish/show/retire
- learner enrollment와 milestone progress 조회
- manual confirmation, score, project bind/sync typed command
- program completion administrator approve/return command

project status, HITL 생략, 자동 과정 완료, arbitrary expression/import는 request field로 제공하지
않는다. Web App은 API가 반환한 milestone state와 allowed command만 표시한다.

## 표준 참고

- [OpenAPI Specification 3.1.0](https://spec.openapis.org/oas/v3.1.0.html)
- [OpenAPI Specification 3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [FastAPI OpenAPI 3.1 안내](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [TOML 1.0.0](https://toml.io/en/v1.0.0)
- [TOML 1.1.0](https://toml.io/en/v1.1.0)
