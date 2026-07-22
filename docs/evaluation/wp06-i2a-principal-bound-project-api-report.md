# WP-06.I2a Principal-bound Project API 개발·리뷰 리포트

- 날짜: 2026-07-22
- 범위: project registration, registration/completion HITL decision, staged artifact boundary
- 판정: **local contract verified; operational auth/upload NO-GO**

## 1. 결과

기존 runtime API에 세 개의 project resource command를 추가했다.

| Method | Route | 구현된 의미 |
|---|---|---|
| POST | `/v1/projects` | verified owner/admin + scope/org, staged PPTX/sidecar hash 검증, idempotent dossier 등록 |
| POST | `/v1/projects/{project_id}/decisions/registration` | 관리자 principal로 approve/reject, 필수 expected revision |
| POST | `/v1/projects/{project_id}/decisions/completion` | 관리자 principal로 accept/not_accept, 필수 expected revision |

request는 actor나 local path를 받지 않는다. 등록 audit와 두 결정 audit의 actor는 bearer token을
검증한 `ApiPrincipal.subject`로 고정된다. organization/scope/stale mismatch는 dossier revision을
바꾸기 전에 거부된다.

## 2. 구현 리뷰

### 발견하고 수정한 문제

1. 첫 idempotency replay 구현은 같은 stable project ID에 새 random transaction event를 만들어
   `dossier_target_missing_event`로 충돌했다. domain create를 다시 실행하기 전에 existing dossier의
   request/hash/context/audit를 비교하고 exact match만 replay하도록 수정했다.
2. dossier만 있고 creation audit가 빠진 부분 commit을 정상 replay로 오인할 수 있었다.
   principal-bound `project_created` audit가 dossier event set과 일치하지 않으면 integrity 409로
   닫도록 보강했다.
3. API layer에서 revision만 확인하면 다른 delivery adapter가 stale decision을 통과시킬 수 있었다.
   `expected_revision`을 facade와 `LocalProjectService`까지 전달해 domain-owned guard로 만들었다.
4. Library registry의 project pipeline을 직접 공개하면 caller path/actor가 다시 열릴 수 있어,
   generic route는 그대로 authority field를 금지하고 별도 resource endpoint만 추가했다.
5. staging 파일을 먼저 다시 읽는 replay는 보관기간이 끝난 정상 재시도를 실패시켰다. claim의
   media/size를 먼저 제한한 뒤 persisted content/context/audit exact match를 확인하고, 신규 생성일
   때만 resolver를 호출하도록 순서를 바꿨다.
6. API hash 검사와 dossier commit 사이 파일 교체를 저장 뒤에 발견하면 잘못된 dossier가 남을 수
   있었다. expected proposal/sidecar hash를 Library create 직전까지 전달해 transaction 전에
   거부하고, 이후 평가도 frozen proposal hash를 재검증하도록 수정했다.
7. project route를 기존 app factory에 계속 쌓으면 1,000줄에 가까워져 education 권한과 섞일
   위험이 있었다. 공통 redacted problem과 principal-bound project router를 별도 API 요소 모듈로
   분리하고 같은 generated OpenAPI/contract를 재검증했다.

### 유지한 경계

- Core Library는 FastAPI에 의존하지 않는다.
- staging resolver와 token verifier 기본값은 모두 거부한다.
- HTTP response/OpenAPI에 resolved local path, dossier URI, token 값을 넣지 않는다.
- 관리자 role만으로는 부족하며 scope, organization, revision과 domain transition을 모두 검사한다.
- education command는 이번 endpoint에 억지로 포함하지 않고 WP-06.I2b로 분리했다.

## 3. 검증

- project API contract: 5 passed
- runtime + project API targeted contract: 12 passed
- full lightweight offline test: 115 passed
- evaluation harness: 10 groups passed
- Ruff check: passed; new API/project/test module format check passed
- full low-memory Pyright: 0 errors, 0 warnings
- workspace validation: 0 errors, 0 warnings
- generated OpenAPI: implemented route/schema와 committed artifact exact match
- clean `[api]` wheel: 12 packages, FastAPI 0.139.2, OpenAPI 3.1.0, 7 routes

단계 종료 수치는 `PROJECT_STATE.md`의 HIST-2026-07-22-007에도 고정했다. 저장소 전체 `ruff format
--check`는 기존 53개 파일을 포맷 대상으로 보고해 일괄 변경하지 않았다. 새 API router/problem,
project module과 contract test 범위는 format check를 통과했다. 외부 모델, Docling, 실제 OIDC,
socket server, 실제 upload, 사내 데이터와 운영 notification은 호출하지 않았다.
첫 wheel smoke 한 줄은 PowerShell f-string 인용 오류로 Python 실행 전 SyntaxError가 났고, 이미 설치된
격리 환경에서 인용만 고쳐 재실행해 위 결과를 확인했다.

## 4. 남은 위험과 다음 단계

- `StagedArtifactResolver`는 approved immutable object version을 반환해야 한다. 현재 local file은
  hash 검증 뒤 교체되는 TOCTOU를 완전히 제거하지 못한다.
- reverse proxy body limit/rate limit/malware scan과 실제 upload lifecycle은 없다.
- OIDC/JWKS, claim mapping, project read/list/report authorization은 없다.
- 관리자 decision response를 받은 뒤 연결이 끊기면 같은 expected revision 재시도는 stale 409가 된다.
  중복 mutation은 막지만 semantic replay와 project status GET이 없어 운영 client 복구 계약은 미완료다.
- WP-06.I2b에서 education enrollment의 learner/mentor/instructor/administrator scope와 program version
  binding을 별도로 구현한다.
- 이후 WP-06 worker slice에서 202, poll/SSE, distributed idempotency/lease를 검증한다.

정확한 공격면과 운영 NO-GO 조건은
[API Alpha Threat Model](../security/api-alpha-threat-model.md), 결정 근거는
[ADR-023](../adr/ADR-023-principal-bound-project-api.md)을 따른다.
