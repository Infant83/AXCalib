# Evaluation Owner 입력 패키지 템플릿

이 디렉터리는 `WP-03.Q2`의 공식 gold benchmark를 만들 때 복사해서 사용하는 **draft 템플릿**이다.
Markdown 하나만으로는 사람의 정책 의도와 실행 가능한 정답 데이터를 동시에 안전하게 표현하기
어렵기 때문에 네 파일을 분리한다.

| 파일 | 책임 | 작성자 |
|---|---|---|
| `OWNER_APPROVAL.md` | 목적, 데이터 경계, 승인·서명과 최종 체크리스트 | Evaluation Owner |
| `review-policy.yaml` | 두 Gate의 criterion ID, evidence tag, recommendation vocabulary | Evaluation Owner |
| `gold-labels.jsonl` | 비식별 project-stage별 정답 assessment, locator, reviewer/adjudication | 지정 평가자 |
| `benchmark-manifest.yaml` | 위 세 파일의 버전·hash와 Owner가 승인한 품질 threshold | Evaluation Owner |

## 작성 순서

1. 이 디렉터리를 승인된 비식별 작업영역으로 복사한다.
2. `review-policy.yaml`의 owner, criterion, reference와 status를 수정한다.
3. `gold-labels.jsonl`에 registration과 completion label을 한 줄에 한 JSON object로 작성한다.
4. 서로 독립된 평가자 두 명이 label을 검토하고 불일치는 adjudication한다.
5. `--hashes-only`로 policy canonical hash와 labels file hash를 계산해 `OWNER_APPROVAL.md`
   frontmatter에 기록한다.
6. 사람이 읽는 본문의 질문과 위험을 확인하고 승인정보를 기록한다.
7. policy, labels, approval 순서로 hash를 계산해 `benchmark-manifest.yaml`에 기록한다.
8. 숨겨 둔 adjudicated label을 `test` split으로 지정하고 manifest의 `evaluation_split`을
   `test`로 고정한다.
9. Owner가 정한 threshold를 manifest에 입력하고 status를 `approved`로 바꾼다.
10. 아래 validator를 실행한 후에만 benchmark report를 생성한다.

PowerShell:

```powershell
uv run --no-sync python scripts/pipelines/validate_evaluation_owner_package.py `
  --package path/to/copied-owner-package `
  --hashes-only

uv run --no-sync python scripts/pipelines/validate_evaluation_owner_package.py `
  --package docs/evaluation/templates/evaluation-owner-package `
  --allow-draft `
  --print-hashes
```

실제 승인 패키지는 `--allow-draft`를 제거한다. 승인 전에는 validator가 구조와 hash를 확인할 수는
있지만 품질 pass/fail은 만들지 않는다.

## Gold label 작성 원칙

- `project_id`는 비식별 ID만 사용한다.
- registration과 completion은 각각 해당 policy의 criterion을 정확히 한 번 포함한다.
- `met`, `partially_met`, `not_met`에는 반드시 안정적인 evidence locator를 넣는다.
- PPTX locator는 로컬 파일경로 대신 `pptx://slide/{number}`를 사용한다.
- 근거가 없으면 추론하지 않고 `insufficient_evidence`로 표시한다.
- gold recommendation은 Agent 초안의 기대값이며 최종 관리자 인증결정이 아니다.
- 공식 `approved` package는 두 평가자와 `adjudication_ref`를 가진 label만 허용한다.
- 개발 중 확인한 test label을 숨겨진 test split의 모델 선택에 재사용하지 않는다.
- 공식 pass/fail은 manifest가 고정한 `test` split만 계산하며 development/validation label은
  prompt나 모델 선택용 참고로만 사용한다.

## 품질지표

AXCalib은 다음 metric을 계산하지만 threshold 값은 임의로 정하지 않는다.

- criterion assessment accuracy
- Agent recommendation accuracy
- evidence locator precision/recall
- insufficient-evidence recall
- 필수 risk-flag recall
- adjudication 이전 평가자 pairwise agreement
- 위험한 자동 긍정 제안률: gold가 비긍정인데 `pass`/`accept`를 제안한 비율
- unsupported-claim rate

`approved` manifest에 Evaluation Owner가 threshold를 입력하고 승인하기 전에는 metric을 계산해도
공식 품질 통과로 해석하지 않는다. 실제 첫 baseline에는 양 Gate를 포함하고, 가능하면 과제 유형과
난이도별 경계 사례를 균형 있게 배치한다. insufficient-evidence, required risk flag 또는 비긍정
recommendation 사례가 하나도 없으면 해당 approved threshold check는 통과하지 않는다.
