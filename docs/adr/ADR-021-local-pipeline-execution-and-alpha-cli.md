# ADR-021: Local Pipeline Execution, Recovery Maintenance, and Alpha CLI

- Status: Accepted
- Date: 2026-07-22
- Scope: WP-01.R1.2 Library MVP / Alpha

## Context

AXCalib의 국소 pipeline은 Library, CLI, 향후 API/worker에서 같은 입력·결과·실패 의미를 가져야
한다. 기존 registry와 pipeline은 호출 가능했지만 run 단위 checkpoint, 동시 replay 차단, cancel,
부분실패 batch, education transaction recovery와 stale local artifact 처리 계약이 한곳에 고정되지
않았다. Windows에서 POSIX 방식의 `os.kill(pid, 0)`을 PID 존재 확인에 사용하면 대상 프로세스를
종료할 수 있다는 실제 중단도 확인했다. Docling contract는 이미지 중심 PPTX에서 text를 만들지
못하면서도 저메모리 환경의 기본 회귀 비용을 크게 만들 수 있다.

## Decision

1. `PipelineContext`는 run, actor, idempotency, expected revision, deadline과 제한된 metadata를 가진
   immutable transport-neutral 계약으로 사용한다. 시간은 timezone-aware여야 한다.
2. `LocalPipelineExecutor`는 request SHA-256과 context identity를 secret-free checkpoint에 기록하고,
   같은 run ID는 filesystem lease로 직렬화한다. terminal 결과는 재실행하지 않고 replay하며
   retryable failure만 같은 run에서 다시 시도할 수 있다.
3. persisted result는 deterministic local path와 SHA-256을 재생 전에 검증한다. hash/path가 바뀌면
   성공 결과를 반환하지 않는다.
4. 취소는 process kill이 아니라 marker를 쓰는 cooperative request다. 이미 commit된 domain side
   effect를 되돌린다는 의미가 아니다.
5. batch는 strict one-item-per-line JSONL, code-owned pipeline ID/version, manifest hash, item별
   idempotency/checkpoint와 bounded concurrency를 사용한다. 10 MiB/10,000 item 한도를 둔다.
6. education과 project reconciliation, workspace maintenance를 별도 allowlisted pipeline으로 둔다.
   maintenance 기본은 report-only이며 apply도 stale lock/orphan은 quarantine, committed journal은
   archive하고 blocked journal은 기본적으로 사람이 확인하게 남긴다.
7. Windows PID 확인은 `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`와
   `GetExitCodeProcess`를 사용한다. `os.kill(pid, 0)`은 POSIX에서만 사용한다.
8. Typer/Rich CLI는 optional `cli` extra인 얇은 delivery adapter다. pipeline list/run/status/cancel,
   JSONL batch와 maintenance만 Alpha 범위로 제공하며 domain 결정을 계산하지 않는다.
9. Docling은 lazy optional adapter와 별도 `prep.ps1 docling` contract로 유지한다. 기본 test와 실제
   PPTX quickstart는 제한형 OOXML, embedded-image renderer와 hash-bound reviewed sidecar를 사용한다.

## Consequences

- Library와 CLI가 같은 registry와 Pydantic request/result를 사용하며, 부분 실패와 재실행을 숨기지
  않는다.
- low-memory 기본 회귀가 Docling import로 불안정해지지 않는다. Docling 검증 자체는 삭제하지 않고
  별도 evidence로 유지한다.
- local filesystem lease와 quarantine은 단일 host Alpha 계약이다. distributed worker lease,
  database transaction, RBAC와 운영 notification은 G4 이후 별도 검증이 필요하다.
- cancellation은 cooperative이므로 pipeline이 context를 확인하지 않는 동안 즉시 중단되지 않으며,
  이미 발생한 domain mutation의 보상 transaction은 별도 설계가 필요하다.
