---
status: accepted
date: 2026-07-20
decision_id: D-024..D-029
---

# ADR-017: 교육 프로그램 composition과 프로젝트 인증 경계

## 맥락

AXCalib의 첫 실행 단위는 한 과제 dossier의 등록심의와 완료평가다. 교육과정에서는 한 학습자가
여러 수업, 확인, 채점, 과제와 level을 순서대로 이수해야 하므로 프로젝트 workflow 위에 과정
기획자가 관리할 수 있는 progression 계층이 필요하다. 이 계층이 프로젝트 상태기계나 사람
승인 Gate를 복제하거나 우회해서는 안 된다.

## 결정

1. `EducationProgram`은 과정 기획자가 발행하는 immutable `program_id@version` blueprint다.
   level, milestone, prerequisite, typed requirement와 allowlisted pipeline ID/version을 가진다.
2. `EducationEnrollment`는 학습자별 mutable progression aggregate다. 가입 시 program SHA-256을
   고정하고 milestone 목표를 생성한다.
3. 현재 직접 심의·평가하는 인증 대상은 제출 프로젝트다. 프로젝트 milestone은 별도
   `ProjectDossier`를 연결하고 저장된 `completion_accepted` 상태를 근거로 완료된다.
4. dossier와 enrollment의 program/version/enrollment/milestone/learner context가 모두 같아야
   연결할 수 있다. caller가 project status를 직접 주입할 수 없다.
5. manual confirmation, score threshold, project status requirement만 alpha catalog에 허용한다.
   arbitrary Python import, expression, dynamic graph execution은 금지한다.
6. 모든 필수 milestone 충족은 과정 완료 **후보**만 만든다. notification이 기록된 관리자
   completion HITL 뒤에만 enrollment를 `completed`로 전이한다.
7. 새 program version은 신규 가입에만 적용한다. 진행 중 enrollment migration과 credential
   발급은 별도 정책·ADR 전에는 구현하지 않는다.

## 결과

- 과정 기획자는 YAML에서 목표·순서·기준을 바꿀 수 있지만 code-owned 불변조건은 끌 수 없다.
- 프로젝트의 두 Gate와 과정 완료 Gate가 별도로 감사된다.
- 기존 프로젝트 dossier schema와 lifecycle을 재사용하며 과정별 진행을 한 파일에 억지로
  합치지 않는다.
- program/enrollment/dossier/audit/outbox가 여러 파일이므로 운영 전 transaction journal 또는
  reconciliation이 필요하다.
- local actor는 인증된 사용자가 아니며 API/RBAC 전에는 운영 승인으로 해석하지 않는다.

## 검증

- program graph와 allowlist validation
- 가입 시 ordered/locked milestone 생성
- idempotent enrollment command
- 다른 enrollment/learner context의 project binding 거부
- project `completion_accepted` 전 milestone 미완료
- 모든 milestone 뒤 notification + `completion_hitl_pending`
- 명시적 administrator command 뒤에만 `completed`

