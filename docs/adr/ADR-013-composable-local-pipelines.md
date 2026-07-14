# ADR-013: 국소 파이프라인을 조합해 전체 workflow를 구성한다

- 상태: Accepted
- 날짜: 2026-07-14

## Context

AXCalib는 Python Library에서 시작해 script, CLI, API, worker, Web App으로 확장한다. 각 interface가
등록심의·완료평가 절차를 별도로 구현하면 판정, 상태전이, retry와 audit 의미가 달라진다. 반대로
처음부터 범용 workflow engine을 만들면 domain MVP보다 orchestration framework 개발이 앞설 수
있다.

## Decision

- dossier, ingest, retrieval, evaluation 등은 요소 모듈로 구현한다.
- 하나의 업무 목적을 완결하는 typed application service를 국소 pipeline class로 구현한다.
- 실행용 Python script는 국소 pipeline 또는 workflow facade를 호출하는 thin adapter로 둔다.
- 전체 workflow는 versioned local pipeline, branch, human wait/resume, checkpoint를 연결한다.
- CLI, API, worker는 script를 호출하지 않고 같은 library pipeline/workflow를 직접 호출한다.
- Web App은 API의 workflow state와 allowed command를 소비하며 로직을 복제하지 않는다.
- workflow는 domain state machine, mandatory HITL, mentor guard, snapshot invariant를 우회할 수 없다.
- 초기에는 명시적 Python composition과 allowlisted registry를 사용하고 arbitrary YAML graph나
  import path 실행을 허용하지 않는다.

## Consequences

요소 모듈과 업무 흐름을 독립적으로 시험하고 여러 interface에서 재사용할 수 있다. 등록심의
단독 실행, 전체 two-gate 실행, batch 같은 조합도 같은 결과계약을 유지할 수 있다. 대신 typed
context/result, pipeline/workflow versioning, checkpoint, idempotency와 import boundary test가
필요하다. 작은 기능을 무조건 pipeline으로 승격하지 않도록 독립 업무결과와 재사용자를 기준으로
경계를 검토한다.

상세 구현계획은 `docs/architecture/composable-pipeline-plan.md`를 따른다.
