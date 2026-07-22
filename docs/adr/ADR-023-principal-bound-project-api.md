# ADR-023: Principal-bound Project Commands and Staged Artifacts

- Status: Accepted
- Date: 2026-07-22
- Scope: WP-06.I2a Project API authority boundary

## Context

WP-06.I1은 generic pipeline 실행에서 `actor_id`와 관리자 결정을 거부했지만, 프로젝트 등록과 두
HITL 결정을 HTTP로 제공하지 않았다. 기존 Python facade는 신뢰된 local caller가 파일 경로와
actor 문자열을 전달하는 계약이므로 그대로 원격 노출하면 bearer principal과 다른 사람을
주장하거나 서버의 임의 경로를 읽을 수 있다. 관리자 결정에는 lost update를 막는 명시적 revision과
project/organization authorization도 필요하다.

## Decision

1. 원격 프로젝트 등록은 `POST /v1/projects` 전용 typed command로만 제공한다. 호출자는
   `project_owner` 또는 `administrator`, `projects:create` scope와 verified organization을 모두
   가져야 한다.
2. request는 로컬 경로를 받지 않는다. deployment가 access check를 마친 opaque artifact ID,
   SHA-256, byte size와 media type만 받고 `StagedArtifactResolver` port가 승인된 local immutable
   file로 해석한다. 기본 resolver는 모두 거부한다.
3. API는 resolver 결과의 확장자, 크기와 SHA-256을 다시 검증하고, Library가 만든 artifact hash도
   요청 expected hash와 transaction 전에 비교한다. 이후 평가도 frozen proposal/sidecar hash를 다시
   확인한다. response에는 artifact/dossier URI를 넣지 않는다.
4. 등록 idempotency key와 verified subject로 안정적인 project ID를 만든다. 기존 dossier와 title,
   review context, proposal/sidecar hash/size/media, review profile, principal-bound creation audit가 모두
   일치할 때만 staging을 다시 요구하지 않고 replay로 반환한다.
5. 등록·완료 결정 request에는 actor field가 없다. `administrator` role, project decision scope와
   proposer organization access가 모두 확인된 뒤 verified principal subject를 domain actor로 넘긴다.
6. 두 결정은 필수 `expected_revision`을 domain service까지 전달한다. stale revision, 잘못된 상태,
   organization/scope mismatch는 mutation 전에 fail closed한다.
7. 이 slice는 in-process Alpha contract다. 실제 upload service, OIDC/JWKS claim mapping, immutable
   object store, rate limit, malware scan과 distributed transaction은 운영 승격 전 별도 증거가
   필요하다.

## Consequences

- HTTP caller는 Windows/Unix path를 전송해 서버 파일을 열 수 없고 사람 결정 actor를 가장할 수
  없다.
- 같은 organization의 administrator라도 explicit decision scope가 없으면 결정할 수 없다.
- 기존 local dossier에 proposer organization 또는 principal-bound creation audit가 없으면 API replay
  또는 decision이 닫힌 상태로 실패할 수 있다. 운영 migration은 후속 정책 대상이다.
- staging file이 hash 검증 뒤 바뀌는 TOCTOU 위험은 이 local Alpha에서 완전히 제거되지 않는다.
  운영 resolver는 content-addressed immutable object version을 반환해야 한다.
- education learner/mentor/instructor command는 project endpoint의 권한을 재사용한다고 가정하지
  않고 WP-06.I2b에서 enrollment/program scope를 별도로 정의한다.
