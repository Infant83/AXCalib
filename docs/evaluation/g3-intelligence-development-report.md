---
document_type: development_and_code_review_report
project: AXCalib
baseline: v0.3-p1-g3-ref1
date: 2026-07-16
status: g3_reference_baseline_verified
---

# G3 Intelligence 개발·코드리뷰 리포트

## 1. 결론

AXCalib는 G2 supplied-PPTX two-gate slice 위에 다음 G3 reference capability를 연결했다.

1. version/hash-bound 심사 policy와 checklist/reference hash
2. optional Docling PPTX parser manifest
3. stage-separated synthetic lexical retrieval metric
4. OpenAI Responses/on-prem Chat Completions structured-output gateway
5. evidence locator를 강제하는 registration/completion model evaluator
6. 사람 reviewer adjustment와 관리자 HITL 경계

기본 offline 두 Gate, mock model 두 Gate, 실제 Docling supplied fixture와 사용자 승인 live
registration smoke가 실행됐다. 이 상태는 **G3 reference baseline verified**이며 실제 rubric,
embedding/Vector DB, on-prem Qwen, model/retrieval gold 품질, 운영 outbox/API/Web 완료가 아니다.

## 2. 요구사항 반영

| 요구 | 구현 | 증거 |
|---|---|---|
| 사업·조직·level별 심사기준 주입 | 명시적 `ReviewPolicyPack` selector와 `ReviewContext` | policy unit/integration tests |
| 기준 변경 감사 | policy canonical SHA-256, reference/checklist SHA-256, dossier/report freeze | workspace validation |
| 직관적 Library | `register_case(...)`, `evaluate/aevaluate(...)`; `create_project` alias | public facade tests |
| 심사자 주관 보존 | `ReviewerAdjustment`를 immutable Agent report와 분리 | stale/duplicate criterion guard |
| PPTX Docling | `DoclingPptxParser` optional extra, page/text/warning manifest | supplied PPTX contract run |
| 외부 OpenAI 기본 | `OPENAI_*`, model 미지정 시 `gpt-5.5`, Responses API | env/transport tests |
| on-prem 확장 | `OPENAPI_*` alias, custom base URL, `Qwen3.5-397B-A17B` example | Chat Completions fake-server test |
| HITL 유지 | model report 뒤 notification → `*_hitl_pending` | fake/live registration, two-gate test |
| RAG portion | stage별 lexical adapter, portion 0.0, synthetic metric | retrieval baseline |

심사 context는 report 감사에는 남지만 model prompt나 자동 profile selection에 넣지 않았다. 조직
정보에 따라 기준을 자동 변경하려면 별도 mapping version, owner 승인과 subgroup 편향평가가
먼저 필요하다.

## 3. 최종 live smoke

사용자가 승인한 비식별 `tests/sources/oled_qc_project_outline.pptx`만 외부 endpoint로 보냈다.
기본 test/eval에는 이 호출을 넣지 않았다.

| 항목 | 결과 |
|---|---|
| project | `g3-live-final-policy-20260716` |
| final state | `registration_hitl_pending` |
| human decision | 없음 |
| notification | recording event 1개 |
| report | `report-registration-model-b8584ea2f0c62555` |
| model | 환경에 지정된 `gpt-4o-mini-2024-07-18` |
| API dialect | Responses |
| latency | 7,531 ms |
| policy | `axcalib.default@1.0.0` |
| policy SHA-256 | `f3ff3e2b46835befca87ae08af96d585c0630d0ef99f0e89dc430ab7fc037a79` |
| normalized evidence SHA-256 | `7430bb3bbf68a0108384b0ba4cabbbb97a37c6648c09485acd08dfc9a6863145` |
| Docling | 2.113.0, 16 pages, 0 text pages, 0 text chars |
| criterion | 7/7 `insufficient_evidence` |
| normalization | 7/7 locator 없는 model 판정 하향 |
| Agent recommendation | `reject` 제안; 관리자 확정 아님 |

현재 shell에는 `OPENAI_MODEL`이 이미 지정돼 있어 사용자 요청의 fallback `gpt-5.5`가 아니라 그
값이 우선됐다. fallback과 on-prem model ID는 network 없는 env contract test로 확인했다.

## 4. 코드리뷰 발견사항과 조치

| 심각도 | 발견 | 조치 | 상태 |
|---|---|---|---|
| High | model이 source locator 없이 `not_met` 또는 `met`를 반환할 수 있음 | 세 판정 모두 `insufficient_evidence`로 하향하고 risk flag 추가; 없는 slide는 실패 | Closed for reference |
| High | completion structured prompt에 등록 당시 목표·KPI baseline이 빠짐 | registration report ID/snapshot hash/criterion 요약·locator를 완료 model 입력에 연결 | Closed |
| High | 등록 후 sidecar 내용을 바꾸면 같은 dossier가 다른 evidence를 읽을 수 있음 | sidecar SHA-256을 artifact에 고정하고 평가 직전 재검증 | Closed |
| High | repository `load(project_id)`는 Pydantic 밖에서 경로이탈 문자열을 받을 수 있음 | repository 경계 strict ID validator와 Windows/Unix traversal 회귀 | Closed |
| Medium | 소속·사업부 context가 prompt에 들어가면 편향 또는 차별기준을 숨길 수 있음 | context와 explicit policy selector 분리, prompt exclusion test | Closed for G3 |
| Medium | YAML policy hash만 고정하면 연결된 checklist 내용이 바뀔 수 있음 | reference SHA-256과 harness drift validation 추가 | Closed |
| Medium | provider error body가 원문을 되돌릴 수 있음 | HTTP status와 type/code/param만 노출하는 safe diagnostic | Closed |
| Open | dossier/report/audit/notification이 하나의 transaction이 아님 | durable outbox, report content hash와 recovery 필요 | WP-01 hardening |
| Open | optimistic revision check와 replace 사이 multi-process race | file lock 또는 DB CAS 필요 | WP-01 hardening |
| Open | model endpoint allowlist/retry/concurrency/usage/cost 없음 | approved composition root와 capability probe 필요 | G3 operational |
| Open | Docling이 image-only slide 의미를 추출하지 못함 | slide render/OCR/VLM gold coverage 필요 | G3 quality |
| Open | retrieval dataset이 4-query synthetic lexical set | labeled corpus, embedding/Qdrant/rerank benchmark 필요 | G3 quality |

숨은 chain-of-thought를 요청하거나 저장하지 않는다. model request/response 원문 대신 hash, model,
response ID, latency와 구조화 finding만 manifest에 남긴다.

## 5. 검증 기록

최종 commit 전 아래 명령을 실행해 결과를 이 문서와 맞춘다.

```powershell
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 eval
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pyright src tests harness evals scripts
python -m pytest tests/contract/test_docling_adapter.py -q
uv lock --check
uv build
git diff --check
```

- workspace validation: 0 errors, 0 warnings
- default offline suite: 40 passed, 1 skipped; skip은 project `.venv`에 optional Docling extra가
  없기 때문
- system Python Docling contract: 1 passed; Docling 2.113.0과 explicit zero-text manifest 확인
- eval: workflow 3/3, supplied-PPTX checks 8/8, retrieval query 4/4; Recall@5 1.0,
  nDCG@5 1.0, stage leakage 0
- Ruff: passed
- Pyright: 0 errors, 0 warnings
- lock: 131 packages resolved, current `uv.lock` 일치
- package: sdist/wheel build 성공; 격리 Python 3.12 환경에서 wheel+dependencies 설치 후
  `axcalib 0.1.0a0`, default model `gpt-5.5` import smoke 성공
- `git diff --check`: passed; Windows line-ending 안내 외 whitespace error 없음

## 6. 다음 승인과 개발 경계

G4로 가기 전 반드시 필요한 것은 Product/Evaluation Owner의 실제 policy 승인, 실제 template과
gold label, dossier/outbox hardening이다. embedding/Qdrant와 on-prem Qwen은 승인된 synthetic 또는
비식별 dataset으로 각각 benchmark한 뒤 승격한다. API/Web은 이 Library application service와
OpenAPI contract만 호출하며 판정·HITL 규칙을 재구현하지 않는다.

구현 근거는 [ADR-016](../adr/ADR-016-review-policy-and-openai-compatible-evaluator.md),
[review policy schema](../schemas/review-policy-pack.md),
[심사 프로필 매뉴얼](../manuals/04-review-profiles-and-model-endpoints.md)에 고정했다.

외부 API 계약은 OpenAI의 [GPT-5.5 model reference](https://developers.openai.com/api/docs/models/gpt-5.5),
[API quickstart](https://platform.openai.com/docs/quickstart/make-your-first-api-request), Docling의
[supported formats](https://docling-project.github.io/docling/usage/supported_formats/)와
[DocumentConverter reference](https://docling-project.github.io/docling/reference/document_converter/)를
확인했다.
