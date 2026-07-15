# Review Policy Pack v1alpha1

`axcalib.review-policy-pack/v1alpha1`은 한 과제에 적용할 등록심의·완료평가 기준을 함께 고정하는
strict YAML 계약이다. 실행 기준은 `src/axcalib/policies/registry.py`의 Pydantic model이다.

## 최소 구조

```yaml
schema_version: axcalib.review-policy-pack/v1alpha1
policy_id: example.program
version: 1.0.0
status: offline_reference       # draft | offline_reference | published | retired
owner: evaluation-owner-id
approval_ref: null              # published이면 필수
description: 정책 목적과 적용 경계
registration:
  stage: registration
  rubric_id: example.registration
  rubric_version: 1.0.0
  checklist_refs: [docs/rubrics/example-registration.md]
  references: []
  criteria: []
  all_met_recommendation: pass
  gap_recommendation: needs_changes
completion:
  stage: completion
  rubric_id: example.completion
  rubric_version: 1.0.0
  checklist_refs: [docs/rubrics/example-completion.md]
  references: []
  criteria: []
  all_met_recommendation: accept
  gap_recommendation: needs_changes
```

각 criterion은 `criterion_id`, `title`, 하나 이상의 `required_tags`, `follow_up`, `critical`, 선택적
`blocking_recommendation`을 가진다. reference는 authority(`normative`, `guidance`, `historical`),
URI, version과 가능한 경우 SHA-256을 가진다.

## 선택과 동결

- 호출자는 `example.program@1.0.0`처럼 정확한 selector를 사용한다.
- registry는 임의 import path나 expression을 실행하지 않고 등록된 YAML만 읽는다.
- 같은 ID/version의 다른 canonical hash는 collision으로 거부한다.
- dossier 생성 시 selector, canonical hash, status, source URI를 `ReviewProfileRef`로 고정한다.
- 평가 시 현재 registry의 hash가 dossier hash와 다르면 실행하지 않는다.
- `offline_reference`는 명시적으로 허용된 local runtime에서만 선택된다.
- `published`는 `approval_ref`가 있어야 하며, 운영 권한·배포 통제는 후속 runtime의 책임이다.

## Context와 편향 경계

`ReviewContext`는 `program_id`, `business_unit_id`, `proposer_org_id`, `certification_level`을 보존한다.
현재 구현은 이 값을 model prompt에 넣거나 자동 점수 조정에 사용하지 않는다. 향후 selector 매핑은
별도 승인된 정책이어야 하며, 매핑 version·근거·변경 이력과 subgroup 편향 평가를 남겨야 한다.

## 변경 규칙

criterion, recommendation, reference 또는 checklist content가 바뀌면 새 policy version을 만든다.
기존 version의 YAML이나 연결 문서를 제자리 수정해 과거 실행의 의미를 바꾸지 않는다. 현재 기본
정책은 `config/review_profiles/axcalib-default-v1.yaml`의 offline reference다.
