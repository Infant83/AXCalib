# AXCalib Risk Register

| ID | 위험 | 영향 | 현재 통제 | 상태 |
|---|---|---|---|---|
| R-001 | Agent의 hallucination 또는 unsupported claim | 잘못된 통과·탈락 제안 | criterion evidence와 관리자 HITL checklist | Open |
| R-002 | historical case 편향과 outcome leakage | 과거 판단을 답처럼 복제 | stage filter, commonality/difference, 관리자 검토 | Open |
| R-003 | similarity portion 과대 설정 | 평가기준보다 검색값이 지배 | 기본 0, 0.25 초과 warning, human final decision | Open |
| R-004 | 승인요청 알림 실패 | 관리자 검토 누락 | 알림 성공 전 HITL pending 전이 금지, 향후 outbox/retry | Mitigated in reference contract |
| R-005 | 선택적 멘토 흐름의 승인 우회 | 완료자료 품질 저하 | mentor가 배정되면 mentor 승인 강제 | Mitigated in reference contract |
| R-006 | 평가 중 dossier 변경 | stale 결과 자동 반영 | revision/hash snapshot과 conflict 처리 계획 | Planned WP-01 |
| R-007 | 실제 데이터 또는 secret 유출 | 개인정보·보안 사고 | synthetic-only 기본, env 이름만 기록, live test 제외 | Open |
| R-008 | GitLab MR 또는 email provider 종속 | 운영 이식성 저하 | NotificationPort와 adapter 분리 | Planned |
| R-009 | 국소 pipeline 과분할 | 경계·버전·운영 복잡도 증가 | 독립 업무결과와 재사용자가 있을 때만 pipeline 승격 | Planned |
| R-010 | script, CLI, API별 로직 복제 | interface마다 판정과 오류 의미가 달라짐 | thin adapter와 interface-parity contract test | Planned |
| R-011 | 범용 workflow engine 조기개발 | Domain MVP 지연과 보안 surface 확대 | 명시적 Python composition과 allowlisted registry부터 구현 | Planned |
| R-012 | pipeline 사이 부분 side effect | 중복 평가·알림·불일치 상태 | local transaction, outbox, idempotency, durable checkpoint | Planned WP-01/06 |
| R-013 | 구조도·module board와 코드 drift | 잘못된 작업순서와 완료판단 | 필수 문서 validation, same-change-set 규칙, Exit Evidence 기반 상태승격 | Mitigated in harness contract |
