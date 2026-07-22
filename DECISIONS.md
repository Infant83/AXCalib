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
| D-024 | 2026-07-20 | Accepted | 교육과정은 과제 dossier를 대체하지 않는 상위 aggregate다. `EducationProgram`은 기획자가 고정한 blueprint, `EducationEnrollment`는 학습자별 진행기록으로 분리한다. |
| D-025 | 2026-07-20 | Accepted | 현재 교육 인증의 직접 평가 대상은 제출 프로젝트다. 프로젝트 `completion_accepted`는 과정 milestone 근거가 되지만 과정 전체 완료를 자동 확정하지 않는다. |
| D-026 | 2026-07-20 | Accepted | 과정 유연성은 versioned level/milestone/prerequisite와 allowlisted manual/score/project requirement로 제공하며 arbitrary Python import 또는 expression은 실행하지 않는다. |
| D-027 | 2026-07-20 | Accepted | 가입은 exact `program_id@version`과 SHA-256을 고정하고 목표를 생성한다. 새 program version은 신규 가입에 적용하며 기존 가입의 자동 migration은 하지 않는다. |
| D-028 | 2026-07-20 | Accepted | 모든 필수 교육 milestone 충족 후에도 notification이 기록된 관리자 completion HITL을 거쳐야 `completed`가 된다. 이는 credential 발급 또는 법적 인증을 뜻하지 않는다. |
| D-029 | 2026-07-20 | Accepted | 교육 project milestone에는 program/version/enrollment/milestone/learner context가 정확히 일치하는 dossier만 연결하며 조건은 저장된 dossier 상태에서 도출한다. |
| D-030 | 2026-07-21 | Accepted | `PROJECT_STATE.md`를 P/WP/G dependency Gantt, Active Slice, 일정·Exit Evidence·검증·특이사항과 append-only 작업 이력을 관리하는 단일 Project Execution Ledger로 사용한다. 단계 종료는 이 원장 갱신을 포함하며 승인 전 미래 일정은 dependency-only로 유지한다. |
| D-031 | 2026-07-21 | Accepted | Qwen provider alias capability와 exact checkpoint deployment 검증을 분리한다. 제품/on-prem은 canonical `OPENAI_*` OpenAI-compatible 계약만 사용하고 SkillBoss는 개인환경 proxy에 한정한다. response model 미보고나 alias는 exact identity가 아니며 structured-output dialect/model을 조용히 fallback하지 않고 숨은 reasoning을 보존하지 않는다. |
| D-032 | 2026-07-22 | Accepted | `json_object` dialect는 gateway가 literal JSON과 canonical schema contract를 prompt에 포함하고 Pydantic으로 재검증한다. wrapped upstream 오류는 allowlisted identifier만 노출한다. 공통 multimodal probe의 기본 `provider_proxy` scope는 model ID가 일치해도 deployment-ready가 될 수 없다. |
| D-033 | 2026-07-22 | Accepted | Local project command는 hash-chained append-only transaction journal로 dossier/audit를 prepare/apply/commit/reconcile한다. HITL report와 recorded outbox는 hash-bound prerequisite이며 reconcile은 notification을 재전송하지 않는다. enrollment, report/outbox producer와 stale-lock recovery는 후속 범위다. |
| D-034 | 2026-07-22 | Accepted | Local pipeline은 immutable context, request hash, per-run filesystem lease, result hash, cooperative cancel과 terminal/retryable replay 의미를 checkpoint한다. JSONL batch는 manifest hash와 item별 상태를 보존하고, education/project reconcile 및 report-only 기본 maintenance는 allowlisted pipeline으로 노출한다. Windows PID 확인은 비파괴 Win32 query를 사용하며 optional Docling contract는 저메모리 기본 test와 분리한다. |
| D-035 | 2026-07-22 | Accepted | HTTP adapter는 Library registry와 별도 exact delivery grant를 요구하고 기본 verifier/grant를 fail closed한다. generic payload의 actor/admin decision을 거부하며 owner/scope로 run을 보호한다. 전체 제품 target OpenAPI와 실제 runtime-generated OpenAPI는 별도 artifact로 관리한다. |
| D-036 | 2026-07-22 | Accepted | Project HTTP command는 request actor/local path를 받지 않고 verified principal과 opaque staged artifact에 bind한다. 등록·완료 결정은 administrator role, explicit scope, organization과 expected revision을 모두 통과해야 하며 project create replay는 content/context/creation audit exact match만 허용한다. |
| D-037 | 2026-07-22 | Accepted | Education HTTP command는 generic pipeline grant가 아니라 actor 없는 resource endpoint로만 제공한다. learner는 subject/self scope, mentor는 enrollment scope, instructor는 immutable program selector scope, administrator는 explicit admin scope와 organization에 bind하며 program hash·revision·project context를 domain에서 재검증한다. 실제 assignment/IdP claim mapping은 운영 Gate로 남긴다. |
| D-038 | 2026-07-22 | Accepted | Project GET은 owner creation audit 또는 administrator read scope와 organization을 통과한 URI/free-text redacted safe view만 반환한다. 두 HITL decision은 raw key를 저장하지 않는 local idempotency record에 principal/resource/stage/revision/payload를 고정하고 exact 성공만 replay하며 cached result도 persisted decision·audit·verified authority와 재검증한다. |
| D-039 | 2026-07-22 | Accepted | HTTP pipeline grant는 기본 inline과 명시적 queued 실행을 분리한다. queued request는 validated 1 MiB 이하 secret-key-free envelope와 context hash를 local queue에 고정하고 202를 반환하며, one-job Worker는 같은 executor를 통해 retryable만 bounded retry한다. poll은 execution status와 queue status를 분리하고 local URI를 제거한다. 이 filesystem lease는 single-host Alpha이며 distributed broker/OIDC/heartbeat를 뜻하지 않는다. |

세부 근거는 `docs/adr/`의 ADR을 따른다.
