---
document_type: development_and_code_review_report
project: AXCalib
work_package: WP-01.R1.2
gate: G2 Domain hardening to G4 Interfaces entry
status: verified_local_library_alpha
date: 2026-07-22
---

# WP-01.R1.2 Library MVP / Alpha 개발·코드리뷰

## 1. 결론

AXCalib는 **single-host, offline/synthetic 범위의 최소 Library MVP/Alpha**로 사용할 수 있다.
실제 제공 PPTX를 dossier에 등록하고 등록심의 초안과 관리자 대기 상태까지 만들 수 있으며,
project/education 상태변경 복구, local pipeline checkpoint/replay/cancel, JSONL batch, non-destructive
maintenance와 얇은 CLI를 같은 Library registry에서 실행한다.

이 판정은 운영 인증제품, exact on-prem Qwen 품질, 공식 rubric, Vector DB, API/RBAC/Web 또는
distributed worker가 완료됐다는 뜻이 아니다. Agent는 여전히 초안만 만들고 관리자가 최종 결정한다.

## 2. 구현 범위

| 영역 | 구현 결과 | 핵심 경계 |
|---|---|---|
| Pipeline kernel | immutable `PipelineContext`, typed descriptor/validation, sync/async | arbitrary import/graph 없음 |
| Local executor | request/context checkpoint, per-run lease, result hash, replay, cancel | single-host filesystem |
| Batch | strict JSONL, manifest hash, item checkpoint, partial status, bounded concurrency | 10 MiB/10,000 item |
| Education recovery | enrollment/audit hash-chain journal, reconcile, outbox hash prerequisite | notification 재전송 없음 |
| Maintenance | report-only 기본, stale lock/orphan quarantine, committed journal archive | blocked journal 자동 삭제 없음 |
| CLI | pipeline list/run, run status/cancel, JSONL batch, maintenance | domain 판단 복제 없음 |
| Packaging | `0.1.0a0` wheel, optional `cli` extra, console entrypoint | API/Web 미포함 |
| PPTX quickstart | actual PPTX 등록→제출→등록심의 초안→HITL pending | sidecar hash 필요, 사람 승인 없음 |

공개 Alpha 예제:

```python
from axcalib import AXCalib

ax = AXCalib("output/review")
case = ax.register_case(
    "tests/sources/oled_qc_project_outline.pptx",
    title="OLED QC 등록심의",
    sidecar_path="tests/sources/oled_qc_project_outline.axcalib.json",
)
ax.submit_registration(case.project_id)
draft = ax.evaluate(case.project_id, "registration")
assert draft.status.value == "waiting_human"
```

## 3. 중단 원인과 재발 방지

### 직접 원인

`LocalWorkspaceMaintenance._pid_alive()`가 Windows에서 `os.kill(pid, 0)`을 PID 존재 확인으로
사용했다. POSIX와 달리 Windows Python의 `os.kill`은 대상 process를 종료할 수 있으며, 테스트가
자기 PID를 확인하다 pytest process 자체를 끝냈다. 이 때문에 traceback 없이 도구 셀이 사라졌다.

### 수정

- Windows: read-only `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` → `GetExitCodeProcess` →
  `CloseHandle`
- POSIX: 기존 `os.kill(pid, 0)` 유지
- active owner, stale owner, quarantine/archiving 회귀 test 추가
- maintenance는 삭제가 아니라 같은 workspace 내부 quarantine/archive만 수행

### 메모리와 Docling

당시 가용 물리 메모리는 약 408~833 MiB로 낮아 중단 위험을 키웠지만 위 pytest 종료의 직접 원인은
아니었다. `DoclingPptxParser`는 `parse()` 시점에만 lazy import되며 문제 test에는 적재되지 않았다.
재발 방지를 위해 기본 `prep test`는 Docling contract를 제외하고 `prep.ps1 docling`으로 별도 실행한다.
기본 actual-PPTX Alpha 경로는 OOXML 안전검사, restricted embedded-image provenance와 hash-bound
reviewed sidecar를 사용한다. Docling 지원을 제거한 것은 아니다.

## 4. 코드리뷰 결과

| 발견사항 | 위험 | 조치 | 상태 |
|---|---|---|---|
| Windows `os.kill(pid, 0)` | 테스트/운영 process 종료 | non-mutating Win32 query | 해결 |
| terminal failure 재실행 | 동일 실패 side effect 중복 | terminal/cancelled replay, retryable만 재시도 | 해결 |
| 같은 run ID 동시 실행 | idempotency 깨짐 | per-run filesystem lease와 동시 replay test | 해결 |
| 결과 파일 변조 미검출 | 잘못된 성공 replay | deterministic path와 SHA-256 확인 | 해결 |
| batch 항목 예외가 전체 중단 | 부분실패 은폐 | item별 failure envelope/progress | 해결 |
| batch ID 재사용 | 다른 manifest 혼합 | manifest SHA-256 conflict guard | 해결 |
| 무제한 JSONL | 메모리 고갈 | 10 MiB/10,000 item 상한 | 해결 |
| naive deadline | timezone 비교 오류 | timezone-aware validator | 해결 |
| cancellation marker 덮어쓰기 | 최초 요청자 감사 손실 | 첫 marker idempotent 보존 | 해결 |
| education file/audit 부분 commit | 진행·감사 불일치 | append-only journal/reconcile | local 해결 |
| report/outbox producer가 journal 밖 | producer 직후 crash 경계 | immutable hash prerequisite와 outbox dedupe; producer transaction 후속 | Open |
| filesystem lease의 분산 한계 | multi-worker 중복 | 현재 single-host 경계 명시; DB/distributed lease 후속 | Open |
| cancel 후 이미 commit된 mutation | rollback 오해 | cooperative 의미 명시; compensation 후속 | Open |

## 5. 검증 증거

| 검증 | 결과 |
|---|---|
| targeted pipeline execution | 11 passed |
| targeted education reconciliation | 2 passed |
| targeted maintenance | 1 passed |
| Alpha CLI contract | 2 passed |
| full lightweight offline test | 103 passed |
| evaluation harness | 10 groups passed; Alpha eval 8/8 checks |
| Ruff | passed |
| Pyright low-memory (`NODE_OPTIONS=512 MiB`, `--threads 1`) | 0 errors, 0 warnings |
| workspace validation | 0 errors, 0 warnings |
| wheel build | `axcalib-0.1.0a0-py3-none-any.whl` success |
| clean install | wheel `[cli]` extra, 15 packages installed |
| installed CLI | 8 allowlisted pipeline descriptors 출력 성공 |
| installed actual-PPTX quickstart | revision 3, `registration_hitl_pending`, `waiting_human` |
| Docling current-turn rerun | 미실행; 저메모리 격리. 기존 증거 16 pages, 0 text 유지 |

Alpha eval은 다음만 주장한다.

- pipeline checkpoint와 terminal replay
- manifest-bound batch와 completed item replay
- education crash/reconcile와 audit exactly-once
- stale lock quarantine, 비파괴 maintenance

모델·검색·공식 평가 정확도는 이 eval의 품질 주장이 아니다.

## 6. 다음 Gate

Library MVP/Alpha checkpoint 후 G4의 가장 작은 slice는 다음이다.

1. 현재 `AXCalib.registry`와 `LocalPipelineExecutor`를 직접 호출하는 minimal FastAPI adapter
2. committed OpenAPI 3.1 artifact와 실제 handler/request/result parity
3. bearer auth dependency와 role boundary의 contract-only 구현
4. 네트워크 배포 없이 in-process contract/E2E

운영 endpoint, 계정 생성, 실제 데이터, external notification과 배포는 별도 승인 전 진행하지 않는다.
