---
baseline: v0.3-p1
phase: P1 Harness
gate: G1 Harness
gate_status: ready_for_review
status: harness_ready_domain_mvp_pending
current_work_package: WP-00
next_work_package: WP-01
updated_at: 2026-07-14
---

# AXCalib Project State

## 현재 상태

P1 실행 하네스와 두 Gate reference contract를 구축했다. dossier schema, 영속 저장,
실제 평가 모델, Vector DB, GitLab/메일 adapter는 아직 구현되지 않았다.
요소 모듈 → 국소 pipeline → versioned total workflow → thin interface 구현방식은 ADR-013과
architecture plan으로 확정했지만 Pipeline kernel은 아직 구현되지 않았다.

## 완료된 범위

- `prep.ps1 status|next|validate|test|eval` 실행 표면
- Python 3.12 `src/axcalib` 패키지 scaffold
- 등록심의·완료평가의 관리자 승인 강제 reference state machine
- 멘토 선택 배정과 완료 제출 승인 guard
- offline recording notification과 lexical retrieval smoke
- 등록·완료·HITL Markdown 체크리스트
- composable local pipeline과 total workflow architecture plan
- workflow blueprint, SVG 한 장 인포그래픽과 M00~M13 module delivery control board

## 차단요인과 Open Decisions

- Product Owner와 Evaluation Owner 지정
- 등록심의·완료평가 공식 rubric과 합격선 승인
- historical similarity contribution의 운영 상한 승인
- 운영 알림 수단을 GitLab Merge Request, email 또는 둘 다로 확정
- 실제 데이터, embedding model, Vector DB와 접근정책 승인
- Web frontend stack과 디자인 방향 선택

## 다음 작업

WP-01에서 `axcalib.dossier/v1alpha1`, revision, snapshot, atomic write와 위 상태기계를
typed PipelineContext/Result/Registry 최소계약과 `dossier.freeze` 국소 pipeline으로 연결하고,
thin working Python script에서 synthetic dossier를 실행한다.
