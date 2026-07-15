# ADR-014: 최소 우선 인터페이스와 점진적 설정·OpenAPI 계약

- 상태: Accepted
- 날짜: 2026-07-15
- 결정자: Product Owner 승인 대기 중인 pre-development baseline
- 관련: WORK_SPEC v0.3-p1, ADR-013, `docs/api/openapi.v1alpha1.json`

## 맥락

AXCalib는 안전한 기본값으로 바로 시작할 수 있어야 하지만, 온프레미스 모델·검색·알림을
연결하는 전문 사용자에게는 충분한 제어권도 제공해야 한다. 모든 옵션을 첫 화면이나 첫 함수에
노출하면 학습 비용과 오설정 위험이 커진다. 반대로 HITL, stale guard, 최종 결정 권한처럼 제품의
안전 불변조건을 설정값으로 만들면 보호 경계를 우회할 수 있다.

## 결정

1. 초보자의 첫 진입점은 `AXCalib().evaluate(...)`와 의미가 같은
   `await AXCalib().aevaluate(...)` 하나로 유지한다.
2. 기본 `config/axcalib.toml`은 synthetic/offline 실행에 필요한 작은 설정만 가진다.
   전문 설정은 `config/axcalib.expert.example.toml`에서 시작한다.
3. 설정 우선순위는 다음과 같다.

   `코드 소유 불변조건 > 안전 기본값 > TOML profile > 환경변수 secret/endpoint > allowlist된 요청 옵션 > policy guard`

4. 관리자 HITL, 승인요청 알림, 사람 최종결정, revision freeze/stale guard, mentor guard는
   설정 가능한 boolean이 아니다. API request와 TOML 양쪽에서 보호 필드 자체를 제공하지 않는다.
5. 알 수 없는 설정과 요청 필드는 묵인하지 않고 실패시킨다. 적용된 설정에는 source map과
   비밀을 제외한 effective-config hash를 실행기록에 남긴다.
6. API의 pre-implementation 계약은 OpenAPI 3.1.0과 JSON Schema Draft 2020-12를 사용한다.
   요청별 제어는 `options` 안의 allowlist된 typed JSON만 허용한다.
7. Python 3.12 표준 `tomllib` 호환을 위해 작성 가능한 설정 문법은 TOML 1.0 범위로 제한한다.
   TOML 1.1과 OpenAPI 3.2 채택은 각각 parser/toolchain 호환성 spike 뒤 별도 ADR로 판단한다.
8. CLI, API, worker는 같은 application service와 동일 input/output/error 의미를 사용한다.

## 결과

- 첫 사용자는 모델·검색·알림 세부사항을 몰라도 offline fixture로 계약을 학습할 수 있다.
- 전문 사용자는 profile과 요청별 allowlist를 조합하되 권한 경계는 바꿀 수 없다.
- OpenAPI artifact에서 SDK, validation, contract test를 생성할 수 있다.
- 향후 옵션 추가는 schema, OpenAPI, 예제, parity test를 같은 변경 세트에서 갱신해야 한다.

## 기각한 대안

- 모든 파라미터를 단일 함수에 노출: 발견성보다 오설정과 버전 결합 비용이 크다.
- 임의 Python import path/graph를 config에서 실행: 공급망·코드 실행 위험과 재현성 저하가 있다.
- HITL을 `true/false` 설정으로 노출: 제품의 사람 책임 불변조건과 충돌한다.
- OpenAPI 3.2 즉시 채택: 최신 표준이지만 MVP 후보 toolchain과 생성기 호환을 먼저 검증해야 한다.

## 검증 의무

- default/expert TOML parse 및 runtime schema 검증
- unknown/protected key 거부
- OpenAPI 3.1 parse, example validation, `additionalProperties: false`
- sync/async/CLI/API result parity
- effective-config hash와 secret redaction

## 표준 근거

- [OpenAPI Specification 3.1.0](https://spec.openapis.org/oas/v3.1.0.html)
- [OpenAPI Specification 3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)
- [FastAPI First Steps](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [TOML 1.0.0](https://toml.io/en/v1.0.0)
