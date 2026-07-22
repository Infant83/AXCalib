# WP-06.I1 Minimal API Parity 개발·코드리뷰 리포트

- 날짜: 2026-07-22
- Phase / WP / Gate: P7 / WP-06.I1 / G4 Interfaces
- 판정: **local/in-process API Alpha contract verified 후보**
- 기준 commit: Library MVP/Alpha `a03a633` 이후 change set

## 1. 결과 요약

`axcalib.api.create_app(...)`이 기존 `AXCalib` facade의 `PipelineRegistry`와
`LocalPipelineExecutor`를 직접 호출하도록 구현했다. 현재 route는 pipeline catalog, synchronous
run, hash-verified status와 cooperative cancel 네 가지다. FastAPI는 `api` optional extra이며
Core/Domain import 경로에는 포함되지 않는다.

이번 결과는 실제 socket server, OIDC/JWKS, tenant/project RBAC, 202 worker, SSE, upload/staging,
rate limit 또는 운영 배포 완료가 아니다. Agent/HITL 최종결정 권한도 HTTP adapter로 이동하지
않는다.

## 2. 구현 계약

| 관심사 | 구현 |
|---|---|
| Library parity | handler가 script subprocess 없이 같은 registry/executor와 typed request/result 사용 |
| 인증 | deployment-owned `TokenVerifier`; 미주입 시 모든 token 거부 |
| HTTP 공개 범위 | exact `ApiPipelineGrant`; 미주입 시 공개 pipeline 0개 |
| 권한 | execute role, run owner/administrator 또는 explicit cross-run scope |
| 사람 권한 경계 | generic payload의 actor/admin decision field 재귀 거부 |
| idempotency | body 또는 `Idempotency-Key`; 둘이 다르면 fail closed, principal+key로 stable run ID |
| revision | envelope와 typed pipeline의 `expected_revision`이 다르면 422 |
| 오류 | auth/role/not-found/validation/conflict/integrity를 redacted problem code로 구분 |
| 응답 | local checkpoint URI 제거, validation input 값 미반사 |
| OpenAPI | generated OpenAPI 3.1 + JSON Schema Draft 2020-12 artifact 고정 |

## 3. OpenAPI 상태 분리

- `docs/api/openapi.v1alpha1.json`: project evaluation/HITL을 포함한 **pre-implementation target**
- `docs/api/openapi.runtime.v1alpha1.json`: 이번에 실제 실행되는 **implemented local Alpha**

목표 계약을 실제 route로 오인하지 않도록 파일과 상태를 분리했다. 구현 artifact는
`scripts/pipelines/export_runtime_openapi.py`로 재생성하고 contract test가 실제 schema와 비교한다.

## 4. 코드리뷰 발견사항과 조치

### CR-01 Registry allowlist와 HTTP allowlist 혼동 — 조치 완료

초기 구현은 registry의 모든 pipeline을 인증된 operator에게 그대로 노출했다. 일부 pipeline은
local path나 사람 actor/decision을 입력하므로 원격 trust boundary로는 안전하지 않았다.
`ApiPipelineGrant`를 별도 delivery allowlist로 도입하고 기본값을 빈 집합으로 변경했다.

### CR-02 Payload actor 가장 가능성 — 조치 완료

education/two-gate request 중에는 `actor_id`, `actor_role`, `administrator_id`와 최종결정 field가
있다. generic endpoint가 이를 신뢰하면 bearer principal과 다른 사람을 주장할 수 있다. 알려진
authority field를 중첩 위치에서도 거부하고, 향후 principal-bound 전용 endpoint에서만 다루도록
고정했다.

### CR-03 Cross-run 조회·취소 — 조치 완료

run ID를 아는 viewer/operator가 다른 actor의 결과를 조회·취소할 가능성을 확인했다. owner,
administrator 또는 `runs:read:any` / `runs:cancel:any` scope만 허용하도록 보강했다.

### CR-04 Raw JSON idempotency drift — 조치 완료

같은 의미의 `{}`와 `{ "apply": false }`가 서로 다른 hash가 될 수 있었다. API boundary에서 같은
registry request type으로 먼저 검증한 model을 executor에 전달해 default가 포함된 canonical 의미로
hash한다. body/header key 충돌과 run reuse conflict도 별도 422/409로 검증한다.

### CR-05 Revision context 불일치 — 조치 완료

HTTP envelope revision과 pipeline payload revision이 다르면 감사 context와 실제 domain 입력이
엇갈릴 수 있었다. typed request에서 revision을 읽어 envelope와 대조하고 불일치 시 실행 전에
거부한다.

### CR-06 Dependency/test compatibility — 조치 완료

FastAPI `0.139.2` / Starlette `1.3.1`에서 legacy `httpx` TestClient가 deprecated 경고를 냈다.
Starlette package contract에 맞춰 dev test client를 `httpx2 2.7.0`으로 전환하고 경고 없는 회귀를
확인했다. OpenAPI drift를 줄이기 위해 FastAPI optional 범위를 `>=0.139,<0.140`으로 제한했다.

### CR-07 남은 운영 위험 — 후속 Gate

- OIDC issuer/JWKS, claim mapping과 key rotation 미구현
- organization/project/access-classification authorization 미구현
- arbitrary local path 대신 upload/staging/URI trust boundary 미구현
- request body size, rate limit, audit correlation, reverse proxy/mTLS 미검증
- synchronous in-process 실행만 존재; durable 202 worker/SSE/lease 미구현
- generic API에서는 사람 권한 command를 의도적으로 실행 불가

이 항목이 남아 있으므로 `deployment_ready`, `full API`, `RBAC complete`로 기록하지 않는다.

## 5. 검증 기록

| 명령 / 증거 | 결과 |
|---|---|
| `uv lock` | 136 packages resolved; FastAPI 0.139.2, Starlette 1.3.1, HTTPX2 2.7.0 |
| `uv sync --locked --dev --extra api --extra cli --extra docling` | 최종 성공; 아래 환경 복구 기록 참조 |
| API contract targeted pytest | 7 passed, 외부 network/socket 없음 |
| final harness + API targeted pytest | 10 passed; ledger/link/read-only contract 포함 |
| `uv run --no-sync ruff check .` | passed |
| 첫 `prep.ps1 test` | 108 passed, 2 failed; 아직 없던 이 리포트의 README link만 실패 |
| final `prep.ps1 validate` | 0 errors, 0 warnings |
| final `prep.ps1 test` | 110 passed in 39.47s; optional Docling excluded by contract |
| final `prep.ps1 eval` | 10 groups passed; 기존 workflow/quality claim 경계 유지 |
| `uv run --no-sync ruff check .` | passed |
| `uv run --no-sync pyright --threads 1` | 0 errors, 0 warnings |
| clean core wheel | 7 packages; AXCalib import 성공, FastAPI 미설치 확인 |
| clean `[api]` wheel | 12 packages; FastAPI 0.139.2, OpenAPI 3.1과 4 routes 확인 |

Docling과 live model은 이번 API slice에서 호출하지 않았다. Qwen 모델 품질이나 PPTX parser 품질에
대한 새 주장을 만들지 않는다.

`uv lock`은 optional Docling dependency tree의 `pypdfium2 5.12.0`이 setup blunder 사유로 yanked됐고
wheel은 5.12.1과 사실상 동일하다는 registry warning을 표시했다. 이번 slice는 Docling을 재실행하지
않았으므로 lock을 임의 승격하지 않았다. 다음 Docling contract 실행 전에 resolver refresh와
5.12.1 호환을 별도로 확인한다.

## 6. 환경 복구 기록

첫 `uv sync`는 이전 설치가 남긴 read-only
`.venv/Lib/site-packages/axcalib-0.1.0a0.dist-info`를 제거하지 못해 access denied로 실패했다.
실행 중 Python process가 없음을 확인하고 해당 local venv metadata의 read-only attribute만 해제한
뒤 다시 동기화했다. 두 번째 sync는 이전 불완전 설치의 `RECORD` 누락 경고를 냈지만 새 editable
설치가 완료됐고, 이후 `RECORD` 존재와 `axcalib 0.1.0a0`, FastAPI/HTTPX2 import를 확인했다.

## 7. 변경 Surface

- `src/axcalib/api/`: auth/grant, HTTP model, FastAPI factory
- `src/axcalib/runtime/execution.py`: hash-verified non-executing `inspect`
- `tests/contract/test_runtime_api_contract.py`: auth, grant, actor injection, owner/scope, idempotency,
  revision, integrity와 OpenAPI parity
- `docs/api/openapi.runtime.v1alpha1.json`, export script
- ADR-022, API manual, README, workflow/module diagrams와 infographic
- `pyproject.toml`, `uv.lock`

## 8. 다음 권장 Slice

1. principal과 domain actor를 bind하는 project/education 전용 typed command endpoint
2. local path를 받지 않는 artifact upload/staging/content-hash contract
3. approved OIDC/JWKS와 organization/project/access-classification RBAC threat model
4. synchronous run을 durable 202 worker, poll/SSE와 resume로 확장
5. 이후 Review Web은 API가 반환한 state/allowed command만 소비

## 9. 참고

- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI OpenAPI 3.1 client generation](https://fastapi.tiangolo.com/advanced/generate-clients/)
- [FastAPI PyPI](https://pypi.org/project/fastapi/)
- [HTTPX2 PyPI](https://pypi.org/project/httpx2/)
