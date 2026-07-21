---
document_type: development_and_code_review_report
project: AXCalib
baseline: v0.3-p1-edu-ref1
date: 2026-07-20
status: offline_reference_verified
---

# 교육 프로그램 Composition · WP-01 Hardening 개발리포트

## 1. 결론

제출 프로젝트를 현재 인증 대상으로 유지하면서, 그 위에 과정 기획자가 versioned level,
milestone, prerequisite와 조건을 구성할 수 있는 교육 progression reference를 구현했다. 사용자가
제공한 실제 제안 PPTX를 등록자료로 쓰고 별도 synthetic 완료 PPTX를 제출하여 다음 흐름을
Library 호출만으로 관통한다.

~~~text
program publish → learner enroll / generated goals
→ orientation confirmation
→ actual proposal PPTX project registration HITL
→ execution + mentor approval
→ synthetic completion PPTX completion HITL
→ stored project completion_accepted roll-up
→ score milestone
→ program completion notification + administrator HITL
→ enrollment completed
~~~

이 결과는 교육 lifecycle과 local persistence contract의 reference 검증이다. 실제 과정 정책,
공식 credential, learner identity, embedding/Qdrant, on-prem Qwen 품질 또는 운영제품 완료가 아니다.

## 2. 제품 의미

| 개념 | 구현 의미 |
|---|---|
| `EducationProgram` | 과정 기획자가 발행하는 immutable `program_id@version` blueprint |
| `EducationEnrollment` | 가입 시 program hash를 고정하고 생성한 학습자별 목표·진행기록 |
| `ProjectDossier` | 제출 프로젝트의 등록심의·수행·완료평가 근거와 두 관리자 HITL |
| project milestone | 저장된 dossier `completion_accepted`를 과정 조건으로 반영 |
| program completion | 필수 milestone 뒤 별도 알림과 관리자 승인으로 확정 |

과정 구성은 manual confirmation, score threshold, project status의 typed union과 allowlisted
pipeline ID/version으로 제한했다. arbitrary Python import, expression, dynamic graph 또는 HITL
우회 option은 지원하지 않는다.

## 3. 실제 PPT 예제

| 항목 | 값 |
|---|---|
| 등록자료 | `tests/sources/oled_qc_project_outline.pptx` |
| 등록자료 특성 | 사용자 제공, 16 slide, image-only |
| 완료자료 | `fixtures/synthetic/education_project_lifecycle/completion_report.synthetic.pptx` |
| 완료자료 특성 | 6 slide, 명시적 SYNTHETIC positive-path fixture |
| program | `ax-oled-project-foundations@0.1.0` |
| milestone | orientation → project certification → final reflection 80+ |
| 최종 project 상태 | `completion_accepted` |
| 최종 enrollment 상태 | `completed` |
| project notification | registration/completion 2건 |
| program notification | completion 1건 |

등록 Agent recommendation은 `needs_changes`, 완료 recommendation은 `accept`였다. 두 결과 모두
관리자 결정을 대신하지 않는다. 예제의 세 administrator command는
`authority_context=offline_unverified_actor`이며 공식 승인이 아니다.

실행 명령:

~~~powershell
uv run --no-sync python examples/education_project_lifecycle/run_full_lifecycle.py `
  --workspace output/education-project-lifecycle
~~~

## 4. WP-01 Hardening

- dossier/program/enrollment JSON Schema Draft 2020-12 export와 drift validation
- dossier/enrollment compare-and-swap 구간의 cross-process filesystem lock
- expected revision을 고정하는 `dossier.update`와 lock-bound `dossier.freeze`
- `scripts/pipelines/run_dossier_freeze.py` thin working script
- request hash를 확인하는 local idempotency result store
- pending/failed/recorded를 저장하고 dedupe/retry하는 durable local notification outbox
- 원문 없이 project/enrollment, stage, revision, report reference와 required role을 고정한 outbox event
- API key 값 없이 config/profile/source를 고정하는 effective-config manifest
- unknown/protected runtime TOML key와 literal credential-like `_env` 값을 manifest 기록 전에
  거부하는 strict guard
- dossier `v1alpha1 → v1alpha2` allowlisted migration과 unknown version 거부

이는 local filesystem reference다. process crash가 남긴 lock 회수, 여러 record의 단일 transaction,
reconciliation과 운영 provider delivery는 남아 있다.

## 5. 약한 품질 Contract

사용자 지시에 따라 embedding과 on-prem model 운영품질을 주장하지 않는 약한 계약만 확인했다.

| 영역 | 실행한 검증 | 주장하지 않는 것 |
|---|---|---|
| Vector path | deterministic fake 32-d embedder, in-memory cosine, stage leakage 0 | semantic quality, Qdrant, Recall/nDCG 품질 |
| Model path | external `gpt-5.5` fallback와 on-prem `Qwen3.5-397B-A17B` profile/dialect/capability config smoke | live Qwen multimodal/structured-output 품질 |
| PPT parsing | 실제 source hash와 reviewed sidecar, 기존 Docling 0-text manifest | OCR/VLM 또는 image understanding 품질 |

이번 변경에서는 외부 model endpoint를 호출하지 않았다.

## 6. 코드리뷰 발견사항

| 심각도 | 발견 | 조치 | 상태 |
|---|---|---|---|
| High | 같은 program의 다른 학습자 project를 enrollment milestone에 연결할 수 있었음 | program/version/enrollment/milestone/learner exact-context 비교와 회귀 test | Closed locally |
| High | `dossier.update`가 사전 revision 확인 뒤 경쟁 update를 새 revision에 적용할 수 있었음 | expected revision을 service CAS까지 전달하고 conflict를 stale result로 반환 | Closed locally |
| Medium | freeze의 load/check/snapshot 구간이 dossier writer와 같은 lock을 공유하지 않았음 | dossier path lock 안에서 exact revision freeze | Closed locally |
| Medium | adapter/idempotency 예외문자열이 secret 또는 원문을 포함할 수 있었음 | persisted error를 exception class 이름으로 제한 | Closed locally |
| Medium | outbox event에 revision/report reference가 없어 재심·감사 연결이 약했음 | safe revision과 report/enrollment reference를 payload와 dedupe key에 추가 | Closed locally |
| Medium | repository path와 YAML 내부 ID가 달라도 load가 성공할 수 있었음 | dossier/program/enrollment content ID와 요청 path selector 일치 검증 | Closed locally |
| Medium | 여러 process의 audit JSONL append가 같은 lock을 사용하지 않았음 | audit append에 filesystem lock과 fsync 적용 | Closed locally |
| High | enrollment YAML을 직접 편집해 알림·관리자 결정 없는 완료 상태를 주장할 수 있었음 | HITL notification, 최종 관리자 decision, milestone 완료시각과 결과 유일성을 schema invariant로 검증 | Closed locally |
| Medium | 과정 관리자 command가 local actor 문자열을 실제 권한처럼 보일 수 있음 | typed administrator role와 `offline_unverified_actor` 기록; API/RBAC 전 운영 금지 | Reference mitigation |
| High | enrollment/dossier/outbox/audit가 서로 다른 파일이라 일부 commit 뒤 crash 가능 | atomic/CAS/idempotency는 존재, transaction journal/reconciliation 필요 | Open hardening |
| Medium | crash가 filesystem `.lock`을 남기면 수동 복구 전 timeout 가능 | timeout/fail-closed는 존재, owner/age 기반 stale-lock recovery 필요 | Open hardening |
| Medium | program version rollout/retire/migration 정책 부재 | exact hash pin과 자동 migration 금지 | Open policy |

## 7. 검증 결과

최종 회귀에서 다음 명령을 실행했다.

~~~powershell
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 eval
uv run --no-sync ruff check src scripts examples harness evals tests
uv run --no-sync pyright src scripts examples harness evals tests
~~~

결과:

- `validate`: 0 errors, 0 warnings
- `test`: 58 passed, 1 optional Docling contract skipped
- `eval`: workflow 3/3, supplied-PPTX, education lifecycle, lexical, fake dense, model config smoke 성공
- Ruff: all checks passed
- Pyright: 0 errors, 0 warnings, 0 informations
- visual audit: 두 SVG를 Edge headless로 1600×1050/1920×1080 렌더해 clipping과 label을 확인
- completion PPTX: local inspector에서 6 slides, 13.3×7.5 inch와 6개 title 확인

개발환경 lockfile은 `uv lock`으로 갱신했다. 최초 `uv sync --locked --dev`는 기존 `.venv`
dist-info access 문제로 실패했으나 최종 재시도는 성공해 `python-pptx 1.0.2`를 설치했다. uv는
기존 editable `axcalib` dist-info에 `RECORD`가 없었다는 정리 warning을 냈지만 현재 workspace
package를 다시 설치했고, 이후 전체 검증은 성공했다.

## 8. 다음 Gate

1. Course/Evaluation Owner의 program/rubric/threshold 승인
2. program publish/retire, migration, 재수강·면제·기한·credential 정책
3. actual completion template와 slide-render/VLM gold coverage
4. approved corpus의 embedding/Qdrant/rerank benchmark
5. on-prem Qwen text/image/structured-output live capability probe
6. cross-file reconciliation과 full checkpoint/cancel
7. project/education Typer CLI parity 후 API/Web 설계
