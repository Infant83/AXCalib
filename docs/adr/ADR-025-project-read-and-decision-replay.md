# ADR-025: Authorized Project Read and Semantic Decision Replay

- Status: Accepted
- Date: 2026-07-22
- Scope: WP-06.I2c project resource and response-loss recovery contract

## Context

WP-06.I2a의 등록·완료 결정 endpoint는 관리자 role, project scope, organization과
`expected_revision`을 확인한다. 따라서 같은 결정을 두 번 적용하지는 않지만, domain commit 뒤 HTTP
응답만 유실된 client는 성공 여부를 확인할 project 조회 endpoint가 없고 같은 요청을 보내면 stale
revision으로 실패한다. 또한 project dossier를 그대로 반환하면 source, snapshot, report URI와
자유서술 진행노트·결정 사유가 노출된다.

## Decision

1. `GET /v1/projects/{project_id}`는 `project_owner` 또는 `administrator`만 사용한다. owner는
   `projects:read:own`과 principal-bound creation audit가 필요하고, administrator는
   `projects:read:any` 또는 `project:{id}:read`가 필요하다. 두 역할 모두 dossier organization 또는
   명시적 organization access를 통과해야 한다.
2. project 조회는 별도 `ProjectResourceView`를 반환한다. artifact는 ID, role, media type, size와
   SHA-256만 제공하고 dossier/source/snapshot/report URI, progress note 원문, mentor identity, decision
   rationale와 audit detail은 구조적으로 포함하지 않는다.
3. registration/completion decision에는 `Idempotency-Key`를 필수로 한다. Library facade는 project,
   stage, actor subject, authority context, expected revision, command, rationale와 adjustments를 canonical
   request hash로 고정하고 성공한 `PipelineResult`를 local idempotency store에 저장한다.
4. HTTP raw key는 평문으로 저장하지 않고 단방향 digest 기반 내부 key로 바꾼다. 내부 key는 actor에
   따라 분리하지 않으므로 같은 raw key를 다른 actor, resource, stage 또는 payload에 재사용하면 409로
   충돌한다. exact retry만 저장된 semantic result를 반환한다.
5. replay 전에는 현재 principal의 role/scope/organization을 다시 확인한다. 반환 전에는 persisted
   decision, verified authority context, target revision, command와 append-only audit event가 cached result와
   일치하는지 검증한다.
6. Library direct call의 기본 authority context는 계속 `offline_unverified_actor`다. API adapter만 검증된
   principal에서 `verified_api_principal`을 전달한다.
7. 이 계약은 단일 workspace의 filesystem idempotency reference다. domain commit과 idempotency result
   write 사이 process crash, 여러 host, database transaction, 실제 OIDC/JWKS와 key retention은 운영
   hardening 범위로 남긴다.

## Consequences

- HTTP 응답이 전송 과정에서 유실돼도 같은 관리자·key·request는 revision이나 audit event를 늘리지
  않고 같은 결정 결과를 회수할 수 있다.
- owner/admin은 현재 project 상태를 조회할 수 있지만 local 파일 위치나 심사 자유서술 원문을 얻지
  못한다. report/evidence 상세 조회는 별도 authorization 계약이 필요하다.
- 다른 actor/resource/payload의 key 재사용은 domain mutation 전에 충돌한다. key namespace와 record
  retention은 distributed idempotency adapter를 도입할 때 다시 결정한다.
- 이 local contract만으로 인터넷 또는 사내 운영망 배포를 승인하지 않는다.
