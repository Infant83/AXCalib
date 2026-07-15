---
baseline: v0.3-p1
phase: P2-P3 Offline Vertical Slice
gate: G2 Domain MVP
gate_status: offline_vertical_slice_verified
status: supplied_pptx_two_gate_mvp_runnable
current_work_package: WP-01-03 offline slice
next_work_package: WP-01-03 hardening
updated_at: 2026-07-16
---

# AXCalib Project State

## 현재 상태

사용자가 제공한 `tests/sources/oled_qc_project_outline.pptx`를 대상으로 Python Library →
allowlisted local pipeline → thin script가 연결되는 **offline two-gate vertical slice**를 구현했다.
등록심의와 완료평가 모두 dossier revision을 freeze하고 JSON/Markdown Agent 초안, recording
notification, 관리자 wait/resume 결정과 audit를 남긴다.

이 입력은 OOXML text가 없는 image-only deck이므로 원본 SHA-256에 고정된 수동 검토 sidecar를
사용한다. 등록 결과는 `needs_changes`이며, 회귀 demo에서는 관리자가 목적과 한계를 적어 조건부
승인 command를 입력한다. 같은 파일을 완료안으로 제출하면 hash 동일성과 수행증거 부재로
`not_accept`를 제안하고 local actor가 `not_accept` command를 입력한다. 현재 local actor는
인증되지 않으므로 이 결과는 실제 관리자 승인, 모델 품질 또는 인증정책 검증이 아니다.

## 구현·검증된 범위

- Pydantic dossier/evidence/report/decision/result schema
- 단일 YAML dossier, optimistic revision, atomic replace와 immutable SHA-256 snapshot
- 제한된 safe OOXML PPTX parser와 hash-bound reviewed sidecar
- registration/completion checklist 기반 deterministic evaluator와 evidence locator
- stage-separated synthetic lexical retrieval, similarity portion `0.0`
- JSON/Markdown report renderer
- 두 Gate recording notification, fail-closed test와 관리자 명시 결정
- 선택적 mentor guard, 수행 시작과 누적 progress note
- allowlisted `two-gate-pptx@v1alpha1` sync/async pipeline과 `AXCalib` facade
- `scripts/pipelines/run_two_gate_pptx.py` working script
- 제공 PPTX 통합 test/eval과 same-hash final guard

## 아직 구현되지 않았거나 완료로 승격하지 않은 범위

- 실제 rubric/합격선/AX Level 정책과 Evaluation Owner 승인
- template별 정식 field mapping, Docling/VLM/OCR adapter와 실제 parser 품질평가
- embedding/Vector DB, 승인된 historical corpus, model panel/calibration
- cross-file transaction, durable outbox, idempotent resume와 multi-process file lock
- 완전한 PipelineContext/checkpoint/cancel/retry runtime와 Typer CLI
- FastAPI/worker, GitLab/email adapter, Web/RBAC/SSO, 배포·운영

따라서 G2의 **local offline vertical slice만 검증**됐고 T1 전체, G3 Intelligence, G4 Interface,
운영 제품은 완료되지 않았다.

## 다음 실행 가능한 작업

1. 실제 사용할 과제 제안서/완료보고서 template을 받으면 field/locator mapping fixture를 추가한다.
2. dossier JSON Schema export, idempotency key, stale result와 durable local outbox를 보강한다.
3. stage별 rubric을 구조화된 registry로 옮기고 evaluator golden dataset을 늘린다.
4. template spike 뒤 Docling/slide-render/VLM 중 필요한 adapter만 선택한다.
5. CLI parity를 완성한 뒤에만 API/worker로 확장한다.

실제 데이터 반입, live model, 운영 알림, API/Web 배포, commit/push는 각각의 명시적 승인 전에는
진행하지 않는다.
