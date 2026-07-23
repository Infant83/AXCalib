# 개발 프로세스

AXCalib는 **P / WP / G** 세 축으로 개발을 관리한다.

- P(Phase): 제품이 성숙하는 큰 개발 단계
- WP(Work Package): 독립적으로 계획·검증·인수할 수 있는 작업 묶음
- G(Gate): 다음 단계로 넘어가기 위해 필요한 증거와 승인 기준

## 단일 실행 원장

메인 저장소의 `PROJECT_STATE.md`가 일정, Active Slice, dependency, 검증 결과, blocker와 개발 이력의
단일 원본이다. 현재 내용은 배포할 때 frontmatter를 제외하고 [개발 실행 원장](Development-Ledger)으로
자동 복사된다.

원장의 현재 상태 절은 갱신할 수 있지만 작업 이력 절은 **append-only**다. 과거 기록을 조용히
수정하지 않고 정정 entry를 추가한다.

## 한 Slice의 표준 흐름

1. 기준 확인: README, WORK_SPEC, GOAL, DESIGN, PROJECT_STATE와 작업 트리를 읽는다.
2. 범위 고정: 요구와 acceptance criteria를 한 문장으로 적는다.
3. 착수 기록: Active Slice, dependency, 예상 Exit Evidence를 원장에 남긴다.
4. 최소 구현: domain/port → 요소 모듈 → Pipeline → script 순으로 가장 작은 end-to-end를 만든다.
5. 코드리뷰: 상태전이, 사람 Gate, 보안, idempotency, stale/recovery와 API 의미를 감사한다.
6. 분리 검증: unit → integration → contract → eval → static/validate 순으로 실행한다.
7. 문서 동기화: 요구, ADR, report, diagram, Wiki 사용법과 원장을 같은 change set에서 갱신한다.
8. 체크포인트: 변경 범위와 미검증을 확인한 뒤 승인된 경우 commit/push한다.

## 검증 명령

```powershell
.\prep.ps1 status
.\prep.ps1 next
.\prep.ps1 validate
.\prep.ps1 test unit
.\prep.ps1 test integration
.\prep.ps1 test contract
.\prep.ps1 eval
```

Wiki 계약은 `prep validate`에 포함되며 별도로 다음 명령도 제공한다.

```powershell
uv run --no-sync python scripts/wiki/sync_wiki.py validate
```

## 완료라고 말할 때 필요한 증거

- 변경한 요구사항 또는 WP와 파일
- 실제 실행한 validation/test/eval 명령과 수치
- 실패 여부와 실행하지 못한 검증의 이유
- 새 결정·위험·후속 dependency
- 구조가 바뀌었다면 diagram과 module control 갱신
- PROJECT_STATE의 Active Slice와 새로운 append-only history ID
- 사용자 인터페이스나 운영법이 바뀌었다면 관련 Wiki page

문서만 작성한 단계는 제품 기능 완료가 아니다. synthetic test는 실제 사내 데이터 품질이나 운영 보안을
증명하지 않는다.

## 현재 진행상태 읽기

가장 최신 내용은 [개발 실행 원장](Development-Ledger)에서 확인한다. 사용자 관점의 실행법은
[5분 시작](Getting-Started), 개발 구조는 [아키텍처와 프로젝트 구조](Architecture-and-Project)를 따른다.
