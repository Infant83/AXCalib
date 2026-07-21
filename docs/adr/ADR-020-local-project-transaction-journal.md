# ADR-020 — Local Project Transaction Journal and Reconciliation

- Status: Accepted
- Date: 2026-07-22
- Scope: WP-01.R1.1 local project dossier/audit recovery

## Context

AXCalib의 project command는 dossier revision을 저장한 뒤 audit JSONL을 append한다. 등록심의와
완료평가에서는 이보다 먼저 report JSON/Markdown과 notification outbox도 생성한다. 각 파일 쓰기는
atomic하지만 프로세스가 중간에 중단되면 dossier에 audit event ID가 있고 audit line은 없거나,
HITL 상태가 참조하는 report/outbox가 달라질 수 있다.

파일별 atomic write만으로는 이 cross-file 불일치를 복구할 수 없다. 반면 현재 local reference에
database transaction이나 범용 workflow engine을 먼저 도입하면 library-first MVP의 범위를 벗어난다.

## Decision

project command의 dossier와 audit 변경을 `axcalib.project-transaction/v1alpha1` plan으로 고정하고,
transaction별 append-only JSONL hash chain을 기록한다.

1. 첫 event는 project ID, base/target revision, command, idempotency key, candidate dossier, 작은
   audit event와 required artifact hash를 가진 `prepared` plan이다.
2. 적용 과정은 `applying → committed`로 append한다. 중단은 `reconcile_required`로 남긴다.
3. reconcile은 base dossier SHA-256과 revision을 비교한 뒤 같은 candidate만 저장한다.
4. dossier에 event ID가 이미 있으면 audit event를 `append_once`로 보충한다.
5. report/outbox는 transaction 전에 존재해야 하는 hash-bound prerequisite다. outbox는
   `delivery_status=recorded`여야 HITL dossier 상태를 적용한다.
6. revision 또는 artifact hash가 다르면 자동 병합·상태 승격하지 않고 `blocked`를 반환한다.
7. reconciliation은 notification adapter를 다시 호출하지 않는다. 기록된 outbox를 검증하므로 반복
   실행해도 관리자 알림을 중복 생성하지 않는다.
8. `project.transaction.reconcile@v1alpha1` pipeline과 thin script는 같은 coordinator를 호출한다.

Journal에는 원본 PPTX/PDF/image bytes나 model reasoning을 넣지 않는다. candidate dossier는 이미
기준 파일에 존재하거나 적용될 구조와 URI/hash 참조만 보존한다.

## Consequences

- prepare, dossier, audit 직후 synthetic crash에서 재시작 복구가 가능하다.
- journal hash chain 변조, stale revision, changed report/outbox는 fail-closed한다.
- project create/update 명령의 dossier/audit gap은 local reference 범위에서 완화된다.
- journal이 dossier 구조를 일시적으로 중복 보존하므로 접근권한·retention·cleanup 정책이 필요하다.
- filesystem journal은 PostgreSQL transaction이나 distributed worker exactly-once를 주장하지 않는다.

## Remaining work

- report/outbox **생성 자체**를 prepare 이전 side effect가 아닌 journaled producer 단계로 전환
- EducationEnrollment와 education audit/outbox transaction coordinator
- stale lock, orphan temp/journal quarantine와 retention/compaction
- model invocation failure의 safe audit/journal event
- API/worker 환경의 database outbox와 concurrency/observability 검증
