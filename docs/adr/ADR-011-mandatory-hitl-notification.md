# ADR-011: 관리자 HITL 승인과 승인요청 알림을 강제한다

- 상태: Accepted
- 날짜: 2026-07-14

## Context

Agent의 통과·미통과 제안에는 hallucination, 편향, 근거누락 위험이 있다. 관리자가 검토할
대상이 생겼다는 사실도 전달되지 않으면 human-in-the-loop가 형식적으로만 존재하게 된다.

## Decision

- 등록과 완료 모두 Agent report 이후 관리자 review request를 만든다.
- `registration_approved`, `registration_rejected`, `completion_accepted`,
  `completion_not_accepted`는 관리자만 확정한다.
- HITL pending 전이에는 notification event 기록 또는 전달 성공이 필수다.
- production adapter는 GitLab Merge Request와 email을 우선 후보로 한다.
- offline test는 외부 전송 없이 recording adapter로 event를 검증한다.
- adapter 실패 시 전이를 완료하지 않고 재시도 가능한 outbox 설계를 WP-01/서비스 단계에
  추가한다.

## Consequences

감사 가능성과 사람 책임은 강해지지만 notification/outbox의 idempotency, retry, recipient
정책이 추가로 필요하다. 실제 GitLab project와 SMTP 설정은 별도 승인 전 만들지 않는다.

