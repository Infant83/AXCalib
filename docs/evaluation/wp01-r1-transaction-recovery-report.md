# WP-01.R1.1 Local Transaction Recovery 개발·검증 리포트

- Date: 2026-07-22
- Phase / WP / Gate: P2 / WP-01.R1.1 / G2 Domain hardening
- Status: `project_dossier_audit_verified_broader_recovery_pending`
- Data: synthetic/local filesystem only
- External model/network: not used

## 1. 이번 단계에서 해결한 문제

기존 구현은 dossier를 저장하고 audit event를 append하는 두 작업 사이에서 프로세스가 종료되면
다음과 같은 불일치가 생길 수 있었다.

- dossier에는 event ID가 있지만 audit JSONL에는 해당 event가 없음
- report/outbox는 만들어졌지만 dossier가 아직 이전 revision임
- 재시도 시 같은 notification 또는 audit event가 중복될 가능성
- 다른 command가 revision을 먼저 바꾼 뒤 과거 작업이 조용히 적용될 가능성

이번 단계는 project command의 dossier/audit 경계를 복구 가능한 local transaction으로 만들고,
HITL 상태에 필요한 report/outbox를 hash-bound prerequisite로 검증했다.

## 2. 구현 내용

| 요소 | 구현 |
|---|---|
| Transaction plan | project, command, idempotency key, base/target revision, dossier/audit payload |
| Journal | transaction별 append-only JSONL, sequence와 previous-event SHA-256 hash chain |
| Apply | base dossier hash/revision 확인 후 create 또는 CAS save |
| Audit | event ID 기준 `append_once`; 같은 ID의 다른 내용은 conflict |
| HITL prerequisite | report JSON/Markdown hash와 recorded notification outbox hash 고정 |
| Reconcile | dossier/audit 누락만 idempotent 복구; stale/변조는 `blocked` |
| Library pipeline | `project.transaction.reconcile@v1alpha1`, sync/async 동일 의미 |
| Script | `scripts/pipelines/run_transaction_reconciliation.py` |

## 3. Failure-injection 결과

| 주입 지점 | 재시작 시 복구 | 반복 reconcile | audit 중복 |
|---|---|---|---|
| `after_prepare` | dossier + audit 적용 | `already_committed` | 0 |
| `after_dossier` | 누락 audit 보충 | `already_committed` | 0 |
| `after_audit` | journal commit만 보충 | `already_committed` | 0 |

추가로 다음 fail-closed 조건을 확인했다.

- outbox hash/status가 plan과 다르면 dossier revision을 올리지 않고 `blocked`
- 다른 command가 target revision을 먼저 사용하면 `target_revision_missing_event`로 차단
- journal line을 수정하면 hash mismatch로 읽기 거부
- HITL recovery가 notification adapter를 다시 호출하지 않아 알림 1건 유지

## 4. 검증 결과

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_transaction_reconciliation.py `
  tests\integration\test_transaction_recovery_pipeline.py -q `
  --basetemp output\pytest-wp01-r1-target-20260722-02
.\prep.ps1 test
.\prep.ps1 eval
.\prep.ps1 validate
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pyright
```

- Targeted recovery tests: 9 passed
- Full offline tests: 88 passed
- Evaluation groups: 9 passed
- Transaction recovery eval: 3/3 crash boundaries passed
- Ruff: passed
- Pyright: 0 errors, 0 warnings

## 5. 코드리뷰 결과

| 검토 항목 | 결과 |
|---|---|
| 원문/secret 저장 | journal에 원본 bytes, key, model reasoning 없음 |
| stale overwrite | base SHA-256/revision과 target event ID 불일치 시 차단 |
| 알림 중복 | reconcile에서 adapter 재호출 없음 |
| invalid success | committed 외 상태를 성공으로 취급하지 않음 |
| journal 변조 | sequence/previous hash/event hash 검증 |
| arbitrary path | required artifact는 workspace 상대경로만 허용 |
| interface 복제 | script와 facade가 같은 allowlisted pipeline 사용 |

## 6. 품질 주장 경계와 다음 작업

이번 결과는 local filesystem의 **project dossier/audit recovery contract**다. 다음을 완료했다고
주장하지 않는다.

- EducationEnrollment/audit/outbox cross-file recovery
- report/outbox producer 자체의 transaction 적용과 orphan quarantine
- stale lock 자동 판정·해제, journal retention/compaction
- database/distributed worker transaction, GitLab/email 운영 delivery
- 실제 데이터, 모델 또는 인증 품질

따라서 WP-01.R1은 `in_progress`로 유지한다. 다음 하위 slice는 R1.2 education/report-outbox producer와
stale-lock recovery다.
