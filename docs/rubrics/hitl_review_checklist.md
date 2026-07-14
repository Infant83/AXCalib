---
rubric_id: axcalib.hitl-review-checklist
version: 0.1.0
stage: hitl
status: draft
owner: Evaluation Owner
---

# 관리자 HITL 검토 체크리스트

## 대상과 버전

- [ ] project_id, stage, dossier revision/hash, snapshot을 확인했다.
- [ ] rubric, checklist, prompt/parser/model, corpus version을 확인했다.
- [ ] 결과가 stale 또는 conflict 상태가 아니다.

## Agent 오류·hallucination

- [ ] 각 observation이 인용된 원문 locator에서 실제로 확인된다.
- [ ] 제출자료에 없는 사실, 숫자, 원인관계를 생성하지 않았다.
- [ ] insufficient evidence를 임의 추론으로 채우지 않았다.
- [ ] structured output validation 실패가 성공으로 처리되지 않았다.

## 편향과 일관성

- [ ] 조직, 직무, 문서 표현력 등 무관한 요소가 판정에 영향을 주지 않았다.
- [ ] 모델 간 disagreement와 반복 편차가 숨겨지지 않았다.
- [ ] 위험한 자동 통과·탈락 제안이 없는지 확인했다.

## RAG와 가중치

- [ ] registration/completion stage filter가 올바르다.
- [ ] 유사사례의 공통점·차이점·적용 한계가 사실에 근거한다.
- [ ] 과거 outcome 또는 조직 metadata가 부당하게 누출되지 않았다.
- [ ] similarity portion, rubric weight 합계와 score 계산을 재검산했다.
- [ ] retrieval unavailable/empty가 정상 결과처럼 숨겨지지 않았다.

## 사람 결정과 알림

- [ ] 승인요청 notification delivery 또는 outbox 기록을 확인했다.
- [ ] Agent 제안을 수용, 수정, override, 반려 또는 추가자료 요청 중 하나로 처리했다.
- [ ] 관리자 actor, 결정 시각, 사유, 대상 revision을 기록했다.
- [ ] 최종 상태 전이는 관리자 권한으로만 수행했다.

