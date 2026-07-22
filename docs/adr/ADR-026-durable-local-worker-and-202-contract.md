# ADR-026: Durable Local Worker and HTTP 202 Contract

- Status: Accepted
- Date: 2026-07-22
- Scope: WP-06.I3 single-host queue, worker, retry, replay, and polling contract

## Context

`LocalPipelineExecutor` already preserves request identity, per-run lease, result hash, cancellation, attempts,
and terminal replay. The FastAPI adapter, however, ran every granted pipeline inside the request. A separate
process could not resume a prepared run because checkpoints intentionally do not persist the request payload.
Long parse or evaluation work therefore needed a durable command envelope without duplicating domain logic in
an API task or worker script.

## Decision

1. `ApiPipelineGrant.execution_mode` is deployment-owned and exact per pipeline version. `inline` remains the
   compatibility default; only an explicitly `queued` grant returns HTTP 202.
2. `LocalPipelineJobQueue` persists the registry-validated object payload, its canonical SHA-256, immutable
   `PipelineContext`, attempt bound, timestamps, and claim lease in a typed envelope. The envelope is limited to
   1 MiB and recursively rejects known credential-bearing keys.
3. Enqueue first creates or reuses the executor's `prepared` checkpoint and then atomically writes the job.
   Re-enqueue of the exact run returns the existing result with `replayed=true`; different pipeline, payload,
   context, or attempt policy conflicts.
4. A worker claims the oldest available job with a renewable-by-reclaim lease and executes the same
   `PipelineRegistry` through `LocalPipelineExecutor`. The supplied worker facade and script process at most one
   job per explicit call and contain no domain transition logic or hidden daemon loop.
5. Only executor results classified `retryable_failure` are requeued. Retry uses the same run and context, an
   exponential delay capped at 300 seconds, and a bounded attempt count. Terminal, stale, blocked, cancelled,
   waiting-human, and successful results are not automatically rerun.
6. A process that dies after the executor commits but before queue finalization is recovered by lease expiry.
   The next worker receives the executor's hash-verified terminal replay rather than invoking the pipeline again.
7. HTTP 202 responses include stable `Location` and `Retry-After` headers. Existing owner/admin/scope checks
   protect poll and cancellation. `PipelineRunView` exposes execution `status` and a separate `queue_status`,
   while structurally removing local path and URI fields from generic output.
8. Queue records and filesystem leases are a single-workspace, single-host Alpha adapter. No claim is made for
   multi-host consensus, broker delivery, heartbeat extension, database transactions, OIDC, proxy limits, or
   production scheduling.

## Consequences

- API requests can hand off approved pipelines without running domain work inline, while direct Library calls
  and existing inline grants retain their behavior.
- Queue state and domain execution state remain distinct, so clients can tell `queued` or `claimed` from a
  pipeline's `prepared`, `running`, or terminal result.
- Exact replay and the executor lease contain duplicate execution on local restart paths. Pipelines must still
  keep their own transaction/idempotency guards for external side effects.
- Payload bytes are durably retained in the workspace. Deployment ACL, retention, encryption, malware/content
  policy, and a distributed queue adapter are required before operational use.
- A lease can expire during a long task because this slice has no heartbeat. Executor serialization still
  prevents concurrent local execution, but the first worker may lose its queue claim and report a claim error;
  a later worker finalizes the replayed result.
