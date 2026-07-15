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
| D-011 | 2026-07-15 | Accepted | Excalibur는 사람 권한을 기억시키는 비유이며 공식 어원이나 자동 인증 알고리즘이 아니다. Agent는 제안하고 승인된 사람이 확정한다. |
| D-012 | 2026-07-15 | Accepted | 첫 인터페이스는 `AXCalib.evaluate/aevaluate`로 작게 두고 default TOML, expert profile, typed request options 순으로 제어를 연다. |
| D-013 | 2026-07-15 | Accepted | 보호 불변조건은 config/API에 노출하지 않고 unknown key를 거부하며 effective-config hash/source를 감사기록에 연결한다. |
| D-014 | 2026-07-15 | Accepted | pre-implementation HTTP 계약은 OpenAPI 3.1.0 + JSON Schema 2020-12, config 작성 문법은 TOML 1.0 범위로 고정한다. |
| D-015 | 2026-07-15 | Accepted | 제품 브리프, quickstart, 정확한 SVG와 6컷 tutorial을 코드와 함께 drift 검증하는 1급 산출물로 유지한다. |
| D-016 | 2026-07-15 | Proposed | owner sign-off 뒤 WP-01 synthetic/offline slice만 CONDITIONAL GO이며 live/pilot/운영은 별도 Gate까지 NO-GO다. |
| D-017 | 2026-07-16 | Accepted | 사용자의 명시적 지시에 따라 제공 PPTX를 사용하는 local/offline two-gate slice를 구현한다. 이 지시는 실제 데이터·live model·운영 배포 또는 공식 rubric 승인으로 확대 해석하지 않는다. |
| D-018 | 2026-07-16 | Accepted | OOXML text가 없는 image-only PPTX는 원본 SHA-256과 일치하는 검토 sidecar가 있을 때만 그 요약·tag를 사용한다. sidecar가 없거나 hash가 다르면 시각 의미를 추론하지 않는다. |
| D-019 | 2026-07-16 | Accepted | 등록 제안서와 완료 제출물의 content hash가 같으면 수행 산출물로 자동 인정하지 않고 완료 산출물 criterion을 `not_met`로 제안한다. 최종 미수용 결정은 관리자 명시 명령으로만 확정한다. |
| D-020 | 2026-07-16 | Accepted | 심사기준은 allowlisted `policy_id@version`과 canonical SHA-256으로 dossier/report에 고정한다. 사업·사업부·소속·인증 level context는 감사용이며 승인된 mapping 없이 자동 profile 선택이나 model prompt에 사용하지 않는다. |
| D-021 | 2026-07-16 | Accepted | model gateway는 표준 `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`을 우선하고 사용자 호환 alias `OPENAPI_*`도 읽는다. 외부 model 미지정 기본값은 `gpt-5.5`, on-prem expert example은 `Qwen3.5-397B-A17B`다. |
| D-022 | 2026-07-16 | Accepted | strict model output의 존재하지 않는 locator는 실패시키고 locator 없는 met/partially_met/not_met는 `insufficient_evidence`로 하향한다. model 결과는 두 HITL Gate를 우회하지 않는다. |
| D-023 | 2026-07-16 | Accepted | 사용자 승인 하의 비식별 supplied fixture live registration smoke 1회는 transport/structured-output/HITL contract 증거로만 사용하며 model 품질 또는 공식 심의 결과로 해석하지 않는다. |

세부 근거는 `docs/adr/`의 ADR을 따른다.
