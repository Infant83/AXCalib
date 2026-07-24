# 읽을 수 있는 Case Lifecycle 예제

이 예제는 작업공간의 실제 제안 PPTX와 별도 synthetic 완료 PPTX를 사용해 다음 흐름을 보여 준다.

```text
register_case → 등록심의 Agent pass 제안 → 관리자 승인
→ mentor 배정 → 수행 기록 → 완료 제출 승인
→ 완료평가 Agent accept 제안 → 관리자 수용
→ case.get_current_status / case.get_summary
```

`review-profile.example.yaml`은 해당 두 fixture로 Library 정보 흐름을 검증하기 위한 축소
`offline_reference` 기준이다. 공식 AX rubric, 실제 학습자 평가 또는 운영 인증 결과가 아니다.
기본 rubric의 부족한 데이터·보안·역할·자원 근거를 숨기기 위한 대체 기준으로 사용해서는 안 된다.

새 output 경로에서 실행한다.

```powershell
uv run --no-sync python examples/case_lifecycle/run_readable_pass.py `
  --workspace output/examples/readable-pass-001 `
  --project-id readable-pass-001
```

생성되는 읽기 자료:

- `01-registration-hitl-pending.md`: Agent가 pass를 제안했지만 사람 결정 전임을 표시
- `02-completion-hitl-pending.md`: Agent가 accept를 제안했지만 사람 결정 전임을 표시
- `03-final-summary.md`: 등록·수행·완료평가와 두 사람 결정을 한 문서로 연결
- `03-final-summary.json`: 같은 의미의 typed JSON projection
- `run-result.json`: 자동 확인용 최소 결과와 품질 주장 한계

같은 project ID가 이미 있는 workspace에서는 덮어쓰지 않고 실패한다. 다른 `--workspace` 또는
`--project-id`를 사용한다.
