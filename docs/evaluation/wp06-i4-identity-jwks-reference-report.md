# WP-06.I4 Identity Policy and OIDC/JWKS Reference Report

- Date: 2026-07-24
- Scope: I4-0 decision packet + I4-1 provider-neutral local signed access-token contract
- Gate impact: G4 local identity evidence added; operational deployment remains **NO-GO**

## 1. Outcome

운영 issuer, 계정, 사내 token 또는 remote endpoint를 만들지 않고 두 단계를 완료했다.

1. `identity-upload-decision-packet.md`가 identity와 immutable upload의 결정 항목을 승인값, Owner,
   Exit Evidence로 분리한다. 빈 항목은 운영 차단조건이다.
2. optional `identity` extra의 `OidcTokenVerifier`가 deployment policy와 issuer-bound
   `JwkSetProvider`를 기존 `TokenVerifier` port에 연결한다.

local RSA/EC signed fixture에서는 정상 token만 `ApiPrincipal`로 변환됐다. signature 변조, 만료,
issuer/audience/type/algorithm/key/claim/role/scope/organization 오류는 거부되고 key source/config
불일치는 HTTP 503으로 분리됐다. 이는 실제 사내 SSO 연결, key rotation, account revocation 또는
penetration test 결과가 아니다.

## 2. Implemented contract

| Surface | Contract |
|---|---|
| Packaging | Core dependency 불변; `identity = FastAPI + PyJWT[crypto]` optional extra |
| Policy | extra-forbid/frozen ID/version, exact HTTPS issuer/JWKS URI, audience, algorithm·claim mapping |
| JWT profile | RFC 9068 `at+jwt`, required iss/sub/aud/exp/iat/jti/client_id |
| Crypto | policy-owned RS256/PS256/ES256 allowlist, unique kid, sig/verify public JWK |
| Key source | issuer와 JWKS URI에 정확히 bind된 provider snapshot; token URL 사용 안 함 |
| Authorization mapping | external role/scope exact allowlist, one mapped role, required organization |
| Failure | invalid token → `None`/401; provider/config failure → exception/503 |
| Data minimization | raw token/전체 claim을 dossier, run checkpoint, response에 저장하지 않음 |

## 3. Code-review findings

1. **직접 JWT/crypto 구현 위험**: 표준 검증 library를 optional extra로 사용하고 서명 primitive를
   재구현하지 않았다.
2. **algorithm confusion**: decode algorithm을 token header로 만들지 않고 policy allowlist에서
   전달한다. `none`과 HS 계열은 policy schema 단계부터 금지한다.
3. **ID/access-token substitution**: `typ=at+jwt|application/at+jwt`만 허용해 일반 JWT/ID token을
   거부한다.
4. **token-controlled key source/SSRF**: `jku`, `x5u`, `x5c`, unknown critical header를 거부하며
   verifier는 policy의 provider만 호출한다.
5. **issuer/key confusion**: snapshot의 issuer와 JWKS URI를 policy와 다시 비교하고 duplicate/unknown
   `kid`를 거부한다.
6. **claim-to-authority 과신**: 외부 role/scope 문자열을 `ApiRole`과 API scope로 직접 신뢰하지 않고
   versioned exact binding을 요구한다. unknown/ambiguous mapping은 fail closed다.
7. **dependency 장애 은폐**: invalid credential과 key provider/config 장애를 401/503으로 구분한다.
   장애 중 이전 principal을 새 요청에 재사용하는 cache는 없다.
8. **민감 token 보존**: API E2E 뒤 workspace JSON 전체에 bearer token이 없음을 검사한다.
9. **Windows 환경 동기화**: 전체 `uv sync --all-extras --dev`는 기존 editable dist-info 제거 중
   access denied로 실패했다. lockfile은 정상 갱신됐고 새 dependency만 `.venv`에 설치해 targeted
   test를 실행했다. clean-wheel smoke에서 optional extra 격리를 별도로 확인했다.
10. **남은 audit gap**: verifier는 `policy_reference`와 JWK snapshot version을 알고 있지만 현재
    project/education domain audit에 그 값을 자동 보존하지 않는다. remote adapter 구현 때
    secret-free identity validation metadata를 audit event에 연결해야 한다.
11. **정적검사 환경 불일치**: direct Pyright가 실행 파일이 있는 `.venv` 대신 base Conda package
    path를 읽어 FastAPI missing-import를 보고했다. `pyproject.toml`에 workspace `.venv`를 고정한 뒤
    같은 direct 명령이 0 errors/0 warnings로 통과했다.

## 4. Verification evidence

| Check | Result |
|---|---|
| Identity unit + API contract | 24 passed |
| Positive algorithms | RS256, PS256, ES256 |
| Negative token cases | tamper, expiry, issuer/audience/type, HS, key/header, claim/mapping/org, size |
| HTTP integration | valid principal/Library run 200, invalid 401, provider mismatch 503 |
| Full split regression | 160 passed: unit 108, integration 31, contract 21 |
| Evaluation harness | 10 groups passed |
| Static review | `ruff check .` passed; Pyright 0 errors/0 warnings; new Python format 3/3 |
| Workspace contract | `prep.ps1 validate` 0 errors/0 warnings |
| Wiki contract | targeted 9 passed; dependency-free CI contract 1 passed; Wiki validation 0 errors |
| Packaging smoke | clean core wheel has no FastAPI/PyJWT; clean `[identity]` imports FastAPI 0.139.2, PyJWT 2.13.0 and verifier |
| Visual review | two stakeholder SVGs rendered; XML/title/desc and status labels checked |
| GitHub delivery | main `7052530`; Actions `30050877129` jobs 2/2, annotations 0/0; Wiki `49b1fbc`; pages 4/4 HTTP 200 |

Repository-wide `ruff format --check src tests harness scripts examples evals`는 이번 변경에서
일괄 수정하지 않은 51개 파일의 기존 formatting drift를 보고한다. 새 Python 파일 3개는 별도
format check를 통과했다. 상세 수치와 품질 주장 경계는 `PROJECT_STATE.md` 최신 history에도
동일하게 고정한다.

## 5. Residual risks and boundaries

- 실제 issuer/audience/claim 이름과 role/scope mapping은 승인되지 않았다.
- remote discovery/JWKS HTTPS fetch, redirect/DNS/egress policy, cache TTL, rotation과 stale-key outage
  동작이 없다.
- account disable/revocation, subject lifecycle과 authoritative education assignment source가 없다.
- `StaticJwkSetProvider`는 local fixture다. 장기 pinned key를 운영 rotation 대신 사용하지 않는다.
- immutable upload/object version/ACL/malware/DLP/retention은 구현되지 않았다.
- reverse proxy, rate limit, socket load, dependency/security scan과 penetration test를 수행하지 않았다.
- current strict unknown role/scope rejection은 AXCalib 전용 claim vocabulary를 전제로 한다. 공용 claim을
  쓰려면 별도 승인 정책과 test가 필요하다.

## 6. Next quality slice

checkpoint 뒤 `WP-00.Q1 goal-alignment-usability-example-audit`을 실행한다. T1/WP/Gate trace matrix,
public facade 단순성, 모든 script의 thin-adapter 여부, clean package와 EX-01~EX-12 정상·오류·경계
example self-check를 검증한다. 그 뒤 승인된 운영값이 있을 때만 remote identity/upload adapter를
구현한다.

## 7. Standards

- [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725)
- [RFC 9068](https://www.rfc-editor.org/rfc/rfc9068)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0-final.html)
- [PyJWT validation API](https://pyjwt.readthedocs.io/en/stable/api.html)
