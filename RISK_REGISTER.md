# AXCalib Risk Register

| ID | 위험 | 영향 | 현재 통제 | 상태 |
|---|---|---|---|---|
| R-001 | Agent의 hallucination 또는 unsupported claim | 잘못된 통과·탈락 제안 | criterion evidence와 관리자 HITL checklist | Open |
| R-002 | historical case 편향과 outcome leakage | 과거 판단을 답처럼 복제 | stage filter, commonality/difference, 관리자 검토 | Open |
| R-003 | similarity portion 과대 설정 | 평가기준보다 검색값이 지배 | 기본 0, 0.25 초과 warning, human final decision | Open |
| R-004 | 승인요청 알림 실패 | 관리자 검토 누락 | 알림 성공 전 HITL pending 전이 금지와 integration test; durable outbox/retry는 미구현 | Mitigated offline; operational open |
| R-005 | 선택적 멘토 흐름의 승인 우회 | 완료자료 품질 저하 | mentor가 배정되면 mentor 승인 강제 및 scenario test | Mitigated offline |
| R-006 | 평가 중 dossier 변경 | stale 결과 자동 반영 | revision/hash snapshot, sequential stale write 거부; multi-process lock/result 격리는 미구현 | Partially mitigated |
| R-007 | 실제 데이터 또는 secret 유출 | 개인정보·보안 사고 | synthetic-only 기본, env 이름만 기록, live test 제외 | Open |
| R-008 | GitLab MR 또는 email provider 종속 | 운영 이식성 저하 | NotificationPort와 adapter 분리 | Planned |
| R-009 | 국소 pipeline 과분할 | 경계·버전·운영 복잡도 증가 | 독립 업무결과와 재사용자가 있을 때만 pipeline 승격 | Planned |
| R-010 | script, CLI, API별 로직 복제 | interface마다 판정과 오류 의미가 달라짐 | working script는 `AXCalib` pipeline만 호출; CLI/API parity는 미구현 | Partially mitigated |
| R-011 | 범용 workflow engine 조기개발 | Domain MVP 지연과 보안 surface 확대 | 명시적 Python composition과 allowlisted registry 구현 | Mitigated for slice |
| R-012 | pipeline 사이 부분 side effect | 중복 평가·알림·불일치 상태 | atomic file replace와 fail-closed는 구현; cross-file transaction/outbox/idempotency는 미구현 | Open hardening |
| R-013 | 구조도·module board와 코드 drift | 잘못된 작업순서와 완료판단 | 필수 문서 validation, same-change-set 규칙, Exit Evidence 기반 상태승격 | Mitigated in harness contract |
| R-014 | Excalibur 비유가 Agent 자동인증으로 해석됨 | 사람 책임 약화·제품 신뢰 훼손 | 고정 문장, 권한 diagram, HITL 경계와 교육용 caption | Mitigated in predev contract |
| R-015 | 옵션 과다로 첫 사용과 운영 구성이 실패 | adoption 저하·오설정 | minimal facade/default와 별도 expert profile | Mitigated in predev contract |
| R-016 | TOML/API로 필수 HITL·알림을 우회 | 무권한 인증 상태 전이 | protected field 미제공, config validation, administrator-only state guard test | Mitigated offline; API open |
| R-017 | OpenAPI/schema/구현 drift | SDK와 API 결과 불일치 | artifact-first example·contract·parity test | Planned WP-06 |
| R-018 | 최신 표준을 성급히 채택해 toolchain 불일치 | 생성기/validator 상호운용 실패 | OpenAPI 3.1/TOML 1.0 baseline, 3.2/1.1 spike | Open |
| R-019 | tutorial이 구현되지 않은 기능을 완료처럼 보임 | 잘못된 기대와 감사 오류 | pre-implementation 라벨, PROJECT_STATE/Exit Evidence 연동 | Mitigated in docs |
| R-020 | image-only PPTX sidecar의 요약·tag 편향 | 잘못된 criterion 근거와 과대평가 | source hash 고정, reviewed-sidecar 표기, 명시 tag만 사용, sidecar 부재 시 insufficient | Open until parser/model benchmark |
| R-021 | local actor ID를 실제 관리자 인증으로 오해 | demo 결과가 운영 승인처럼 사용됨 | `explicit_command_input`과 `offline_unverified_actor` 기록, API/RBAC 전 운영 금지 | Mitigated in demo; auth open |
