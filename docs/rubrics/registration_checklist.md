---
rubric_id: axcalib.registration-checklist
version: 0.1.0
stage: registration
status: draft
owner: Evaluation Owner
---

# 등록심의 체크리스트

## 입력과 재현성

- [ ] project_id, dossier revision, content hash, snapshot_id가 고정되어 있다.
- [ ] 적용 rubric/checklist version과 평가 run이 연결되어 있다.
- [ ] 필수 artifact가 hash와 source locator로 참조된다.

## 문제·목표·범위

- [ ] 해결할 문제와 AX 적용 필요성이 구체적이다.
- [ ] 목표, 범위, 제외범위가 서로 모순되지 않는다.
- [ ] 일정, 역할, 자원과 주요 위험이 현실적으로 제시되어 있다.

## KPI와 증거계획

- [ ] KPI마다 baseline, target, unit, period, measurement method가 있다.
- [ ] 목표 달성을 검증할 evidence와 locator 계획이 있다.
- [ ] 증거가 부족하면 추론하지 않고 insufficient_evidence로 표시한다.

## 데이터·보안·윤리

- [ ] 데이터 출처, 접근등급, 개인정보와 외부전송 위험이 확인됐다.
- [ ] 실제 자료 반입과 model endpoint가 승인 범위 안에 있다.
- [ ] 사람의 최종 승인 없이 자동 통과하지 않는다.

## 유사과제 RAG

- [ ] registration stage corpus만 조회했다.
- [ ] adapter, query version, corpus snapshot을 기록했다.
- [ ] 유사점, 차이점, 적용 한계와 source locator를 제시했다.
- [ ] similarity portion과 계산방식을 리포트에 표시했다.
- [ ] 과거 outcome을 현재 과제의 정답으로 사용하지 않았다.

## 평가초안 결과

- [ ] criterion별 assessment와 evidence가 구조화되어 있다.
- [ ] 통과·미통과 제안 모두 같은 형식의 리포트를 생성한다.
- [ ] Agent recommendation과 관리자 final decision 필드가 분리되어 있다.
- [ ] 관리자 승인요청 notification event가 생성됐다.

