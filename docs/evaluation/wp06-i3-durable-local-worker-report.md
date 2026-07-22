# WP-06.I3 Durable Local Worker and HTTP 202 Report

- Date: 2026-07-22
- Scope: single-host filesystem queue, in-process FastAPI contract, synthetic/offline only
- Gate impact: G4 Interfaces local evidence added; operational deployment remains NO-GO

## 1. Outcome

WP-06.I3 adds a durable local job envelope and a one-job Worker over the existing Library pipeline executor.
An exact delivery grant can now choose `queued`; the API validates and checkpoints the request, persists it,
and returns HTTP 202 without invoking the domain pipeline inline. Polling exposes the pipeline result and a
separate queue state. Restart, expired-claim reclaim, bounded transient retry, pre-start cancellation, payload
hash failure, and exact terminal replay are covered by deterministic tests.

This is a local Alpha recovery contract. It is not Redis/RabbitMQ, multi-host scheduling, OIDC, an immutable
upload service, a socket-server load test, or production authorization approval.

## 2. Implemented contract

| Surface | Contract |
|---|---|
| Library | `enqueue_pipeline(...)` prepares without execution; `create_worker(...).run_once()` processes at most one job |
| Job envelope | validated object, request SHA-256, immutable context, 1 MiB bound, forbidden credential keys |
| Claim | oldest available job, exclusive lease, expired-claim reclaim |
| Retry | retryable result only, same run/context, exponential backoff, default maximum three attempts |
| Crash recovery | executor-terminal/queue-unfinalized restart returns a hash-verified replay without a second pipeline call |
| HTTP | exact queued grant → 202 + `Location` + `Retry-After`; inline remains 200 |
| Poll | authorized run view with independent `queue_status`; local path/URI fields removed |
| Script | `run_local_worker_once.py` prints safe identifiers/status and never loops implicitly |

## 3. Code-review findings and fixes

1. **Completed re-enqueue lacked replay provenance**: the queue returned `inspect()` with `replayed=false`.
   Existing exact jobs now return `replayed=true` and the API contract verifies it.
2. **Execution state alone hid queue failure/progress**: a prepared run could not distinguish queued, claimed,
   exhausted, or blocked. `queue_status` is now a separate typed field in accepted and poll responses.
3. **Generic output exposed adapter-local references**: maintenance output contained `root`, `manifest_uri`, and
   action destinations. The HTTP view recursively removes URI/path-shaped fields; domain-specific report/evidence
   endpoints still require their own allowlisted response models.
4. **Filename ordering contradicted FIFO documentation**: claim selection now snapshots available jobs, orders
   them by `queued_at`, and rechecks availability under the file lock before claim.
5. **Crash after pipeline commit could look unfinished**: the recovery test commits through the executor, drops
   queue finalization, expires the claim, and proves the next worker replays the one committed result.
6. **Concurrent exact enqueue could return a stale prepared view**: two callers can both pass the first job-file
   check. The second locked check now returns the existing executor result with replay provenance. A synchronized
   concurrency test proves one job file and one pipeline invocation; both callers may conservatively report
   `replayed=true` when they shared an already-created run checkpoint.

## 4. Verification evidence

| Check | Current result |
|---|---|
| Worker unit tests | 7 passed, including concurrent exact enqueue |
| Worker script integration | 1 passed |
| Runtime API contract | 8 passed |
| API + Worker combined contract | 27 passed |
| Library MVP/Alpha worker eval | enqueue-no-inline and execute/replay checks passed |
| Full lightweight regression | 130 passed: unit 83, integration 28, contract 19 |
| Offline evaluation harness | 10 groups passed |
| Ruff / Pyright | full lint passed / 0 errors, 0 warnings |
| `prep.ps1 validate` | 0 errors / 0 warnings |
| Clean `[api]` wheel | Python 3.12.12, FastAPI 0.139.2, OpenAPI 3.1/17 paths, Worker prepared→succeeded |
| SVG/PNG audit | XML/link validation passed; 1920×1080 and 1600×1050 renders inspected without clipping |

The first monolithic full-suite attempt reached the orchestration command's 60-second timeout and was killed
without an assertion failure. `prep test` was then changed to isolated unit/integration/contract processes, each
group passed independently, the aggregate command completed in 74.4 seconds, and the final concurrent-enqueue
case was followed by a complete 83-test unit group rerun. Default checks do not import Docling or call an
external model.

## 5. Residual risks and boundaries

- Queue payloads are retained as local plaintext JSON; workspace ACL, encryption, retention, content
  classification, and approved redaction policy are deployment responsibilities.
- The denylist prevents common credential keys but is not a complete data-loss-prevention system.
- No worker heartbeat exists. If execution exceeds its claim lease, another worker may reclaim; the executor's
  per-run lock and terminal replay preserve local result semantics, but one worker can lose finalization ownership.
- Filesystem claim/retry is not distributed consensus. Multi-host operation requires a database or broker-backed
  adapter, visibility timeout/heartbeat, dead-letter policy, metrics, and recovery drills.
- Cancellation is cooperative and pre-start/checked-boundary based; it does not kill a process or roll back an
  already committed dossier/audit mutation.
- Generic key-based path redaction is defense in depth, not a substitute for pipeline-specific transport-safe
  output review.

## 6. Next slice

G4 still needs an approved OIDC/JWKS claim mapping, authoritative education assignments, immutable upload/ACL/
malware boundary, request/rate limits, and a distributed worker adapter. SSE is optional after polling semantics
and deployment ownership are approved; the local one-job Worker does not need it to remain testable.
