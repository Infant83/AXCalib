# ADR-024: Principal-bound Education Resources and Assignment Scopes

- Status: Accepted
- Date: 2026-07-22
- Scope: WP-06.I2b Education principal binding contract

## Context

`education-program-runtime@v1alpha1`은 Python Library에서 학습자 가입, milestone 시작, 강사·멘토
확인, 점수, project 연결·동기화와 과정 완료 결정을 실행한다. 기존 typed command에는 local trusted
caller가 넣는 `learner_ref`, `actor_id`, `actor_role`이 있으므로 이를 generic HTTP pipeline으로
노출하면 bearer principal과 다른 사람을 주장하거나 다른 enrollment를 갱신할 수 있다. enrollment
schema에는 운영 계정·조직·배정 정보를 넣지 않았고 승인된 OIDC claim mapping도 아직 없다.

## Decision

1. `education-program-runtime@v1alpha1`은 generic pipeline grant로 공개할 수 없다. 교육 HTTP 명령은
   actor field가 없는 전용 program/enrollment/milestone resource endpoint만 사용한다.
2. 학습자 가입은 `learner` role, `education:enroll:self` scope, verified organization과 exact
   `program_id@version` SHA-256을 요구한다. `learner_ref`와 audit actor는 principal subject에서 만들고
   organization은 `learner_enrolled` audit에 고정한다.
3. 진행 명령은 다음 배정 scope를 사용한다.
   - learner: enrollment의 `learner_ref`와 subject가 같고 `education:progress:self`
   - mentor: `education:enrollment:{enrollment_id}:mentor`
   - instructor: `education:program:{program_id}@{version}:instructor`
   - administrator: `education:admin:any` 또는 `education:enrollment:{id}:admin`
4. 모든 명령은 audit에 principal subject/role과 `verified_api_principal` authority context를 남긴다.
   request는 actor, role, learner 또는 organization을 지정하지 않는다.
5. mutation request는 `Idempotency-Key`와 `expected_revision`을 필수로 한다. 새 요청의 stale revision은
   domain service와 repository CAS에서 거부하고, 같은 key·같은 request 재시도는 저장된 성공 결과를
   재생한다.
6. project bind와 sync는 program/version/enrollment/milestone/learner context를 매번 다시 확인한다.
   API에서 조직을 함께 전달해 dossier의 `proposer_org_id`도 일치해야 하며 project 상태는 저장된
   dossier에서만 도출한다.
7. program publish/retire, 실제 mentor/instructor assignment 저장소, OIDC/JWKS claim mapping과 계정
   관리는 이번 Alpha 범위가 아니다. program은 Library/bootstrap에서 미리 발행된 immutable artifact를
   조회하고 가입할 수만 있다.

## Consequences

- project API role이나 generic operator grant가 교육 권한으로 자동 승격되지 않는다.
- 기존 library-only enrollment는 organization-bound creation audit가 없으므로 HTTP resource로
  조회·변경되지 않고 integrity 409로 닫힌다. 운영 migration은 별도 정책이 필요하다.
- mentor/instructor 배정은 현재 deployment가 검증해 넣는 resource scope가 기준이다. 실제 IdP claim과
  조직 인사·교육 배정 원장의 일치 여부는 아직 검증되지 않았으므로 운영 배포는 NO-GO다.
- program hash, enrollment revision, organization과 project context 중 하나라도 다르면 mutation 전에
  실패한다. 사람 완료결정과 notification/domain HITL 불변조건은 계속 Library가 최종 검사한다.
