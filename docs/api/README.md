# AXCalib API 계약

API는 Library의 기능을 새로 구현하는 계층이 아니라 versioned pipeline/workflow facade를 HTTP로
노출하는 얇은 adapter다. 계약은 현재 두 층으로 명시적으로 분리한다.

- [전체 제품 목표 계약](openapi.v1alpha1.json): project evaluation/HITL까지 포함하는
  **pre-implementation target**
- [구현된 runtime 계약](openapi.runtime.v1alpha1.json): WP-06.I1 pipeline runtime, WP-06.I2a/I2b/I2c의
  principal-bound resource command/read/replay, WP-06.I3 durable local 202 Worker와 WP-06.I4.1
  OIDC/JWKS signed fixture **implemented local Alpha/reference**

목표 계약에만 존재하는 endpoint를 실행 가능하다고 간주하지 않는다. 구현 artifact는 FastAPI가
생성한 schema와 contract test에서 byte 의미 수준으로 비교한다.

## 표준 기준

- OpenAPI 문서는 FastAPI가 안정적으로 생성하는 `3.1.0`을 기준으로 한다.
- Schema dialect는 JSON Schema Draft 2020-12다.
- 문서는 JSON으로 보관해 YAML parser 차이를 없앤다.
- 모든 구현 endpoint는 bearer 인증을 요구한다. verifier가 없으면 fail closed한다. optional
  `identity` extra는 deployment-owned issuer/JWKS/claim policy를 받는 RFC 9068 local reference를
  제공하지만 실제 운영값과 remote key refresh를 대신 정하지 않는다.
- registry 등록은 HTTP 공개를 뜻하지 않는다. exact `ApiPipelineGrant`가 있어야 catalog와 run에
  노출된다.
- grant의 기본 execution mode는 inline이다. deployment가 exact version을 `queued`로 지정한 경우에만
  validated/hash-bound local job을 기록하고 202를 반환한다.
- queued payload는 object/1 MiB 한도와 알려진 credential key deny를 통과해야 한다. 이는 DLP나 운영
  content policy를 대신하지 않는다.
- run 조회·취소는 owner, administrator 또는 명시적 cross-run scope만 허용한다.
- project 등록은 project owner/administrator role, `projects:create` scope와 verified organization을
  모두 요구한다. 두 HITL 결정은 administrator role, project decision scope, dossier organization과
  expected revision을 모두 검사하며 `Idempotency-Key`가 필수다.
- project 조회는 owner `projects:read:own` + creation audit 또는 administrator read scope와 organization을
  요구한다. response는 local URI, progress note, mentor identity와 decision rationale를 포함하지 않는다.
- 동일 decision principal/key/resource/stage/revision/payload는 저장된 성공 결과를 replay한다. 다른
  actor/resource/payload가 같은 key를 쓰면 mutation 없이 409로 닫힌다.
- generic pipeline payload가 `actor_id`, `actor_role` 또는 관리자 결정을 전달하는 것은 거부한다.
  전용 project decision endpoint에는 actor field가 없으며 검증된 principal subject만 audit actor가 된다.
- `education-program-runtime@v1alpha1`은 generic grant로 노출할 수 없다. 교육 endpoint는 learner,
  mentor, instructor, administrator의 exact resource scope와 organization을 검사하고 request actor를
  principal subject로 대체한다.
- remote project request는 local path를 받지 않는다. deployment-owned `StagedArtifactResolver`가 opaque
  artifact ID를 access-check하고 API가 media type, byte size와 SHA-256을 재검증한다. 기본 resolver는
  모두 거부한다.
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

## OIDC/JWKS local reference

설치와 회귀 확인:

~~~powershell
uv sync --locked --dev --extra api --extra identity
uv run --no-sync pytest tests/unit/test_oidc_identity.py `
  tests/contract/test_oidc_api_contract.py -q
~~~

deployment 조합은 기존 `create_app`의 작은 주입점을 그대로 사용한다.

~~~python
from axcalib.api import create_app
from axcalib.api.oidc import OidcTokenVerifier

verifier = OidcTokenVerifier(
    policy=approved_identity_policy,
    jwk_set_provider=approved_jwk_set_provider,
)
app = create_app(runtime, token_verifier=verifier, pipeline_grants=grants)
~~~

`approved_identity_policy`와 remote provider는 이 저장소가 자동 생성하지 않는다. 현재 concrete
`StaticJwkSetProvider`는 local signed fixture용이다. issuer/audience/role/scope/organization,
key rotation, revocation과 assignment는
[I4 결정 패킷](../security/identity-upload-decision-packet.md)을 Owner가 채운 뒤 운영 adapter에
주입한다. Core 설치에는 PyJWT/cryptography가 포함되지 않는다.

## 예시

- [등록심의 평가 요청](examples/registration-evaluation.request.json)
- [완료평가 평가 요청](examples/completion-evaluation.request.json)
- [202 응답](examples/run-accepted.response.json)

위 예시는 전체 제품 **target interface contract**다. 현재 실행 가능한 runtime route는 다음이다.

| Method | Route | 현재 의미 |
|---|---|---|
| GET | `/v1/pipelines` | deployment가 허용한 pipeline catalog |
| POST | `/v1/pipelines/{pipeline_id}/versions/{pipeline_version}/runs` | inline 200 또는 queued 202 + stable Location; 같은 Library executor 사용 |
| GET | `/v1/runs/{run_id}` | result path/hash를 검증한 execution status/output와 독립 queue status 조회 |
| POST | `/v1/runs/{run_id}/cancel` | process kill이 아닌 cooperative marker |
| POST | `/v1/projects` | principal-bound project 등록; required idempotency key와 staged PPTX hash 검증 |
| GET | `/v1/projects/{project_id}` | owner/admin scope·organization을 확인한 URI/free-text redacted current state |
| POST | `/v1/projects/{project_id}/decisions/registration` | 관리자 등록 승인/반려; scope/org/revision + semantic replay |
| POST | `/v1/projects/{project_id}/decisions/completion` | 관리자 완료 수용/미수용; scope/org/revision + semantic replay |
| GET | `/v1/programs/{program_id}/versions/{program_version}` | local path를 제거한 immutable program/hash 조회 |
| POST | `/v1/programs/{program_id}/versions/{program_version}/enrollments` | exact hash의 principal-bound learner self enrollment |
| GET | `/v1/enrollments/{enrollment_id}` | learner 또는 배정 reviewer/admin의 진도 조회 |
| POST | `/v1/enrollments/{id}/milestones/{milestone_id}/start` | 해당 learner의 milestone 시작 |
| POST | `/v1/enrollments/{id}/milestones/{milestone_id}/manual-confirmations` | 설정된 instructor/mentor/admin의 확인 기록 |
| POST | `/v1/enrollments/{id}/milestones/{milestone_id}/scores` | 설정된 reviewer의 점수 기록 |
| POST | `/v1/enrollments/{id}/milestones/{milestone_id}/projects` | learner project dossier 연결과 context/org 검증 |
| POST | `/v1/enrollments/{id}/milestones/{milestone_id}/project-sync` | 저장된 dossier 상태에서 project requirement 동기화 |
| POST | `/v1/enrollments/{enrollment_id}/completion-decisions` | 관리자 과정 완료 승인/보완반려 |

구현 artifact 재생성:

~~~powershell
uv run --no-sync python scripts/pipelines/export_runtime_openapi.py
~~~

TestClient 계약은 실제 socket이나 외부 인증 endpoint를 열지 않는다. 운영 server, remote
discovery/JWKS cache·rotation·revocation, rate limit, immutable upload service, 실제 교육 배정 source,
project list/report authorization, distributed worker/heartbeat와 SSE는 후속 WP-06 범위다. local Worker
경계는 [WP-06.I3 리포트](../evaluation/wp06-i3-durable-local-worker-report.md), identity 경계는
[ADR-028](../adr/ADR-028-provider-neutral-oidc-jwks-reference.md), 운영 NO-GO와 공격면은
[API/Identity Threat Model](../security/api-alpha-threat-model.md)을 따른다.

현재 decision replay는 단일 workspace의 local filesystem record다. domain commit 뒤 idempotency
success record write 전 process crash, multi-host serialization, retention과 database transaction은
해결하지 않는다. 이 경계는 distributed worker/idempotency adapter 전에 반드시 보강한다.

## 교육 프로그램 확장 경계

implemented OpenAPI는 미리 발행된 immutable program의 safe 조회, learner self enrollment, enrollment
조회, milestone start/manual confirmation/score/project bind·sync와 administrator completion
approve/return을 제공한다. mutation은 `Idempotency-Key`와 `expected_revision`이 필수이며 같은
principal/key/request의 성공 결과만 replay한다.

| actor 역할 | principal/resource 조건 |
|---|---|
| learner | enrollment `learner_ref`와 subject 일치 + `education:progress:self` |
| mentor | `education:enrollment:{id}:mentor` |
| instructor | `education:program:{program_id}@{version}:instructor` |
| administrator | `education:admin:any` 또는 enrollment별 admin scope |

모든 역할은 enrollment creation audit에 고정된 organization도 일치해야 한다. program publish/retire,
mentor/instructor assignment 저장소와 실제 IdP claim mapping은 아직 구현하지 않았다. library-only
legacy enrollment처럼 organization-bound creation audit가 없는 resource는 HTTP에서 fail closed한다.

project status, HITL 생략, 자동 과정 완료, arbitrary expression/import는 request field로 제공하지
않는다. Web App은 API가 반환한 milestone state와 allowed command만 표시한다.

## 표준 참고

- [OpenAPI Specification 3.1.0](https://spec.openapis.org/oas/v3.1.0.html)
- [OpenAPI Specification 3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [FastAPI OpenAPI 3.1 안내](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [TOML 1.0.0](https://toml.io/en/v1.0.0)
- [TOML 1.1.0](https://toml.io/en/v1.1.0)
