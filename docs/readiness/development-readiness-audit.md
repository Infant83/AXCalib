---
title: AXCalib Development Readiness Audit
status: offline_slice_implemented
verdict: OFFLINE_VERTICAL_SLICE_VERIFIED
baseline: v0.3-p1
updated_at: 2026-07-16
owner_signoff: user_directive_for_local_offline_slice
---

# 개발 준비 감사

## 판정

**VERIFIED — 사용자의 명시적 지시 범위에서 supplied-PPTX local/offline vertical slice가
구현·검증됐다.**

**NO-GO — 실제 데이터, live model, 운영 알림, Vector DB, API 배포, Web pilot.**

이 판정은 T1 전체, 제품 기능 완료 또는 모델 품질 검증을 뜻하지 않는다. 실제 rubric,
template, 데이터, model, outbox, CLI/API/Web과 운영 보안은 별도 Gate다.

## 감사 범위와 결과

| 영역 | 확인한 기준 | 결과 | 개발 전/중 증거 |
|---|---|---|---|
| 정체성 | 공식명, Excalibur 비유, 사람 최종권한 | Ready | product brief, concept manual, D-011 |
| 도메인 | 단일 dossier, 두 Gate, snapshot/stale | Offline slice verified | repository/pipeline integration tests |
| 인터페이스 | 최소 sync/async facade와 동일 의미 | Library/script slice verified | `AXCalib`, allowlisted pipeline, working script |
| 설정 | minimal/expert 분리, unknown/protected key 거부 | Contract ready | TOML 2종, JSON Schema, harness validation |
| API | typed JSON, idempotency, wait/resume | Contract ready | OpenAPI 3.1 artifact; auth threat model은 WP-06 |
| 검색 | stage 격리, portion 0 offline, 결손 시 fail | Synthetic lexical verified | stage-filter eval; 품질 주장은 금지 |
| 사람 검토 | 알림, checklist, mentor guard, final actor | Offline integration verified | two notification/decision audit |
| 데이터·보안 | synthetic-only, env secret, 원문 최소화 | Conditional | 실제 data classification/DPIA 미승인 |
| 시험 | read-only validation, offline test/eval | Supplied PPTX regression verified | `prep.ps1`과 static checks |
| 문서·교육 | product brief, manual, diagram, comic | Ready | `docs/manuals`와 시각 자산 |
| 운영 | outbox/retry/delivery/RBAC/observability | Not ready | WP-06 전 NO-GO |
| Frontend | API boundary와 역할은 정의 | Decision pending | 3개 후보 중 stack/design owner 선택 필요 |

## 이번 감사에서 닫은 결함

1. Agent가 인증을 결정하는 것으로 읽히던 문구를 사람 권한 중심으로 교정한다.
2. 필수 HITL/notification을 조정 가능한 boolean처럼 보이게 하던 default config를 제거한다.
3. 추상 route 목록을 typed OpenAPI request/response와 allowlist options로 고정한다.
4. 초보·운영자·전문가·통합 개발자의 사용 경로를 분리한다.
5. 비유, 매뉴얼, 웹툰, 정확한 SVG를 하나의 교육 체계로 연결한다.

## 남은 차단 항목

| ID | 항목 | 언제 필요 | 해제 책임 |
|---|---|---|---|
| B-01 | Product/Evaluation Owner가 공식 rubric·수치·운영 baseline 승인 | 실제 평가 전 | Product/Evaluation Owner |
| B-02 | 합격선·AX Level·similarity 최대 portion 정책 | 실제 평가 전 | 평가 책임자 |
| B-03 | 실제 데이터 분류·비식별·보존 승인 | pilot 전 | Data/Security Owner |
| B-04 | SSO/RBAC와 reviewer/certification role mapping | API/Web 전 | Security/Product Owner |
| B-05 | GitLab/email 운영 adapter와 outbox SLA | 운영 전 | Platform Owner |
| B-06 | Frontend 후보와 디자인 방향 선택 | WP-07 전 | Product Owner |
| B-07 | OpenAPI 3.2 및 TOML 1.1 toolchain 호환 spike | WP-06 전/선택 | Tech Lead |

## 구현된 local/offline slice

제공 PPTX 한 건을 대상으로 다음을 구현했다.

1. Pydantic dossier/evidence/report schema와 YAML round-trip
2. atomic create/load/update와 revision 증가
3. immutable snapshot + SHA-256 freeze
4. 금지 상태전이와 stale write 거부
5. `AXCalib.evaluate/aevaluate`와 allowlisted two-gate pipeline
6. registration/completion report, recording notification, explicit human decision와 audit
7. 동일 proposal/final hash의 완료 `not_accept` guard

JSON Schema export, idempotent checkpoint, durable outbox와 독립 CLI는 아직 남았다. 실제 LLM,
embedding, Qdrant, FastAPI, email/GitLab, Web UI는 이 slice에 넣지 않았다.

## Owner sign-off checklist

- [x] 사용자 지시로 local/offline supplied-PPTX 구현 범위 승인
- [x] Agent 제안과 관리자 결정을 분리한 채 실행
- [x] minimal facade와 progressive config 방향을 slice에 적용
- [x] 실제 데이터·live model·운영 배포 NO-GO 유지
- [ ] Product/Evaluation Owner의 공식 rubric·수치 승인
- [ ] OpenAPI 3.1 구현 계약 승인
- [ ] Frontend/design 선택은 별도 Gate로 유지

승인 기록은 날짜, 승인자 역할, baseline hash와 함께 `DECISIONS.md` 또는 별도 ADR에 남긴다.
