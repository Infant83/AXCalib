# API / Web / App 적용

## 원칙

Library가 의미의 기준이다. CLI, FastAPI, Worker는 같은 application service와 schema를 호출한다.
Web App은 상태와 `allowed_commands`를 API에서 받아 표시하며 별도의 승인 로직을 프론트엔드에 복사하지
않는다.

```text
Python Library
  ├─ CLI
  ├─ FastAPI / OpenAPI 3.1
  ├─ local or distributed Worker adapter
  └─ Human Review Web App
```

## API 계약

- request/response는 versioned OpenAPI 3.1과 JSON Schema Draft 2020-12를 따른다.
- request option은 `additionalProperties: false`인 allowlisted typed field만 받는다.
- 동기·비동기 의미는 같고 비동기 Library 함수에는 `a` 접두어를 사용한다.
- 긴 작업은 `202 Accepted`, `Location`, `Retry-After`로 polling reference를 반환한다.
- project read, decision replay, poll/cancel은 인증 principal과 resource scope를 다시 확인한다.
- report 결과에서 로컬 filesystem URI나 secret을 노출하지 않는다.

현재 계약 artifact는 메인 저장소의 `docs/api/openapi.runtime.v1alpha1.json`과
`docs/api/openapi.v1alpha1.json`이다. 현재 구현은 local Alpha이며 운영 OIDC server가 아니다.

## Web Review App 예상 화면

1. Review Queue: 등록·완료 HITL 대기, SLA, 증거 부족 표시
2. Project Dossier: 목표, KPI, revision, mentor와 artifact hash
3. Evidence Review: criterion별 locator, 원문 발췌, 판단불가 이유
4. Similar Case Panel: 공통점·차이점·적용 한계와 corpus snapshot
5. Decision Drawer: 승인·보류·반려·추가자료 요청과 rationale
6. Audit Timeline: Agent 출력, reviewer 수정, 알림, 상태전이를 구분

사람이 결정하기 전에 점수만 크게 보여 주거나 유사도 순위로 자동 승인하지 않는다. 구현되지 않은
기능은 UI에서 완료색으로 표시하지 않는다.

## App 통합 체크리스트

- API 응답의 `allowed_commands`만 활성화했는가?
- stale revision과 permission denied를 일반 오류와 구분하는가?
- Agent 제안과 관리자 최종결정을 시각적으로 분리했는가?
- evidence locator에서 허용된 발췌만 보여 주는가?
- 요청 재시도에 idempotency key를 유지하는가?
- 실제 사용자 신원·assignment source가 승인되지 않았으면 fail-closed하는가?

권한과 업로드 경계가 승인되기 전에는 [보안과 HITL](Security-and-HITL)의 운영 NO-GO를 적용한다.
