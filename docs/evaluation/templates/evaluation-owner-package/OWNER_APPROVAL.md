---
schema_version: axcalib.evaluation-owner-approval/v1alpha1
benchmark_id: replace.ax-project.semantic-gold
benchmark_version: 0.1.0
status: draft
decision: pending
owner_ref: replace:evaluation-owner
approval_ref:
approved_at:
policy_id: replace.ax-project.review
policy_version: 0.1.0
policy_sha256: da528d736c27017c6221172a33aef567f561e534fdc636bb9d3f55d7b5678f53
labels_sha256: 54f299b4de5af992dc4cecc0fc1198063377fc53316cf404acccde13bcc373ab
data_classification: synthetic
external_model_allowed: false
---

# Evaluation Owner 승인서

이 문서는 평가기준과 gold label에 대한 사람 책임을 기록한다. `draft` 상태에서는 복사용
템플릿이며 공식 품질 baseline이 아니다.

## 1. 적용 범위

- 대상 사업/교육과정:
- 대상 과제 유형:
- 적용 certification level:
- 등록심의 적용범위:
- 완료평가 적용범위:
- 제외 대상:

## 2. 기준과 합격선 검토

- [ ] registration/completion criterion ID와 정의를 검토했다.
- [ ] critical criterion과 recommendation 규칙을 검토했다.
- [ ] threshold를 업무 위험도와 함께 검토했다.
- [ ] similarity portion과 historical-case 사용 한계를 검토했다.
- [ ] Agent 제안과 관리자 최종결정을 분리했다.

## 3. Gold label 품질

- [ ] 모든 label은 비식별 또는 승인된 데이터만 사용한다.
- [ ] 두 평가자가 독립적으로 검토했다.
- [ ] 불일치를 adjudication하고 참조번호를 기록했다.
- [ ] criterion별 assessment와 locator가 원문으로 역추적된다.
- [ ] 근거가 없는 항목은 `insufficient_evidence`로 표시했다.
- [ ] test split을 모델·prompt 선택에 사용하지 않았다.

## 4. 위험과 데이터 처리

- 개인정보/기밀정보 포함 여부:
- 외부 endpoint 전송 허용범위:
- 보존·삭제 기준:
- 예상 편향과 완화책:
- 위험한 자동 긍정 제안의 허용 한계:

## 5. 승인

- Evaluation Owner:
- 독립 Reviewer 1:
- 독립 Reviewer 2:
- Adjudicator:
- 승인 근거/회의록:
- 특이사항:

승인할 때 frontmatter의 `status`, `decision`, `approval_ref`, `approved_at`, policy/labels hash를
갱신한다. 본문 체크가 끝나지 않았다면 `approved`로 변경하지 않는다.
