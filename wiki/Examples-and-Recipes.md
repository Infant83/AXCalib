# 예제와 Recipe

모든 예제는 기본적으로 synthetic 또는 저장소 fixture를 사용한다. 실제 사내 제출자료를 외부 endpoint로
보내지 않는다.

## Recipe 1: 첫 등록심의만 실행

```powershell
uv run --no-sync python examples/library_mvp_alpha_quickstart.py `
  --workspace output/example-registration
```

결과에서 `waiting_human`, report URI, allowed command를 확인한다. 이 예제가 가장 작은 Library Alpha
smoke다.

## Recipe 2: 교육 프로그램과 프로젝트 lifecycle

```powershell
uv run --no-sync python examples/education_project_lifecycle/run_full_lifecycle.py `
  --workspace output/example-education `
  --config config/axcalib.toml
```

이 예제는 immutable `program_id@version`, enrollment, milestone, project Dossier 연결과 두 사람 Gate를
보여 준다. 과정 기획자가 바꿀 수 있는 것은 allowlisted requirement/condition/Pipeline ID이며 임의 Python
import나 사람 Gate 우회는 허용하지 않는다.

## Recipe 3: 실제 제공 PPTX의 two-gate working script

```powershell
uv run --no-sync python scripts/pipelines/run_two_gate_pptx.py --help
```

옵션을 먼저 확인하고 별도 `output/` workspace에서 실행한다. working script는 파일 입력과 Library 호출만
담당하며 상태전이·판정·retry 규칙을 복사하지 않는다.

## Recipe 4: 긴 작업을 local Worker로 처리

Producer와 Worker가 같은 workspace를 사용해야 한다.

```python
prepared = client.enqueue_pipeline(
    pipeline_id,
    pipeline_version,
    payload,
    context=context,
)
worker = client.create_worker(worker_id="local-worker-01")
completed = worker.run_once()
```

명령행 Worker는 한 건만 처리하고 종료한다.

```powershell
uv run --no-sync python scripts/pipelines/run_local_worker_once.py --help
```

현재 queue는 single-host filesystem Alpha다. 여러 서버가 같은 디렉터리를 공유하는 distributed queue로
간주하지 않는다.

## Recipe 5: 분리 검증으로 재개 가능하게 실행

```powershell
.\prep.ps1 test unit
.\prep.ps1 test integration
.\prep.ps1 test contract
```

중간에 프로세스가 종료되면 실패한 그룹만 다시 실행한다. memory-heavy Docling은 `.\prep.ps1 docling`로
분리한다.

## Recipe 6: Wiki를 두 플랫폼 형식으로 미리보기

```powershell
uv run --no-sync python scripts/wiki/sync_wiki.py validate
uv run --no-sync python scripts/wiki/sync_wiki.py export `
  --target github --output output/wiki-preview/github
uv run --no-sync python scripts/wiki/sync_wiki.py export `
  --target gitlab --output output/wiki-preview/gitlab
```

원격 전송은 일어나지 않는다. 실제 publication 규칙은 [문서 운영 규칙](Documentation-Governance)을
따른다.
