# WP-06.I5a On-prem Qwen Verification CLI 개발 리포트

- Date: 2026-07-24
- Phase / WP / Gate: P7 / WP-06.I5a / G4 Interfaces
- Requirement: FR-023, FR-036, FR-052, FR-063
- Status: `verified_local_interface`; exact on-prem execution pending
- Quality boundary: local fake endpoint와 문서/packaging contract; exact on-prem 품질 아님

## 1. 결과

기존 `probe_qwen35_capabilities.py`가 소유하던 canonical environment와 Qwen route 조립을
`probe_qwen35_from_env()` Library service로 이동했다. working script와 새
`axcalib verify qwen`은 같은 service를 호출하므로 exact checkpoint, text/vision, structured output,
identity와 report 의미가 한 곳에 유지된다.

사내 사용자는 다음의 짧은 명령을 우선 사용할 수 있다.

```powershell
uv run --no-sync axcalib verify qwen `
  --expected-checkpoint Qwen3.5-397B-A17B `
  --scope deployment `
  --output output/onprem/qwen35-capability.json
```

설치 entrypoint를 사용할 수 없는 진단환경에는 `python -m axcalib.cli` fallback이 있다. 기존 script
entrypoint도 호환을 위해 유지한다.

## 2. 변경 범위

| 영역 | 변경 |
|---|---|
| Library | canonical `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`과 Qwen3.5 route를 검증하는 shared service |
| Script | 자체 client/config 조립을 제거하고 shared service 호출 |
| CLI | `verify qwen`, deployment/provider-proxy scope, text-only, output와 exit code |
| Packaging | `python -m axcalib.cli` module entrypoint |
| Test | fake exact endpoint에서 script/CLI parity, text/vision, secret/reasoning 비보존 |
| Example | EX-14 model deployment operator scenario |
| Wiki | clone/install, PowerShell/Bash 환경변수, capability, 등록심의, Docling, 실패분류와 결과 전달 |

## 3. Interface 계약

### Library

```python
from axcalib.models import probe_qwen35_from_env

report = probe_qwen35_from_env()
```

호출은 세 canonical 환경변수를 모두 명시적으로 요구한다. `OPENAI_MODEL`이 Qwen3.5 route를
식별하지 않으면 network 요청 전에 거부한다.

### CLI exit

| Exit | 의미 |
|---:|---|
| `0` | 선택 scope의 capability와 identity 기준 충족 |
| `1` | secret-free report는 생성됐지만 capability/identity 기준 미충족 |
| `2` | 필수 환경변수 또는 Qwen route 설정 오류 |

`provider_proxy`는 capability를 확인해도 exact deployment readiness를 만들지 않는다.
`--text-only`도 vision을 실행하지 않으므로 deployment readiness가 될 수 없다.

## 4. 코드리뷰

| 확인항목 | 판정 | 근거/남은 범위 |
|---|---|---|
| script/CLI domain 복제 | Pass | 두 adapter가 shared Library service 호출 |
| exact model identity | Pass | requested/response/expected checkpoint explicit match 유지 |
| silent fallback | Pass | dialect/model 자동 교체 없음 |
| secret/raw content | Pass | key는 client에만 전달; report는 endpoint hash와 safe check metadata만 보존 |
| hidden reasoning | Pass | raw response와 `reasoning_content`를 report/CLI에 보존하지 않음 |
| 사람 Gate | Not affected | capability interface는 dossier 상태나 승인결정을 변경하지 않음 |
| 실제 model 품질 | Not verified | exact endpoint, registration/completion과 Owner gold가 필요 |
| 기존 `.venv` packaging | Environment issue | 다수 package가 read-only이고 일부 `RECORD`가 없어 sync 실패; source defect와 분리해 clean venv 검증 |
| clean Rich compatibility | Defect fixed | `Console.print(stderr=True)`가 Rich 15에서 실패해 `typer.echo(err=True)`와 missing-env 회귀 추가 |

## 5. 검증

최종 검증 결과:

```text
targeted model/CLI/docs/Wiki: 22 passed
full split: 192 passed
  unit: 132
  integration: 39 (core 9, eval 24, ops 6)
  contract: 21
offline eval: 10 groups passed
Ruff: passed
Pyright: 0 errors, 0 warnings
workspace validate: 0 errors, 0 warnings
Wiki validate/export: 18 GitHub + 18 GitLab managed files
```

현재 `.venv`의 read-only metadata와 일부 누락된 `RECORD` 때문에 in-place `uv sync`는 실패했다.
이를 소스 결함과 분리해 새 wheel과 clean venv에서 Rich 15 조합의 console/module entrypoint,
help와 canonical env 누락 exit 2를 traceback 없이 확인했다. 첫 clean run에서 발견한
`Console.print(stderr=True)` 비호환도 이 과정에서 수정했다.

실제 SkillBoss나 외부 model은 이번 slice에서 호출하지 않았다. SkillBoss 확인은 on-prem 제품경로가
provider-independent `OPENAI_*`를 유지해야 한다는 routing 판단에만 사용했다.

## 6. 배포 증거

- main implementation commit: `65aeab46af2fe944a15508564a368deb943d1b08`
- GitHub Actions: run `30067692706`, validate/publish 2개 job success, annotation 0
- GitHub Wiki remote: `8e76cd81af967d67e32e9cdb3c5f5deddd680963`
- 공개 페이지: `On-Prem-Qwen-Verification`, HTTP 200과 제목 render 확인

사내 GitLab Wiki는 같은 18-file export contract만 검증했으며 실제 runner/credential/push는
플랫폼 환경에서 확인해야 한다.

## 7. 다음 개발 순서

1. 사내에서 exact `Qwen3.5-397B-A17B` capability JSON과 테스트 PPTX registration report를 만든다.
2. completion template이 승인되면 같은 snapshot/policy로 completion report를 만든다.
3. Evaluation Owner가 rubric, threshold와 hidden adjudicated labels를 제공하면 WP-03.Q2b를 실행한다.
4. 승인 corpus/labels 뒤 WP-04 embedding/Qdrant/rerank와 P6 multi-model calibration을 진행한다.
5. 운영 identity/upload/distributed worker와 Web은 각각의 Owner 결정 뒤 진행한다.

Wiki 사용법은 `wiki/On-Prem-Qwen-Verification.md`, 현재 dependency와 Gate는
`PROJECT_STATE.md`를 기준으로 한다.
