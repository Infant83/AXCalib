# 교육 프로젝트 인증 lifecycle 예제

이 예제는 “과정에 등록한 학습자가 단계별 수업·프로젝트·평가를 완료하고, 프로젝트와 과정
완료 모두 권한 있는 관리자의 확인을 거친다”는 흐름을 Python Library 관점에서 보여 준다.

## 인증 단위와 경계

- 현재 AXCalib의 실제 심사 단위는 제출 프로젝트 하나와 그 dossier다.
- 교육 프로그램은 여러 마일스톤을 연결하는 상위 blueprint다.
- 프로그램 가입 시 해당 version의 목표와 조건이 enrollment에 생성된다.
- 프로젝트 마일스톤은 임의 점수 입력이 아니라 실제 dossier 상태를 읽는다.
- program version·enrollment·milestone·learner context가 모두 일치하는 dossier만 연결한다.
- 프로젝트 `completion_accepted`는 프로젝트 마일스톤 완료조건일 뿐 과정 전체 인증은 아니다.
- 모든 필수 마일스톤 완료 뒤에도 과정 상태는 `completion_hitl_pending`에서 멈춘다.
- 이 fixture의 관리자·강사·멘토 ID는 인증되지 않은 synthetic actor다.

## 사용 자료

| 역할 | 자료 |
|---|---|
| 등록 제안서 | `tests/sources/oled_qc_project_outline.pptx` |
| 등록 sidecar | 원본 SHA-256에 고정된 수동 시각 요약 |
| 완료보고서 | `fixtures/synthetic/education_project_lifecycle/completion_report.synthetic.pptx` |
| 프로그램 | `fixtures/synthetic/education_project_lifecycle/program.yaml` |

원본 제안서는 수정하거나 외부 endpoint로 보내지 않는다. 완료보고서는 실제 연구성과가 아니라
별도 hash를 가진 명시적 synthetic fixture다.

## 상태 흐름

~~~text
Program 0.1.0 publish
→ learner enroll
→ orientation available / 나머지 locked
→ 강사 이수 확인
→ OLED project milestone available
→ 실제 PPT register_case + enrollment bind
→ registration evaluate → waiting_human → 관리자 approve
→ mentor 배정 + execution + progress
→ synthetic completion 제출 + mentor 승인
→ completion evaluate → waiting_human → 관리자 accept
→ enrollment가 project dossier 상태를 sync
→ reflection 평가 85점
→ program completion_hitl_pending + 승인요청 기록
→ 관리자 approve
→ enrollment completed
~~~

## 실행

빈 workspace 경로를 사용한다.

~~~powershell
uv run --no-sync python examples/education_project_lifecycle/run_full_lifecycle.py `
  --workspace output/education-project-lifecycle
~~~

동일한 교육 command에 idempotency key를 다시 보내면 저장된 구조적 결과를 반환한다. 같은 key를
다른 command body에 재사용하면 거부한다. 프로젝트의 관리자 결정은 예제에서도 별도 명시적
호출이며 Agent report가 대신 만들지 않는다.

## 향후 API/Web 매핑

`EducationProgramPipeline`의 typed command와 `EducationPipelineResult`가 전달 경계다. 향후
API는 command를 JSON으로 검증해 같은 Library pipeline을 호출하고, Web App은
`enrollment_status`, `active_milestone_ids`, `allowed_commands`를 렌더링한다. UI가 상태전이,
점수조건 또는 프로젝트 승인 로직을 다시 구현하지 않는다.
