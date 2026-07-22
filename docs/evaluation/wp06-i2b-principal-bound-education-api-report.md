# WP-06.I2b Principal-bound Education API 개발·리뷰 리포트

- 날짜: 2026-07-22
- 범위: immutable program 조회, learner enrollment, milestone/reviewer/project command, program completion decision
- 판정: **local contract verified; operational identity/assignment NO-GO**

## 1. 결과

기존 runtime/project API에 actor 없는 education resource endpoint를 추가했다.

| Resource | 구현된 의미 |
|---|---|
| program version GET | local source URI를 제거한 immutable program과 SHA-256 조회 |
| program enrollment POST | verified learner self enrollment, exact program hash와 organization 고정 |
| enrollment GET | learner 또는 배정 mentor/instructor/admin의 URI-redacted progress 조회 |
| milestone start | enrollment learner subject와 self-progress scope 확인 |
| manual confirmation / score | rubric에 설정된 reviewer role과 enrollment/program assignment scope 확인 |
| project bind / sync | learner 또는 배정 actor, dossier education context와 organization 재검증 |
| completion decision | administrator resource scope, organization, revision과 domain HITL 확인 |

request는 `actor_id`, `actor_role`, `learner_ref` 또는 `organization_id`를 받지 않는다. audit actor는
검증된 `ApiPrincipal.subject/role`이며 API 경계는 `verified_api_principal`로 기록된다. Python Library를
직접 호출하는 기존 예제는 계속 `offline_unverified_actor`이므로 운영 인증으로 오해하지 않는다.

## 2. Authorization matrix

| 역할 | 필수 resource binding | 허용된 Alpha 명령 |
|---|---|---|
| learner | enrollment learner와 subject 일치, `education:progress:self` | 조회, 시작, project bind/sync |
| mentor | `education:enrollment:{id}:mentor` | mentor requirement 확인, 조회/sync |
| instructor | `education:program:{program_id}@{version}:instructor` | instructor requirement 확인·점수, 조회/sync |
| administrator | `education:admin:any` 또는 enrollment별 admin scope | reviewer override, 조회/sync, 과정 완료결정 |

모든 역할은 enrollment creation audit에 고정된 organization도 일치해야 한다. self enrollment는 별도
`education:enroll:self` scope와 expected program SHA-256을 요구한다. `education-program-runtime`은
generic `ApiPipelineGrant`로 공개할 수 없어 actor-bearing Library command가 원격 우회로가 되지 않는다.

## 3. 구현 리뷰

### 발견하고 수정한 문제

1. 첫 FastAPI contract 실행에서 별도 router의 postponed annotation이 closure 안
   `Depends(authenticate)`를 query parameter로 해석해 네 endpoint test가 422가 됐다. 기존 project
   router와 같은 eager annotation 방식으로 바꿔 dependency를 정상 복구했다.
2. endpoint에서 current revision을 idempotency replay보다 먼저 거부하면 성공 응답 유실 뒤 같은
   key/request도 stale 409가 됐다. authorization은 현재 enrollment로 먼저 확인하되 revision은
   idempotency store 뒤 domain service가 검사하게 해 exact replay와 새 stale command를 구분했다.
3. API layer에만 revision을 두면 Library/다른 adapter가 stale update를 보낼 수 있었다. 모든 education
   mutation command가 optional expected revision을 service까지 전달하고 repository CAS가 다시 확인한다.
4. 기존 project sync는 bind 이후 dossier context가 바뀌어도 status만 읽었다. bind와 sync 모두
   program/version/enrollment/milestone/learner를 재검사하고 API는 proposer organization도 요구한다.
5. enrollment create replay가 idempotency 결과만 반환하면 audit나 program binding 손상을 숨길 수
   있었다. 응답 전 persisted enrollment, program hash, learner, organization-bound creation audit를
   다시 검증하도록 보강했다.
6. reviewer route가 organization보다 requirement를 먼저 조회하면 다른 tenant가 requirement 존재를
   status code로 탐색할 수 있었다. organization authorization을 requirement lookup보다 앞에 뒀다.
7. 첫 전체 test는 새 리포트 링크와 append-only history를 마감하기 전에 실행해 harness 2건이
   실패하고 나머지 118건이 통과했다. 리포트와 HIST-2026-07-22-008을 추가한 뒤 같은 명령을 재실행해
   120/120을 통과했고 최종 closeout은 HIST-2026-07-22-009에 고정했다.

### 유지한 경계

- Core Library는 FastAPI나 OIDC 구현에 의존하지 않는다.
- response/OpenAPI에는 program/enrollment local URI, bearer token 또는 rejected input value가 없다.
- project 상태는 request가 아니라 repository dossier에서 읽는다.
- 모든 과정 milestone 완료 뒤에도 durable notification과 administrator domain HITL을 우회하지 않는다.
- program publish/retire와 실제 mentor/instructor assignment source는 구현하지 않았다.

## 4. 검증

- education API targeted contract: 5 passed
- runtime + project + education API contract: 17 passed
- education Library unit/integration regression: 7 passed
- full lightweight offline test: 120 passed
- evaluation harness: 10 groups passed
- Ruff check와 changed-file format check: passed
- low-memory Pyright: 0 errors, 0 warnings
- generated OpenAPI: 3.1.0, 16 paths, committed artifact exact match
- clean `[api]` wheel: FastAPI 0.139.2, OpenAPI 3.1.0, 16 paths
- workspace validation: 0 errors, 0 warnings
- SVG/PNG: Edge headless render 후 현재/향후 label과 clipping을 시각 확인

외부 모델, Docling, 실제 OIDC/JWKS, 계정·교육 배정 원장, socket server, 실데이터와 운영
notification은 호출하지 않았다.

## 5. 남은 위험과 다음 단계

- mentor/instructor scope는 deployment가 검증해 주입하는 Alpha 계약이다. 실제 IdP claim, 인사·교육
  배정 원장, delegation/revocation과 tenant 정책은 승인·검증되지 않았다.
- program publish/show-all/retire 권한과 기존 library-only enrollment의 organization migration은 없다.
- project decision endpoint는 commit 뒤 응답 유실을 같은 결과로 replay하지 못하고 authorized project
  GET도 없다. WP-06.I2c에서 이 복구 계약을 우선한다.
- immutable upload/ACL/malware scan, distributed idempotency/worker, 202/poll/SSE는 후속 G4 범위다.
- 이 결과는 API authorization 구조의 local contract이지 교육 정책·점수·공식 인증 품질 검증이 아니다.

결정 근거는 [ADR-024](../adr/ADR-024-principal-bound-education-api.md), 공격면은
[API Alpha Threat Model](../security/api-alpha-threat-model.md)을 따른다.
