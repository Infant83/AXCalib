# WP-06.I4 Identity and Upload Decision Packet

- 상태: **결정 입력 대기 / local reference만 구현**
- 적용 Gate: G4 Interfaces
- 대상 승인자: Product Owner, Security Owner, Identity/Platform Owner, Data Owner
- 현재 금지: 실제 계정 생성, 사내 token 반입, 원격 JWKS 호출, 운영 upload, 사내 데이터 전송

이 문서는 운영값을 대신 정하지 않는다. 각 행의 `승인값`과 `Owner`가 채워지고 Exit Evidence가
제출되기 전까지 AXCalib API는 운영 승격 **NO-GO**다. 권장안은 논의를 시작하기 위한 안전한
기준이며 회사 정책 승인이 아니다.

## 1. Identity / OIDC 결정표

| 결정 항목 | 안전한 권장안 | 승인값 | Owner | 필요한 Exit Evidence |
|---|---|---|---|---|
| token 종류 | RFC 9068 JWT access token; ID token은 API access token으로 수용하지 않음 | TBD | Identity + Security | `typ=at+jwt`, ID-token substitution negative test |
| issuer | metadata와 token `iss`가 완전히 같은 HTTPS URI | TBD | Identity | 승인된 metadata export, exact-match test |
| API audience | AXCalib resource server 전용 audience 하나 | TBD | Product + Identity | 다른 audience token 거부 test |
| discovery / JWKS URI | 승인된 metadata의 HTTPS `jwks_uri`; token의 `jku/x5u`는 사용하지 않음 | TBD | Identity + Platform | allowlisted egress, redirect/DNS/SSRF review |
| signature algorithm | 현재 reference는 RS256/PS256/ES256만; `none`, HS 계열 금지 | TBD | Security | algorithm confusion negative test, key-size policy |
| key rotation | `kid`가 유일한 issuer-bound key set; bounded cache와 refresh, 이전 key 유예기간 명시 | TBD | Identity + Platform | 새 key/이전 key/unknown key/IdP outage drill |
| 필수 표준 claim | `iss`, `sub`, `aud`, `exp`, `iat`, `jti`, `client_id` | TBD | Identity | 누락·type·expiry·future-time test |
| role claim 이름 | AXCalib 전용 claim 권장; arbitrary group 문자열을 직접 role로 사용하지 않음 | TBD | Product + Identity | claim vocabulary와 versioned mapping |
| scope claim 이름 | API resource 전용 scope; request body가 scope를 만들 수 없음 | TBD | Product + Identity | route별 scope matrix test |
| organization claim | immutable organization identifier; 표시명 사용 금지 | TBD | Product + Identity | tenant 이동·퇴사·조직 미지정 test |
| role mapping | 외부값 → `ApiRole` exact allowlist; 한 token이 여러 AXCalib role로 모호하면 거부 | TBD | Product + Security | 전체 role mapping table과 ambiguity test |
| scope mapping | 외부값 → AXCalib scope exact allowlist; 동적 project/enrollment scope 발급 책임 명시 | TBD | Product + Security | command/resource별 positive/negative test |
| token 수명 / clock skew | 짧은 access token, reference 최대 15분·skew 30초; 운영값 별도 승인 | TBD | Security + Platform | NTP/clock drift와 boundary test |
| subject lifecycle | `issuer + sub`를 안정 식별자로 사용; email/사번 표시값으로 대체하지 않음 | TBD | Identity + Privacy | rename/re-hire/merge 처리 정책 |
| 계정 회수 / revocation | 짧은 수명 + IdP disable; 즉시 회수 요구 시 introspection/deny source 별도 설계 | TBD | Identity + Security | 퇴사·권한회수 SLA와 drill |
| 교육 배정 source | mentor/instructor/program assignment의 authoritative store와 갱신/회수 책임 | TBD | Education Product | assignment 생성·변경·회수·tenant test |
| 장애 동작 | invalid token은 401, key source/config 장애는 503; 이전 검증 결과로 새 요청 승인 금지 | TBD | Platform + Security | outage/stale-cache test와 runbook |
| 감사 | policy ID/version, issuer, key snapshot version과 actor subject를 기록; raw token/전체 claim 미기록 | TBD | Security + Audit | redaction test, retention/접근권한 |

현재 `src/axcalib/api/oidc.py`는 위 표의 cryptographic/claim validation reference만 제공한다.
`StaticJwkSetProvider`는 synthetic/offline 검증용이다. remote discovery, HTTP fetch, cache, refresh,
revocation, authoritative assignment 연동은 아직 없다.

## 2. Immutable upload 결정표

| 결정 항목 | 안전한 권장안 | 승인값 | Owner | 필요한 Exit Evidence |
|---|---|---|---|---|
| service / trust boundary | API가 local path를 받지 않고 승인된 staging service의 opaque object ID만 받음 | TBD | Platform | architecture/data-flow review |
| object identity | bucket/key 표시값 대신 immutable version ID + SHA-256 | TBD | Platform | overwrite/TOCTOU negative test |
| creator / tenant ACL | principal, organization, project purpose를 staging record에 고정 | TBD | Security + Product | cross-tenant IDOR test |
| upload URL | 짧은 만료의 signed URL; content type/length/version 조건 고정 | TBD | Platform + Security | replay/expiry/oversize test |
| type / size | allowlisted PPTX/PDF/image와 업무별 한도; 확장자만 신뢰하지 않음 | TBD | Product + Security | magic/container/type confusion test |
| archive safety | zip entry 수·압축비·총 해제 크기·nested archive 제한 | TBD | Security | zip-bomb corpus test |
| malware | 비동기 scan 완료 전 resolver가 artifact를 반환하지 않음 | TBD | Security + Platform | clean/infected/scan-timeout test |
| classification / DLP | 허용 access class만 지정 model/storage 경계로 이동 | TBD | Data + Security | classification policy와 egress test |
| encryption / key | TLS와 at-rest encryption, key rotation/접근로그 | TBD | Platform + Security | configuration evidence |
| retention / deletion | stage·approved·rejected별 보존기간과 legal hold | TBD | Data + Legal | lifecycle/deletion audit |
| promotion transaction | hash/scan/ACL 확인 뒤 dossier revision에 version/hash를 고정; 실패 시 orphan 정리 | TBD | Platform | crash/retry/reconcile test |
| download / report access | project/report/evidence 전용 authorization과 enumeration 방지 | TBD | Product + Security | object-level authorization test |
| incident response | quarantine, re-scan, compromised hash/key 대응 | TBD | Security | incident runbook와 drill |

현재 `StagedArtifactResolver`는 opaque ID, principal/purpose, size/media/hash를 검사하는 local port다.
실제 object version, malware scanner, signed URL, ACL, retention service는 구현되지 않았다.

## 3. 승인 완료조건

운영 구현을 시작하려면 다음 자료가 한 change set 또는 승인 기록으로 연결되어야 한다.

1. 위 표의 모든 운영 `승인값`과 accountable Owner
2. issuer metadata/JWKS의 비밀정보 없는 승인 snapshot
3. versioned role/scope/organization/assignment mapping
4. token lifetime, key rotation, outage, revocation runbook
5. immutable object lifecycle, malware/DLP, ACL, retention/deletion 정책
6. synthetic contract test와 승인된 비식별 staging test 계획
7. ADR, threat model, risk register와 rollback/no-go 기준

승인 뒤에도 관리자 HITL, notification, mentor guard, revision/stale guard는 token claim이나 설정으로
끄지 않는다.

## 4. 표준 근거

- [RFC 8725: JSON Web Token Best Current Practices](https://www.rfc-editor.org/rfc/rfc8725)
- [RFC 9068: JWT Profile for OAuth 2.0 Access Tokens](https://www.rfc-editor.org/rfc/rfc9068)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0-final.html)
- [PyJWT API validation guidance](https://pyjwt.readthedocs.io/en/stable/api.html)
