# ADR-012: 단계별 retrieval과 설정 가능한 similarity portion

- 상태: Accepted with proposed operating guard
- 날짜: 2026-07-14

## Context

등록심의와 완료평가는 유사성의 의미가 다르며, embedding model과 실제 corpus는 아직 없다.
유사도 자체를 합격점수로 사용하면 과거 편향과 outcome leakage가 확대될 수 있다.

## Decision

- registration/completion corpus와 query를 논리적으로 분리한다.
- retrieval은 Protocol 뒤에 두고 null, lexical, vector, hybrid, 관리자 승인 adapter를 허용한다.
- raw similarity는 직접 합격점수가 아니라 commonality/difference/limitation을 포함한
  historical-consistency 신호의 입력이다.
- stage/rubric별 `similarity_portion`을 `0.0..1.0`으로 설정한다.
- offline 기본값은 lexical adapter와 portion `0.0`이다.
- `0.25` 초과는 warning을 내고 Evaluation Owner 승인을 요구하는 운영 guard를 제안한다.
- portion이 양수인데 retrieval이 없으면 조용히 가중치를 재분배하지 않는다.

## Consequences

실제 embedding 없이 상태·필터·리포트 계약을 개발할 수 있다. 다만 vector retrieval 품질과
적정 portion은 labeled corpus와 전문가 평가 전에는 검증됐다고 말할 수 없다.

