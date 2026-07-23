# AXCalib 5분 시작

이 예제는 네트워크·GPU·Vector DB 없이 제공된 PPTX fixture를 등록심의 첫 사람 Gate까지 실행한다.

## 1. 환경 준비

```powershell
uv sync --frozen
.\.venv\Scripts\python.exe -m pip --version
```

Python baseline은 3.12 이상이다. `.venv/`, `output/`, API key와 실제 제출자료는 Git에 넣지 않는다.

## 2. 가장 작은 예제 실행

```powershell
uv run --no-sync python examples/library_mvp_alpha_quickstart.py `
  --workspace output/wiki-quickstart
```

예제는 다음 순서로 동작한다.

1. `AXCalib(workspace)` 인스턴스를 만든다.
2. `register_case(...)`로 PPTX와 sidecar를 한 Project Dossier에 등록한다.
3. `submit_registration(...)`으로 등록심의 제출 revision을 고정한다.
4. `evaluate(..., "registration")`으로 평가초안과 report를 생성한다.
5. `registration_hitl_pending`에서 멈추고 관리자 결정을 기다린다.

## 3. Python 코드로 확인

```python
from axcalib import AXCalib

ax = AXCalib("output/my-first-case")
dossier = ax.register_case(
    "tests/sources/oled_qc_project_outline.pptx",
    title="OLED QC 등록심의 예제",
    sidecar_path="tests/sources/oled_qc_project_outline.axcalib.json",
    project_id="wiki-demo-001",
)
ax.submit_registration(dossier.project_id)
draft = ax.evaluate(dossier.project_id, "registration")

print(draft.status)
print(draft.dossier_status)
print(draft.report_markdown_uri)
```

관리자 결정 없이 승인 상태로 넘어가지 않는 것이 정상이다. `report_markdown_uri`는 평가초안이지
최종 인증서가 아니다.

## 4. 기본 검증

긴 검증은 메모리와 프로세스를 격리해 나눠 실행한다.

```powershell
.\prep.ps1 validate
.\prep.ps1 test unit
.\prep.ps1 test integration
.\prep.ps1 test contract
.\prep.ps1 eval
```

Docling 계약은 별도의 선택 명령으로 실행한다.

```powershell
.\prep.ps1 docling
```

다음 단계는 [Library 매뉴얼](Library-Manual)과 [두 Gate 실습](Two-Gate-Tutorial)이다.
