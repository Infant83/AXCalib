---
rubric_id: axcalib.completion-checklist
version: 0.1.0
stage: completion
status: draft
owner: Evaluation Owner
---

# 완료평가 체크리스트

## 제출과 승인

- [ ] 완료 제출 dossier revision과 snapshot이 고정되어 있다.
- [ ] mentor가 배정됐다면 mentor 승인기록이 있다.
- [ ] mentor가 없다면 project owner 또는 관리자 제출 확인이 있다.
- [ ] completion submission report와 evaluation result report가 구분된다.

## 등록 baseline 비교

- [ ] approved registration 목표, 범위, KPI를 불러왔다.
- [ ] 원래 baseline, 승인된 변경, 최종결과를 분리했다.
- [ ] 미승인 변경이나 범위 누락을 risk로 표시했다.

## 수행증거와 KPI

- [ ] 산출물의 존재, 작동, 재현성과 version/hash를 확인했다.
- [ ] KPI observed value, unit, period, method, evidence locator가 있다.
- [ ] progress와 mentor 지적사항의 반영 여부를 확인했다.
- [ ] 실패, 한계, 보안·운영 위험과 후속계획을 포함했다.

## 유사과제 RAG

- [ ] completion stage corpus만 조회했다.
- [ ] 등록 당시 outcome이 completion 검색에 부당한 shortcut이 되지 않았다.
- [ ] adapter, query/rerank version, corpus snapshot을 기록했다.
- [ ] 유사점, 차이점, 적용 한계와 similarity portion을 표시했다.
- [ ] 유사성만으로 완료 통과를 제안하지 않았다.

## 평가초안과 HITL

- [ ] criterion별 evidence 또는 insufficient_evidence가 있다.
- [ ] Agent recommendation과 관리자 final decision이 분리되어 있다.
- [ ] stale/conflict 여부를 확인했다.
- [ ] 관리자 승인요청 notification event가 생성됐다.

