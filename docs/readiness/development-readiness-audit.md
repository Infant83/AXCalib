---
title: AXCalib Development Readiness Audit
status: g4_identity_local_reference_quality_audit_pending
verdict: LOCAL_LIBRARY_API_WORKER_IDENTITY_REFERENCE_VERIFIED_OPERATIONAL_NO_GO
baseline: v0.3-p1-identity-reference
updated_at: 2026-07-24
owner_signoff: user_directive_for_g3_and_limited_live_fixture
---

# 개발 준비 감사

## 판정

**VERIFIED — 사용자의 명시적 지시 범위에서 supplied-PPTX local/offline vertical slice, G3
Intelligence contract, Qwen Plus provider-proxy capability/registration, 교육 program composition과 WP-01 local
hardening, Library/CLI/API/Worker Alpha와 local signed identity reference가 검증됐다.**

**NO-GO — 실제 데이터, exact Qwen registration/completion·gold 품질, on-prem 운영승격, 운영 알림, Vector DB 운영,
approved remote identity/immutable upload, API 배포, Web pilot.**

이 판정은 T1 전체, 제품 기능 완료 또는 모델 품질 검증을 뜻하지 않는다. 실제 rubric,
template, 승인된 gold label, on-prem model, 운영 notification adapter, CLI/API/Web과 보안은 별도 Gate다.

## 감사 범위와 결과

| 영역 | 확인한 기준 | 결과 | 개발 전/중 증거 |
|---|---|---|---|
| 정체성 | 공식명, Excalibur 비유, 사람 최종권한 | Ready | product brief, concept manual, D-011 |
| 도메인 | 단일 dossier, 두 Gate, snapshot/stale | Offline slice verified | repository/pipeline integration tests |
| 교육 progression | versioned program, generated goals, project roll-up, program HITL | Offline reference verified | actual-PPT lifecycle and program tests |
| 인터페이스 | 최소 sync/async facade와 동일 의미 | Library/script slice verified | `AXCalib`, allowlisted pipeline, working script |
| 설정 | minimal/expert 분리, unknown/protected key 거부 | Contract ready | TOML 2종, JSON Schema, harness validation |
| API/Worker | typed JSON, idempotency, resource auth, queued recovery | Local contract verified | OpenAPI 3.1, WP-06.I1~I3 tests/reports |
| Identity | RFC 9068 type/signature/issuer/audience/JWK/claim mapping | Local signed reference verified | ADR-028, 24 targeted tests; remote operation pending |
| 검색 | stage 격리, portion 0 offline, 결손 시 fail | Synthetic lexical verified | stage-filter eval; 품질 주장은 금지 |
| 심사정책 | 기준 주입, version/hash/status, 사람 수정 분리 | G3 reference verified | policy registry, checklist hash, adjustment tests |
| 문서 파싱 | parser provenance와 coverage | Docling contract verified | supplied deck 16쪽, text page 0, text char 0 |
| 모델 | provider 교체, identity/dialect, strict output, locator guard | Proxy registration verified; exact pending | Qwen Plus text/vision+registration, GPT-4o comparison pass, GLM vision fail, fake exact E2E |
| 사람 검토 | 알림, checklist, mentor guard, final actor | Offline integration verified | two notification/decision audit |
| 데이터·보안 | synthetic-only, env secret, 원문 최소화 | Conditional | 실제 data classification/DPIA 미승인 |
| 시험 | read-only validation, offline test/eval | Supplied PPTX regression verified | `prep.ps1`과 static checks |
| 문서·교육 | product brief, manual, diagram, comic | Ready | `docs/manuals`와 시각 자산 |
| 운영 | local outbox/recovery/API/Worker/identity는 reference; remote identity/upload/distributed infrastructure 없음 | Not ready | decision packet과 G4 NO-GO |
| Frontend | API boundary와 역할은 정의 | Decision pending | 3개 후보 중 stack/design owner 선택 필요 |

## 이번 감사에서 닫은 결함

1. Agent가 인증을 결정하는 것으로 읽히던 문구를 사람 권한 중심으로 교정한다.
2. 필수 HITL/notification을 조정 가능한 boolean처럼 보이게 하던 default config를 제거한다.
3. 추상 route 목록을 typed OpenAPI request/response와 allowlist options로 고정한다.
4. 초보·운영자·전문가·통합 개발자의 사용 경로를 분리한다.
5. 비유, 매뉴얼, 웹툰, 정확한 SVG를 하나의 교육 체계로 연결한다.
6. 변경 가능한 심사기준을 hash-bound policy pack으로 분리하고 소속정보의 암묵적 prompt 주입을
   금지한다.
7. model의 locator 없는 긍정·부정 판정을 insufficient evidence로 하향하고 존재하지 않는 locator를
   실패시킨다.
8. sidecar 파일 자체의 hash도 dossier에 고정해 평가 전 변경을 탐지한다.
9. repository API의 project ID 경로이탈을 schema 밖에서도 거부한다.
10. 다른 enrollment/learner의 project binding을 exact education context로 거부한다.
11. stale update 경쟁 구간을 service CAS와 freeze lock까지 연결한다.
12. outbox/idempotency error record에서 provider message를 제거한다.
13. `json_object`의 literal JSON/schema prompt contract를 gateway에 고정하고 wrapped upstream 4xx를
    안전한 identifier로 진단한다.
14. Qwen 전용 검증과 별도로 model-independent multimodal provider/deployment scope를 제공한다.
15. JWT algorithm/token/key confusion을 막는 optional identity verifier와 401/503 failure boundary를
    추가하고 운영 issuer/upload 결정을 Owner packet으로 분리한다.

## 남은 차단 항목

| ID | 항목 | 언제 필요 | 해제 책임 |
|---|---|---|---|
| B-01 | Product/Evaluation Owner가 공식 rubric·수치·운영 baseline 승인 | 실제 평가 전 | Product/Evaluation Owner |
| B-02 | 합격선·AX Level·similarity 최대 portion 정책 | 실제 평가 전 | 평가 책임자 |
| B-03 | 실제 데이터 분류·비식별·보존 승인 | pilot 전 | Data/Security Owner |
| B-04 | 실제 issuer/JWKS rotation/revocation, SSO/RBAC와 reviewer/certification role mapping | 운영 API/Web 전 | Identity/Security/Product Owner |
| B-05 | GitLab/email 운영 adapter와 outbox SLA | 운영 전 | Platform Owner |
| B-06 | Frontend 후보와 디자인 방향 선택 | WP-07 전 | Product Owner |
| B-07 | OpenAPI 3.2 및 TOML 1.1 toolchain 호환 spike | WP-06 전/선택 | Tech Lead |
| B-08 | on-prem Qwen capability, endpoint allowlist와 data egress 승인 | on-prem/live 운영 전 | Model/Security Owner |
| B-09 | 실제 template과 labeled retrieval/model gold set | G3 품질승격 전 | Data/Evaluation Owner |
| B-10 | program publish/retire/migration, 재수강·면제·credential 정책 | 교육 pilot 전 | Course/Product Owner |
| B-11 | education/report-outbox producer/stale-lock reconciliation | API/worker 전 | Tech/Platform Owner |
| B-12 | exact `Qwen3.5-397B-A17B` full registration/completion와 deployment fingerprint | G3 품질승격 전 | Model/Evaluation Owner |
| B-13 | immutable upload version/ACL/malware/DLP/retention | 운영 artifact 반입 전 | Platform/Security/Data Owner |
| B-14 | GOAL trace, public API/script usability와 EX-01~EX-12 self-check | 다음 local 표준화 checkpoint | Tech/Product Owner |

## 구현된 local/offline slice

제공 PPTX 한 건을 대상으로 다음을 구현했다.

1. Pydantic dossier/evidence/report schema와 YAML round-trip
2. atomic create/load/update와 revision 증가
3. immutable snapshot + SHA-256 freeze
4. 금지 상태전이와 stale write 거부
5. `AXCalib.evaluate/aevaluate`와 allowlisted two-gate pipeline
6. registration/completion report, recording notification, explicit human decision와 audit
7. 동일 proposal/final hash의 완료 `not_accept` guard

8. hash-bound two-stage review policy와 criterion별 reviewer adjustment
9. optional Docling parser manifest와 zero-text 경계
10. stage-aware synthetic retrieval metric과 OpenAI-compatible structured evaluator
11. 사용자 승인 비식별 fixture의 단일 live registration transport/HITL smoke
12. dossier/program/enrollment JSON Schema와 multi-process local CAS lock
13. local idempotency result store, durable notification outbox와 effective-config manifest
14. versioned program/enrollment, typed milestone과 actual-PPT project roll-up/program HITL 예제
15. Qwen Plus와 GPT-4o provider proxy의 supplied-fixture registration report/notification/HITL smoke
16. generic multimodal text/vision probe와 JSON-object schema compatibility contract
17. project dossier/audit append-only journal, HITL artifact prerequisite와 3-boundary crash recovery
18. local executor checkpoint/cancel/result replay, education reconcile, maintenance, JSONL batch와 CLI
19. principal-bound project/education resource API, safe read/decision replay와 generated OpenAPI
20. queued 202, durable local Worker lease/retry/restart/terminal replay
21. portable GitHub/GitLab Wiki와 GitHub live automatic publication
22. provider-neutral OIDC/JWKS local signed validation과 identity/upload decision packet

embedding/Qdrant, exact on-prem Qwen registration/completion·gold, multi-model calibration, remote
identity/immutable upload, distributed worker, email/GitLab operating adapter와 Web UI는 아직 넣지 않았다.
전체 GOAL·public API·script/example 사용성 재감사는
`library-standardization-and-example-plan.md`의 WP-00.Q1로 이어간다.

## Owner sign-off checklist

- [x] 사용자 지시로 local/offline supplied-PPTX 구현 범위 승인
- [x] Agent 제안과 관리자 결정을 분리한 채 실행
- [x] minimal facade와 progressive config 방향을 slice에 적용
- [x] 실제 데이터·운영 배포 NO-GO 유지
- [x] 사용자 지시로 비식별 fixture live registration smoke 1회 승인·실행
- [ ] Product/Evaluation Owner의 공식 rubric·수치 승인
- [ ] OpenAPI 3.1 구현 계약 승인
- [ ] Frontend/design 선택은 별도 Gate로 유지

승인 기록은 날짜, 승인자 역할, baseline hash와 함께 `DECISIONS.md` 또는 별도 ADR에 남긴다.
