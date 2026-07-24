# ADR-029: Project-id-bound Case Read Facade

- Status: Accepted for local Library Alpha
- Date: 2026-07-24
- Decision owner: AXCalib architecture baseline; operational API owner remains open

## Context

`register_case(...)`는 사용자 문서에서 `case`로 불렸지만 실제 반환형은 생성 직후의 frozen
`ProjectDossier`였다. 이후 관리자 결정과 수행 기록이 저장돼도 그 Python 값은 갱신되지 않았다.
또한 `ReportRenderer`는 한 Gate의 immutable Agent report만 렌더하므로 “지금 어느 단계인가”와
“등록·수행·완료 결과가 어떻게 연결됐는가”를 한 호출로 답할 수 없었다.

Dossier에 repository/service를 숨겨 넣으면 domain record가 transport와 storage에 결합되고,
ReportRenderer가 file read와 state semantics를 가지면 불변 report와 lifecycle summary의 책임이
섞인다.

## Decision

1. `AXCalib.register_case(...)`는 project_id와 read dependency만 가진 live `Case`를 반환한다.
2. `Case`는 mutable state를 cache하지 않고 모든 status/summary 호출에서 최신 dossier를 다시 읽는다.
3. `get_current_status/aget_current_status`는 현재 상태, 대기 대상, domain-valid next action과 최신
   Gate 결과를 반환한다.
4. `get_summary/aget_summary`는 등록심의·수행·완료평가를 연결하되 Agent assessment, 사람 결정과
   effective assessment를 분리한다.
5. object가 기본이며 `format=json|md`, `verbose=false|true`만 제공한다.
6. `ReportRenderer`는 기존 immutable Agent report renderer로 유지하고 `CaseViewRenderer`는 이미
   조립된 typed projection만 순수 렌더링한다.
7. raw latest dossier는 `case.dossier`, initial raw snapshot 호환은 `create_project(...)`로 제공한다.
8. report read는 reports root, size, schema, project/stage/report/snapshot/policy/artifact identity와
   active/archive committed transaction SHA-256을 fail-closed로 검증한다.
9. 기본 projection은 local URI, storage path, criterion excerpt, actor/rationale를 제외한다.
   `verbose=True`는 local Library 권한을 전제로 한 명시적 확장이며 remote API authorization을
   대신하지 않는다.

## Consequences

- 사람의 수정이 같은 `Case`에서 즉시 보이면서 Agent report 원본은 불변으로 남는다.
- Python/JSON/Markdown이 같은 typed source를 사용해 정보 흐름이 일관된다.
- 기존 `register_case` 반환형을 `ProjectDossier`로 강제한 외부 Alpha 코드는 `case.dossier` 또는
  `create_project`로 명시적으로 이동해야 한다.
- report 조회는 local journal 수에 선형이며 pilot storage에서는 report hash index가 필요하다.
- remote API/Web은 verbose projection을 그대로 반환하지 않고 principal-bound safe view를
  별도로 조립해야 한다.
- journal hash anchor가 없는 오래된 local report는 조용히 신뢰하지 않고 다시 평가하거나 migration
  해야 한다.

## Rejected alternatives

- `ProjectDossier.get_summary()`: frozen domain record에 repository/service 생명주기를 결합한다.
- `ReportRenderer.get_current_status()`: 단일 report rendering과 lifecycle read semantics를 섞는다.
- Agent report를 사람 보정 결과로 rewrite: 원본 model 결과와 감사 경계를 잃는다.
- 별도 summary 저장파일을 새로운 진실원천으로 운영: dossier와 drift할 수 있다.

