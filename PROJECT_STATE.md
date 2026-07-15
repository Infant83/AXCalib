---
baseline: v0.3-p1
phase: P2-P5 G3 Intelligence Reference
gate: G3 Intelligence
gate_status: reference_baseline_verified
status: policy_docling_retrieval_structured_model_reference_runnable
current_work_package: WP-02-05 reference baseline
next_work_package: WP-01 hardening and G3 quality benchmark
updated_at: 2026-07-16
---

# AXCalib Project State

## 현재 상태

사용자가 제공한 `tests/sources/oled_qc_project_outline.pptx`를 대상으로 Python Library →
allowlisted local pipeline → thin script가 연결되는 두 Gate vertical slice에 G3 Intelligence
reference capability를 추가했다.

- `ReviewPolicyPack`이 등록·완료 기준, checklist/reference, recommendation을 묶고 version과
  canonical SHA-256으로 dossier/report에 고정한다.
- `ReviewContext`는 사업·사업부·제안자 소속·인증 level을 감사용으로 보존하지만 자동 profile
  선택이나 model prompt에는 사용하지 않는다.
- optional Docling adapter가 parser version/status/source hash/page/text coverage를 report에 남긴다.
- stage-separated lexical retrieval은 작은 synthetic dataset에서 Recall@5, nDCG@5와 leakage를
  회귀한다.
- strict structured evaluator는 OpenAI Responses와 on-prem-compatible Chat Completions를 같은
  interface 뒤에 둔다. locator 없는 판정은 insufficient evidence로 하향한다.
- 관리자 notification과 HITL pending은 model 사용 여부와 무관하게 필수다. 사람 adjustment는
  Agent report와 분리해 저장한다.

제공 deck은 16쪽 image-only 자료다. 설치된 Docling 2.113.0으로 실제 변환했지만 text page와
추출문자는 모두 0이었다. 따라서 hash-bound reviewed sidecar 또는 향후 slide-render/VLM 없이는
시각 내용을 판단하지 않는다.

사용자가 승인한 비식별 fixture live registration smoke는 성공했고 관리자 결정을 하지 않은 채
`registration_hitl_pending`에서 멈췄다. 당시 환경의 `OPENAI_MODEL`이 지정한 모델을 사용했으며,
7개 criterion 모두 locator 부족 때문에 `insufficient_evidence`로 정규화됐다. 이 결과는 transport와
HITL 경계 검증이지 모델 품질이나 공식 심의 결과가 아니다.

## 구현·검증된 범위

- Pydantic dossier/evidence/policy/report/decision/result schema
- 단일 YAML dossier, optimistic revision, atomic replace와 immutable SHA-256 snapshot
- project ID path traversal 거부와 hash-bound PPTX reviewed sidecar
- registration/completion policy registry, exact selector/hash/status guard
- criterion별 reviewer adjustment와 stale base-assessment 검증
- safe OOXML parser와 optional local Docling PPTX manifest
- deterministic evaluator와 strict structured model evaluator
- OpenAI-compatible standard `OPENAI_*`와 호환 `OPENAPI_*` 환경계약
- 외부 default `gpt-5.5`, on-prem example `Qwen3.5-397B-A17B`
- stage-separated synthetic lexical retrieval baseline, similarity portion `0.0`
- JSON/Markdown report에 policy/evidence/parser/model manifest 연결
- 두 Gate recording notification, fail-closed test와 관리자 wait/resume
- 선택적 mentor guard, 수행 시작과 누적 progress note
- allowlisted `two-gate-pptx@v1alpha1` sync/async pipeline과 `AXCalib` facade

## 아직 구현되지 않았거나 완료로 승격하지 않은 범위

- Product/Evaluation Owner가 승인한 실제 rubric/합격선/AX Level과 context→profile mapping
- 실제 template field coverage, slide rendering, OCR/VLM과 gold evidence label
- embedding/Vector DB/Qdrant, 승인 historical corpus, rerank와 실제 retrieval 품질
- on-prem Qwen endpoint capability probe, multi-model panel/calibration와 비용·usage 추적
- endpoint allowlist, retry/concurrency, secret manager와 data egress policy
- cross-file transaction, report integrity, durable outbox, idempotent resume와 multi-process lock
- 완전한 PipelineContext/checkpoint/cancel/retry runtime와 Typer CLI
- FastAPI/worker, GitLab/email adapter, Web/RBAC/SSO, 배포·운영

따라서 **G3 reference baseline은 검증**됐지만 T1 전체, G3 운영 품질, G4 Interface 또는 운영
제품은 완료되지 않았다.

## 다음 실행 가능한 작업

1. dossier/report JSON Schema, CAS/file lock, idempotency와 durable local outbox를 보강한다.
2. 실제 proposal/completion template과 평가 owner가 승인한 policy/gold label을 고정한다.
3. slide-render/VLM parser coverage와 Qdrant/embedding retrieval benchmark를 분리해 실행한다.
4. on-prem Qwen endpoint의 text/image/structured-output capability contract를 확인한다.
5. CLI parity를 완성한 뒤에만 API/worker로 확장한다.

실제 데이터 반입, 추가 live model, 운영 알림, API/Web 배포는 각각 명시적 승인 전에는 진행하지
않는다.
