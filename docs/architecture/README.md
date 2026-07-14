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
| [AXCalib Workflow & Architecture deck](../presentations/AXCalib_Workflow_Architecture_v0.3-p1.pptx) | 두 Gate·pipeline·module·RAG·Wave를 설명하는 12장 검토자료 |
| [ADR-013](../adr/ADR-013-composable-local-pipelines.md) | 국소 pipeline 조합 방식을 채택한 결정과 결과 |

## 권장 읽기 순서

1. 발표자료 또는 인포그래픽으로 전체 계층과 불변조건을 본다.
2. workflow blueprint에서 분기와 사람 승인 지점을 확인한다.
3. module delivery plan에서 현재 상태와 선행조건을 확인한다.
4. composable pipeline plan에서 Python 계약과 구현 상세를 확인한다.
5. 실제 작업 전 `PROJECT_STATE.md`와 `prep.ps1 next`를 확인한다.

## 상태 표기

| 상태 | 의미 |
|---|---|
| not_started | 문서 계약도 구현도 없음 |
| interface_defined | 입력·출력·경계가 문서화됨 |
| offline_reference | synthetic/in-memory 구현으로 핵심 계약 일부를 실행함 |
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
