# AXCalib Architecture 문서 지도

이 폴더는 AXCalib 구현구조와 작업계획의 시각적 기준점이다. 제품 요구사항은 루트
`WORK_SPEC.md`, 단계별 수용기준은 `GOAL.md`, 상세 기술설계는 `DESIGN.md`가 우선하며 이
폴더는 이를 구현 가능한 구조도와 module별 납품계획으로 풀어낸다.

## 문서 지도

| 문서 | 읽는 목적 |
|---|---|
| [workflow-blueprint.md](workflow-blueprint.md) | 전체 workflow, 두 Gate, 실행 sequence, 실패·재개와 module dependency 구조도 |
| [module-delivery-plan.md](module-delivery-plan.md) | module별 입력·출력·의존성·첫 slice·검증·완료증거와 Wave 계획 |
| [composable-pipeline-plan.md](composable-pipeline-plan.md) | PipelineContext/Result/Registry, local pipeline과 total workflow 구현계약 |
| [workflow-at-a-glance.svg](diagrams/workflow-at-a-glance.svg) | 비기술 이해관계자용 한 장 인포그래픽 |
| [axcalib-visual-guide.md](axcalib-visual-guide.md) | AXCalib 철학, Library 활용법, API/Web/App 예상 적용 사례와 생성 자산 |
| [AXCalib ecosystem infographic](diagrams/axcalib-ecosystem-infographic.svg) | 철학·조합계층·적용면을 연결한 편집 가능한 16:9 인포그래픽 |
| [사람 권한 구조도](../manuals/diagrams/authority-model.svg) | 증거·보정·Agent 제안·관리자 HITL·사람 결정의 정확한 경계 |
| [제품 브리프](../product/product-brief.md) | Excalibur 기억 장치, 사용자 약속과 MVP 경계 |
| [개발 준비 감사](../readiness/development-readiness-audit.md) | supplied-PPTX offline slice 검증과 live/운영 NO-GO |
| [PPTX demo 기록](../evaluation/oled-qc-pptx-demo.md) | 실제 입력 hash, 등록/완료 결과와 quality-claim 경계 |
| [G3 Intelligence 개발 리포트](../evaluation/g3-intelligence-development-report.md) | policy/Docling/retrieval/model 구현·live probe·코드리뷰 결과 |
| [교육 프로그램/WP-01 개발 리포트](../evaluation/education-program-wp01-development-report.md) | actual-PPT lifecycle, program composition, local hardening과 코드리뷰 |
| [WP-02.Q1 근거 품질 리포트](../evaluation/wp02-actual-ppt-evidence-quality-report.md) | 제한형 actual-PPT render, gold locator, traceability metric과 코드리뷰 경계 |
| [WP-05.Q1 Qwen capability 리포트](../evaluation/qwen35-capability-validation-report.md) | provider proxy, exact checkpoint identity, on-prem 환경계약과 full-rubric 실패 경계 |
| [WP-01.R1.1 transaction recovery 리포트](../evaluation/wp01-r1-transaction-recovery-report.md) | project journal, crash injection, 무중복 reconcile과 남은 경계 |
| [교육 프로젝트 lifecycle](../workflows/education_project_lifecycle.md) | program→enrollment→project two-gate→program HITL 운영계약 |
| [AXCalib Workflow & Architecture deck](../presentations/AXCalib_Workflow_Architecture_v0.3-p1.pptx) | 두 Gate·pipeline·module·RAG·Wave를 설명하는 12장 검토자료 |
| [ADR-013](../adr/ADR-013-composable-local-pipelines.md) | 국소 pipeline 조합 방식을 채택한 결정과 결과 |
| [ADR-014](../adr/ADR-014-progressive-configuration-and-openapi.md) | 최소 facade, expert config와 OpenAPI 제어 경계 |
| [ADR-022](../adr/ADR-022-fail-closed-runtime-api.md) | runtime API의 fail-closed verifier/grant와 target/implemented 계약 분리 |
| [ADR-015](../adr/ADR-015-image-only-pptx-offline-evidence.md) | image-only PPTX sidecar와 same-hash final 처리 결정 |
| [ADR-016](../adr/ADR-016-review-policy-and-openai-compatible-evaluator.md) | hash-bound 심사기준, structured model, OpenAI/on-prem 환경계약 |
| [ADR-017](../adr/ADR-017-education-program-composition.md) | 교육 program/enrollment와 project 인증 경계, version/roll-up 결정 |
| [ADR-018](../adr/ADR-018-qwen-capability-and-provider-alias.md) | Qwen provider proxy와 exact deployment identity·structured-output 경계 |
| [ADR-019](../adr/ADR-019-json-object-contract-and-multimodal-probe.md) | JSON-object provider compatibility와 공통 multimodal probe 경계 |
| [ADR-020](../adr/ADR-020-local-project-transaction-journal.md) | local project journal, recovery, HITL artifact prerequisite와 남은 범위 |

## 권장 읽기 순서

1. visual guide 또는 인포그래픽으로 철학, 활용법과 예상 적용면을 본다.
2. workflow blueprint에서 분기와 사람 승인 지점을 확인한다.
3. module delivery plan에서 현재 상태와 선행조건을 확인한다.
4. composable pipeline plan에서 Python 계약과 구현 상세를 확인한다.
5. 실제 작업 전 단일 실행 원장 `PROJECT_STATE.md`의 P/WP/G Gantt, Active Slice와 최근 이력을
   확인하고 `prep.ps1 next`로 동일 frontmatter를 요약한다.

## 상태 표기

| 상태 | 의미 |
|---|---|
| not_started | 문서 계약도 구현도 없음 |
| interface_defined | 입력·출력·경계가 문서화됨 |
| offline_reference | local/synthetic 구현으로 핵심 계약 일부를 실행함 |
| contract_verified | module 단독 contract test와 working script가 통과함 |
| integrated | total workflow와 interface에서 같은 구현을 사용함 |
| pilot_validated | 승인된 비식별 pilot에서 품질·운영 지표를 검증함 |
| blocked_policy | 구현보다 정책·보안·권한 결정이 먼저 필요함 |

상태는 자동 진척률이 아니다. 다음 상태의 Exit Evidence가 모두 존재할 때만 승격한다.

## 구조도 유지 규칙

- 상태명, pipeline id, module id를 코드·schema와 동일하게 유지한다.
- workflow 분기가 바뀌면 Mermaid 구조도, module dependency, 요구 추적표를 같이 갱신한다.
- SVG는 요약 자료이며 세부 충돌 시 Mermaid와 기준 문서가 우선한다.
- PowerPoint도 요약자료이며 baseline, module 상태 또는 다음 slice가 바뀌면 함께 검토한다.
- 다이어그램에 Agent의 자동 final decision 경로를 추가하지 않는다.
- 실제로 구현되지 않은 노드는 완료색으로 표시하지 않는다.
- 구조도 변경 뒤 `prep.ps1 validate`, test/eval, local link와 SVG XML 검증을 수행한다.
