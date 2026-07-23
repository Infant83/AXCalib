# 아키텍처와 프로젝트 구조

## 제품 계층

```text
Domain schema and state machine
        ↓
Element modules: dossier / ingest / retrieval / evaluation / report / audit
        ↓
Local pipeline classes with typed input and output
        ↓
Versioned workflow: branch / human wait-resume / checkpoint
        ↓
CLI / API / Worker / Web adapters
```

Core Library는 FastAPI, 특정 프론트엔드, 특정 LLM, Deep Agents 또는 특정 Vector DB에 의존하지 않는다.
외부 시스템은 Protocol이나 adapter 뒤에 둔다.

HTTP identity도 같은 원칙을 따른다. optional `identity` adapter가 issuer-bound JWK snapshot을
검증해 `ApiPrincipal`을 만들고, Library state machine은 그 뒤에도 관리자 HITL과 revision guard를
다시 확인한다. 현재는 local signed reference이며 remote discovery/rotation과 실제 assignment는
운영 Owner 승인 전 미구현이다.

## 주요 디렉터리

| 경로 | 역할 |
|---|---|
| `src/axcalib/` | 배포되는 Python Library |
| `src/axcalib/pipelines/` | 독립 업무 목적의 typed local Pipeline |
| `src/axcalib/runtime/` | 실행, checkpoint, batch, queue와 transaction recovery |
| `apps/api`, `apps/worker`, `apps/web` | Library를 소비하는 delivery adapter |
| `scripts/pipelines/` | argument/file I/O만 담당하는 working script |
| `config/` | offline-safe 기본 및 expert profile |
| `fixtures/synthetic/` | 실제 개인정보가 없는 고정 입력 |
| `tests/`, `evals/` | 동작 회귀와 품질 평가를 분리한 검증 |
| `docs/` | 요구·설계·ADR·rubric·report의 기준 문서 |
| `wiki/` | GitHub/GitLab Wiki로 배포할 사용자용 단일 원본 |
| `PROJECT_STATE.md` | P/WP/G, Active Slice, 검증과 append-only 개발 실행 원장 |

## 두 Gate 상태 불변조건

- 등록심의를 통과하기 전에 수행 단계로 갈 수 없다.
- Agent의 평가초안은 반드시 등록·완료 각각의 HITL pending을 거친다.
- notification event가 기록되지 않으면 HITL pending 전이를 완료하지 않는다.
- 멘토가 배정되면 mentor 승인 없이 완료평가 제출을 등록하지 않는다.
- 완료평가는 등록 때 고정한 목표·KPI·범위와 누적 증거를 함께 비교한다.
- 사람 승인 없이 `registration_approved`, `completion_accepted`, `certified`로 전이하지 않는다.

## 교육 프로그램 composition

기획자는 immutable `program_id@version`에 level, milestone, prerequisite, typed requirement와 allowlisted
Pipeline을 선언한다. 학습자 가입 시 version과 SHA-256을 고정한다. 새 program version이 생겨도 기존
enrollment를 조용히 이동시키지 않는다.

Project milestone에는 같은 program version, enrollment, learner context의 Dossier만 연결한다.
Project 완료 수용은 교육 milestone의 근거이지 과정 전체 인증의 자동 결정이 아니다.

## 아키텍처 확인 순서

메인 저장소에서 다음 문서를 기준으로 삼는다.

1. `WORK_SPEC.md`: 제품 요구와 범위
2. `GOAL.md`: Phase, WP, Gate 수용기준
3. `DESIGN.md`: 기술·UX 설계
4. `docs/architecture/workflow-blueprint.md`: Mermaid 구조 기준
5. `docs/architecture/module-delivery-plan.md`: M00~M13 module control board
6. `docs/adr/`: 중요한 선택과 결과

현재 구현 상태는 [개발 실행 원장](Development-Ledger)에서 확인한다.
