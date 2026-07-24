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

## Recipe 2: 실제 제안 PPT의 읽을 수 있는 통과·수용 예제

```powershell
uv run --no-sync python examples/case_lifecycle/run_readable_pass.py `
  --workspace output/example-readable-pass `
  --project-id example-readable-pass-001
```

등록심의 HITL 대기, 완료평가 HITL 대기와 최종 lifecycle summary를 Markdown/JSON으로 만든다.
실제 제안 PPTX와 synthetic 완료 PPTX를 사용하지만 기준은 해당 정보 흐름용 축소
`offline_reference`다. 공식 AX rubric, 실제 학습자 평가나 운영 인증 결과가 아니다.

`examples/catalog.yaml`에는 EX-01~EX-14의 persona, fixture, 명령, 기대 상태/실패와 cleanup이 있다.
첫 사용자는 Recipe 1/2만 보고, stale·알림·retrieval·model·identity·worker·batch 경계는 필요할 때
catalog에서 실행한다.

## Recipe 3: 교육 프로그램과 프로젝트 lifecycle

```powershell
uv run --no-sync python examples/education_project_lifecycle/run_full_lifecycle.py `
  --workspace output/example-education `
  --config config/axcalib.toml
```

이 예제는 immutable `program_id@version`, enrollment, milestone, project Dossier 연결과 두 사람 Gate를
보여 준다. 과정 기획자가 바꿀 수 있는 것은 allowlisted requirement/condition/Pipeline ID이며 임의 Python
import나 사람 Gate 우회는 허용하지 않는다.

## Recipe 4: 실제 제공 PPTX의 two-gate working script

```powershell
uv run --no-sync python scripts/pipelines/run_two_gate_pptx.py --help
```

옵션을 먼저 확인하고 별도 `output/` workspace에서 실행한다. working script는 파일 입력과 Library 호출만
담당하며 상태전이·판정·retry 규칙을 복사하지 않는다.

## Recipe 5: 긴 작업을 local Worker로 처리

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

## Recipe 6: 분리 검증으로 재개 가능하게 실행

```powershell
.\prep.ps1 test unit
.\prep.ps1 test integration-core
.\prep.ps1 test integration-eval
.\prep.ps1 test integration-ops
.\prep.ps1 test contract
```

중간에 프로세스가 종료되면 실패한 그룹만 다시 실행한다. memory-heavy Docling은 `.\prep.ps1 docling`로
분리하며, 기본 2,048MB 가용 메모리 preflight와 300초 watchdog을 통과하지 못하면 즉시
`BLOCKED_RESOURCE`로 종료한다.

## Recipe 7: Wiki를 두 플랫폼 형식으로 미리보기

```powershell
uv run --no-sync python scripts/wiki/sync_wiki.py validate
uv run --no-sync python scripts/wiki/sync_wiki.py export `
  --target github --output output/wiki-preview/github
uv run --no-sync python scripts/wiki/sync_wiki.py export `
  --target gitlab --output output/wiki-preview/gitlab
```

원격 전송은 일어나지 않는다. 실제 publication 규칙은 [문서 운영 규칙](Documentation-Governance)을
따른다.

## Recipe 8: Evaluation Owner gold package 확인

공식 품질평가는 Markdown 한 장이 아니라 승인 Markdown, 실행형 review-policy YAML, gold JSONL과
hash manifest를 함께 사용한다. 먼저 복사용 draft가 fail-closed 계약을 지키는지 확인한다.

```powershell
uv run --no-sync python scripts/pipelines/validate_evaluation_owner_package.py `
  --package docs/evaluation/templates/evaluation-owner-package `
  --allow-draft `
  --print-hashes
```

공식 package는 두 평가자의 adjudication, Owner threshold와 숨겨 둔 `test` split의 등록·완료 label을
모두 가져야 한다. 승인 전 draft 검증은 공식 모델 품질 통과가 아니다.

## Recipe 9: OIDC/JWKS local signed contract

실제 사내 IdP를 호출하지 않고 ephemeral RSA/EC key와 synthetic claim으로 valid/invalid 경계를
검증한다.

```powershell
uv sync --locked --dev --extra api --extra identity
uv run --no-sync pytest tests/unit/test_oidc_identity.py `
  tests/contract/test_oidc_api_contract.py -q
```

정상 token만 `ApiPrincipal`로 매핑된다. signature 변조, 만료, 다른 issuer/audience/type/key,
unmapped role/scope/org는 거부되고 key provider/config 장애는 503으로 구분된다. 이 recipe는 실제
SSO 연결·계정 회수·key rotation 증거가 아니다.

## Recipe 10: Evaluation Owner draft package 검증

```powershell
uv run --no-sync python scripts/pipelines/validate_evaluation_owner_package.py `
  --package docs/evaluation/templates/evaluation-owner-package `
  --allow-draft `
  --print-hashes
```

결과의 `official_quality_executable`은 `false`다. Owner가 published rubric, 양 Gate adjudicated
label과 threshold를 승인한 뒤 `--allow-draft` 없이 검증해야 공식 benchmark runner에 입력할 수 있다.

## Recipe 11: On-prem Qwen capability와 등록심의

exact checkpoint, structured text/vision, 테스트 PPTX 등록심의와 Docling을 한꺼번에 섞지 않고
단계별로 실행한다. 복사 가능한 PowerShell/Bash 명령, 기대 JSON과 실패 분류는
[On-prem Qwen 실행 검증](On-Prem-Qwen-Verification)을 따른다.
