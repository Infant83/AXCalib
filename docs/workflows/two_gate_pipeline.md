# AXCalib 두 Gate 작업지침

이 문서는 등록심의와 완료평가의 실행 순서, 사람 책임, 보고서, 알림, 유사과제 검색의
최소 계약을 정의한다. Agent 결과는 항상 평가초안이며 관리자 결정과 분리한다.

## 1. 등록심의 제출과 평가

과제 수행자는 dossier의 등록 proposal, KPI, 범위, 일정, evidence reference를 작성한다.
시스템은 revision과 SHA-256 snapshot을 고정한 뒤 등록 체크리스트로 평가초안을 생성한다.
등록 단계의 historical case만 검색하고, 검색 adapter와 corpus snapshot을 기록한다.

## 2. 등록심의 결과와 HITL

### 2.1 Agent가 통과를 제안한 경우

`registration_evaluation_report`를 작성하고 `registration_hitl_pending`으로 전이하기 전에
관리자 승인요청 알림을 기록하거나 전송한다. Agent 제안만으로
`registration_approved`가 되지 않는다.

### 2.2 Agent가 미통과를 제안한 경우

미충족 criterion, 부족한 증거, 보완 가능 여부를 포함한 동일 형식의 리포트를 작성한다.
관리자 HITL이 미통과를 확정하면 `registration_rejected`로 종료한다. 관리자가 Agent 오류를
확인하면 결과를 수정하거나 추가자료를 요청할 수 있다.

### 2.3 관리자 HITL

관리자는 `docs/rubrics/hitl_review_checklist.md`로 hallucination, unsupported claim, 편향,
RAG stage leakage, 가중치 계산, evidence locator를 확인한다. 최종 결정은 승인, 반려,
보완요청, Agent 제안 override 중 하나이며 actor, 시각, 사유, 대상 revision을 감사기록에
남긴다.

알림은 필수다. production adapter 후보는 GitLab Merge Request와 email이며, offline
하네스는 외부 전송 없이 recording adapter로 event 발생을 검증한다. 알림 기록에 실패하면
HITL pending 전이를 완료하지 않는다.

## 3. 선택적 멘토 배정

등록 승인 뒤 관리자는 멘토를 배정할 수 있다. 멘토가 없어도 수행을 시작할 수 있다.
멘토가 배정되면 mentor_ref, 배정자, 배정 시각을 기록한다.

## 4. 과제 수행과 dossier 갱신

과제 수행자는 progress, mentor note, artifact, KPI observation, risk, approved change를 같은
dossier에 누적한다. 등록 당시 approved baseline은 덮어쓰지 않고 change request로 연결한다.
모든 갱신은 expected_revision과 atomic replace를 사용한다.

## 5. 완료평가 진입 승인

과제 수행자가 완료 제출을 요청한다. 멘토가 배정된 경우 mentor 승인 없이는 완료평가
제출을 등록할 수 없다. 멘토가 없는 경우 project owner 또는 관리자가 제출을 확인할 수
있다.

## 6. 완료평가 제출 리포트 등록

`completion_submission_report`는 수행자가 만드는 제출 문서다. 등록 baseline, 승인된 변경,
최종 산출물, KPI 관측, 실패와 한계를 포함한다. 필요한 내부 품의 또는 mentor 승인을 받은
뒤 완료평가 입력으로 등록한다. 이 문서는 다음 단계의 평가결과 리포트와 다르다.

## 7. 완료평가와 평가결과 리포트

시스템은 완료 dossier snapshot과 approved registration baseline을 비교한다. completion
stage historical case만 RAG하고 `completion_evaluation_report`를 작성한다. 리포트에는
criterion 결과, evidence, baseline diff, 유사점·차이점·적용 한계, corpus snapshot,
similarity portion, Agent recommendation을 포함한다.

## 8. 완료평가 HITL

등록심의와 같은 HITL checklist를 적용하고 관리자 승인요청 알림을 필수로 발생시킨다.
관리자는 Agent 오류·편향·hallucination과 historical case 영향, stale 여부를 검토한다.

## 9. 최종 완료 결정

관리자만 `completion_accepted` 또는 `completion_not_accepted`를 확정한다. AX Level 또는
공식 인증은 완료평가와 분리된 후속 policy Gate다.

## RAG와 similarity portion

- registration과 completion corpus/query를 분리한다.
- adapter는 `null`, `lexical`, `vector`, `hybrid` 또는 관리자 승인 구현체로 교체할 수 있다.
- raw cosine/dense similarity를 직접 합격점수로 사용하지 않는다.
- 유사점, 차이점, 적용 한계를 평가한 historical-consistency signal에만 portion을 적용한다.
- portion은 stage/rubric별 `0.0..1.0` 설정이며 기본값은 `0.0`이다.
- `0.25` 초과는 harness warning과 Evaluation Owner의 명시적 승인을 요구한다.
- portion이 0보다 큰데 adapter/corpus가 없으면 가중치를 조용히 재배분하지 않고 평가를
  차단하거나 insufficient evidence로 반환한다.

## 실제 Python implementation contract

이 전체 순서를 interface script에 복사하지 않는다. dossier freeze, evidence 준비,
stage retrieval, 평가, report, review request, 관리자 decision을 국소 pipeline으로 구현하고
`two-gate-standard` workflow가 분기와 사람 대기/재개를 연결한다. script, CLI, API, worker는
같은 library pipeline/workflow를 호출한다. 상세 경계는
`docs/architecture/workflow-blueprint.md`, `docs/architecture/composable-pipeline-plan.md`와
ADR-013을 따른다.

~~~python
from pathlib import Path

from axcalib import AXCalib
from axcalib.pipelines import TwoGatePptxRequest

client = AXCalib.from_toml("config/axcalib.toml", workspace="output/review")
summary = client.run_pptx(
    TwoGatePptxRequest(
        proposal_path=Path("proposal.pptx"),
        title="검토할 과제",
    )
)
assert summary.final_status.value == "registration_hitl_pending"
~~~

2026-07-16 slice는 dossier persistence, JSON/Markdown report, recording notification과 명시적
관리자 decision까지 구현한다. GitLab/email, durable outbox, embedding, Vector DB, live model,
API/Web은 후속 WP다.
