# WP-06.I2c Project Read and Decision Replay Report

- Date: 2026-07-22
- Scope: in-process FastAPI + local filesystem idempotency, synthetic/offline only
- Gate impact: G4 Interfaces evidence added; operational deployment remains NO-GO

## 1. Outcome

WP-06.I2c는 project owner/administrator의 organization-bound safe GET과 registration/completion 관리자
결정의 semantic replay를 구현했다. 성공한 결정은 principal, resource, stage, revision과 payload에
고정된 local idempotency record로 재생되며, 다른 actor/resource/payload의 key 재사용은 mutation 없이
409로 닫힌다. API decision은 `verified_api_principal`로 기록되고 Library direct call의 기본값은
`offline_unverified_actor`로 유지된다.

이 결과는 local contract evidence다. 실제 OIDC/JWKS, distributed idempotency, database transaction,
immutable upload, 202 worker나 운영 배포를 검증하지 않았다.

## 2. Implemented contract

| Surface | Contract |
|---|---|
| `GET /v1/projects/{project_id}` | owner creation audit 또는 admin read scope, organization guard, URI-free safe view |
| registration decision | required `Idempotency-Key`, principal/organization/revision binding, exact semantic replay |
| completion decision | registration과 동일한 replay/integrity contract |
| Library facade | optional idempotency key와 authority context; 기존 direct-call 기본 의미 유지 |
| generated OpenAPI | 구현 route와 required header를 OpenAPI 3.1 artifact에 반영 |

`ProjectResourceView`는 project metadata, status/revision, artifact hash metadata, 두 review gate의 report
ID/decision command, free-text가 아닌 progress count만 제공한다. dossier/source/snapshot/report URI,
decision rationale, progress notes, mentor identity와 raw audit detail은 반환 모델에 존재하지 않는다.

## 3. Code review findings and fixes

1. **Revision guard만으로는 response loss를 복구하지 못함**: 기존 endpoint는 commit 뒤 retry를 stale
   409로 반환했다. 기존 `LocalIdempotencyStore`를 `AXCalib.decide_*` facade에 연결해 successful result를
   저장·재생하도록 수정했다.
2. **actor별 key namespace는 confused-deputy 충돌을 숨김**: actor를 내부 key에 넣으면 다른 principal이
   같은 raw key를 재사용해도 별도 record가 된다. raw key digest만 내부 namespace로 사용하고 actor,
   resource, stage와 payload를 request hash에 포함해 cross-context reuse를 409로 고정했다.
3. **authorization 없는 cache replay 위험**: idempotency 결과를 먼저 읽지 않고 현재 principal의
   role/scope/organization을 매 요청마다 확인한 뒤 replay한다.
4. **cache 또는 audit drift 은폐 위험**: 반환 전에 cached result의 pipeline/status/revision/command와
   persisted decision, `verified_api_principal` authority context 및 append-only audit event를 함께
   재검증한다.
5. **dossier 직접 직렬화 정보노출**: safe-view 모델을 새로 두어 local URI와 자유서술/identity field를
   allowlist 밖으로 제거했다.
6. **API 인증과 domain authority provenance 불일치**: service/facade에 authority context를 전달하되
   기존 Library 호출의 offline 기본값은 유지했다.

## 4. Verification evidence

| Check | Result |
|---|---|
| project API targeted contract | 6 passed |
| runtime + project + education API combined | 18 passed |
| full lightweight offline regression | 121 passed |
| offline evaluation harness | 10 groups passed |
| Ruff lint / changed Python format | full lint passed / 7 passed |
| low-memory full Pyright | 0 errors / 0 warnings |
| `prep.ps1 validate` | 0 errors / 0 warnings |
| clean `[api]` wheel | FastAPI 0.139.2 / OpenAPI 3.1 / 17 paths |
| generated OpenAPI | OpenAPI 3.1, 17 implemented paths |

Targeted contract는 owner/admin read scope, owner binding, cross-organization denial, response redaction,
required idempotency header, registration/completion exact replay, audit/revision exactly-once와
actor/resource/payload conflict를 포함한다. repository 전체 `ruff format --check .`은 기존 52개 파일의
format drift를 검출했으나 이번 변경 Python 7개는 모두 통과했다. 범위 밖 파일은 일괄 재작성하지
않았고 이 예외를 `PROJECT_STATE.md` closeout history에 기록했다.

## 5. Residual risks and boundaries

- domain commit 뒤 idempotency success record를 쓰기 전에 process가 종료되는 극단적 crash window는
  local filesystem 두 파일을 하나의 원자 transaction으로 묶지 않는다.
- idempotency key retention, multi-host serialization, database/outbox transaction과 worker lease는
  distributed adapter가 필요하다.
- owner는 Alpha에서 principal-bound creation audit로 식별한다. ownership transfer/delegation은 별도
  authoritative assignment source가 필요하다.
- project list, report/evidence content read, audit timeline과 reviewer workbench API는 구현하지 않았다.
- 실제 IdP claim mapping, 계정 회수, proxy/rate limit, immutable upload와 penetration test가 없으므로
  운영 배포는 계속 NO-GO다.

## 6. Next slice

G4의 다음 우선순위는 approved OIDC/JWKS claim mapping 및 immutable upload/staging 경계 또는
durable 202 worker/poll/SSE 중 Product/Security Owner가 승인한 dependency다. project report/evidence
조회는 별도 redaction·authorization 계약 없이 현재 safe GET에 합치지 않는다.
