# ADR-028: Provider-neutral OIDC/JWKS access-token reference

- 상태: Accepted for local contract
- 날짜: 2026-07-24
- 범위: WP-06.I4.0-1 / M02, M12

## Context

API Alpha는 deployment가 주입하는 `TokenVerifier` 뒤에서 principal을 사용하지만 실제 JWT signature,
issuer, audience와 claim mapping을 검증하지 않았다. 반대로 사내 issuer/audience/claim 이름과
revocation 정책은 아직 승인되지 않았으므로 특정 IdP나 계정을 임의로 연결할 수 없다.

## Decision

1. JWT access-token 검증은 optional `identity` extra의 `OidcTokenVerifier`로 제공한다. Core Library는
   PyJWT, cryptography, FastAPI에 의존하지 않는다.
2. token은 RFC 9068 profile로 취급해 `at+jwt`, exact issuer/audience, expiry/issued-at/JTI/client ID와
   asymmetric signature를 검증한다. ID token, `none`, symmetric algorithm과 token-controlled
   `jku/x5u/x5c`는 거부한다.
3. algorithm 목록은 policy가 가진 RS256/PS256/ES256 allowlist에서만 선택한다. token header가
   검증 algorithm 목록을 결정하지 않는다.
4. `JwkSetProvider`는 policy의 issuer와 JWKS URI에 고정된 immutable snapshot을 반환한다. key `kid`는
   유일하고 key algorithm/use/key-ops/material이 검증돼야 한다.
5. 외부 role/scope는 versioned exact mapping을 통과해야 한다. unknown 또는 ambiguous 값,
   organization 누락은 기본 reference에서 거부한다.
6. invalid token은 `None`으로 401에 연결하고 provider/configuration 장애는 예외로 503에 연결한다.
   token과 raw claims는 dossier, audit, checkpoint 또는 response에 저장하지 않는다.
7. remote discovery/JWKS HTTP adapter, cache/rotation/revocation, 실제 assignment source와 operating
   configuration은 승인 뒤 별도 slice로 구현한다. `StaticJwkSetProvider`는 운영 승격 증거가 아니다.

## Consequences

- local signed fixture로 cryptographic validation과 기존 resource authorization 연결을 재현할 수 있다.
- issuer나 role mapping을 코드에 하드코딩하지 않고 IdP 교체가 가능하다.
- 운영 adapter가 없는 현재 상태에서는 network key rotation과 account revocation을 검증할 수 없다.
- strict unknown-role/scope 정책은 전용 AXCalib claim vocabulary를 요구한다. 실제 IdP가 공용 claim을
  사용한다면 Security Owner가 별도 mapping/ignore 정책을 승인하고 회귀 test를 추가해야 한다.

## Evidence

- `src/axcalib/api/oidc.py`
- `tests/unit/test_oidc_identity.py`
- `tests/contract/test_oidc_api_contract.py`
- `docs/security/identity-upload-decision-packet.md`
- `docs/security/api-alpha-threat-model.md`
