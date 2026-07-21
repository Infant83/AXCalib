# AXCalib API 계약

API는 Library의 기능을 새로 구현하는 계층이 아니라 versioned pipeline/workflow facade를 HTTP로
노출하는 얇은 adapter다. 개발 전 기준은 [OpenAPI v1alpha1](openapi.v1alpha1.json)이며 실제
FastAPI 구현과 생성된 `openapi.json`은 이 계약에 대한 compatibility test를 통과해야 한다.

## 표준 기준

- OpenAPI 문서는 FastAPI가 안정적으로 생성하는 `3.1.0`을 기준으로 한다.
- Schema dialect는 JSON Schema Draft 2020-12다.
- 문서는 JSON으로 보관해 YAML parser 차이를 없앤다.
- 모든 endpoint는 bearer/OIDC 인증을 전제로 하며 role만이 아니라 organization, project,
  access classification scope를 함께 검사한다. 실제 issuer와 claim mapping은 WP-06 threat model에서 확정한다.
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

이 문서와 예시는 **interface contract**이며 현재 P1에서 endpoint가 실행된다는 뜻이 아니다.

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
