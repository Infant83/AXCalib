# AXCalib Example Catalog

첫 사용자는 두 경로만 보면 된다.

1. `library_mvp_alpha_quickstart.py`: 실제 제안 PPTX를 등록하고 첫 관리자 HITL에서 멈춘다.
2. `case_lifecycle/run_readable_pass.py`: 실제 제안 PPTX와 synthetic 완료 PPTX를 두 Gate로
   연결하고 `Case`의 Markdown/JSON 상태·요약을 만든다.

```powershell
uv run --no-sync python examples/library_mvp_alpha_quickstart.py `
  --workspace output/examples/quickstart

uv run --no-sync python examples/case_lifecycle/run_readable_pass.py `
  --workspace output/examples/readable-pass `
  --project-id readable-pass-001
```

두 번째 예제의 축소 기준은 Library 정보 흐름을 확인하는 `offline_reference`이며 공식 AX
rubric이나 실제 학습자 인증이 아니다.

## 문제 상황별 자가점검

`catalog.yaml`은 EX-01~EX-13을 정상, 사람 대기, 반려, stale, 알림, retrieval, model, identity,
worker, 교육 context, batch 실패와 Evaluation Owner gold package 검증으로 나눈 실행 원장이다.
각 항목은 다음을 포함한다.

- persona와 synthetic fixture
- 그대로 실행할 PowerShell 명령
- 기대 상태 또는 기대 실패
- 실제 pytest evidence
- output 정리 방식

전체 catalog 계약만 빠르게 확인하려면 다음 명령을 사용한다.

```powershell
uv run --no-sync pytest tests/unit/test_example_catalog.py -q
```

외부 모델·실제 계정·실제 수강생 데이터는 어느 catalog 기본 명령에도 사용하지 않는다.
