# AXCalib Decisions

| ID | 날짜 | 상태 | 결정 |
|---|---|---|---|
| D-001 | 2026-07-12 | Accepted | 공식 이름은 AXCalib / AX Certification Agent Library다. |
| D-002 | 2026-07-12 | Accepted | 사용자 기준 파일은 project별 단일 dossier이고 평가는 immutable snapshot을 사용한다. |
| D-003 | 2026-07-14 | Accepted | 등록·완료 평가 결과는 Agent 초안이며 관리자 승인 전에는 최종 상태로 전이하지 않는다. |
| D-004 | 2026-07-14 | Accepted | 두 HITL Gate 진입에는 승인요청 알림 event가 필수다. offline에서는 recording adapter로 검증한다. |
| D-005 | 2026-07-14 | Accepted | 멘토 배정은 선택이지만 배정된 경우 완료평가 제출 전 멘토 승인이 필수다. |
| D-006 | 2026-07-14 | Accepted | registration/completion retrieval은 stage를 분리하고 관리자 지정 adapter를 사용한다. |
| D-007 | 2026-07-14 | Proposed | historical similarity portion 기본값은 0이며 0.25 초과는 policy warning과 별도 승인을 요구한다. |
| D-008 | 2026-07-14 | Open | Web frontend와 주 디자인은 제안안 중 사용자 선택 후 확정한다. |
| D-009 | 2026-07-14 | Accepted | 요소 모듈을 typed 국소 pipeline으로 완결하고 versioned total workflow가 이를 연결한다. script/CLI/API/worker는 같은 Library 구현을 사용한다. |
| D-010 | 2026-07-14 | Accepted | workflow Mermaid blueprint, SVG 인포그래픽과 M00~M13 module control board를 구현상태·Exit Evidence와 함께 유지한다. |

세부 근거는 `docs/adr/`의 ADR을 따른다.
