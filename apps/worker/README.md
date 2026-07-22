# Worker runtime

WP-06.I3에는 single-host filesystem queue와 한 번에 한 job만 처리하는 local Worker Alpha가 있다.
외부 broker나 실제 알림은 사용하지 않는다. Worker는 API와 같은 pipeline registry/executor를 사용해
checkpoint에서 재개하며 task 함수에 domain 상태전이와 평가 규칙을 복제하지 않는다.

~~~powershell
uv run --no-sync python scripts/pipelines/run_local_worker_once.py `
  --workspace output/api-local `
  --worker-id worker:local-once
~~~

명령은 처리할 job이 없으면 `{"processed": false}`로 종료하고, 있으면 run/pipeline/status/attempt 같은
안전한 식별자만 출력한다. 자동 daemon loop는 없다. 운영 supervisor가 호출 주기, 종료, 관측성을
소유해야 한다.

현재 보장 범위:

- typed validated payload와 SHA-256, 1 MiB 한도, 알려진 credential key 거부
- oldest-available claim, lease expiry 뒤 reclaim
- retryable failure만 최대 시도 횟수 안에서 backoff/retry
- terminal/cancelled result replay와 process-restart recovery
- API queued grant의 202/Location/Retry-After 및 authorized poll/cancel

현재 보장하지 않는 범위:

- multi-host consensus, broker/database queue, heartbeat, dead-letter queue와 autoscaling
- OIDC/JWKS, immutable upload, workspace encryption/retention과 production deployment
- running process 강제 종료 또는 이미 commit된 domain mutation rollback
