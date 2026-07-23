# AXCalib 인수인계 안내

이 문서는 AXCalib를 처음 이어받는 사람이 **무엇을 만드는지, 지금 어디까지 됐는지, 다음에 무엇을
해야 하는지** 짧은 시간 안에 이해하도록 돕는다. 상세 진행상태는 `PROJECT_STATE.md`가 유일한 실행
기준정보다.

## 1. AXCalib를 한 문장으로 설명하면

AXCalib는 제출된 프로젝트의 근거를 모아 등록심의와 완료평가 초안을 만들고, 판단 편차를 점검한 뒤
**권한 있는 관리자가 최종 승인하도록 돕는 Python 라이브러리**다.

Agent가 사람 대신 인증하지 않는다. AXCalib의 역할은 다음 세 문장으로 기억하면 된다.

> 근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다.

## 2. 쉬운 용어 설명

| 용어 | 쉬운 뜻 |
|---|---|
| dossier | 한 프로젝트의 목표, 증거, 심의와 승인 기록을 모은 기록철 |
| snapshot | 평가 도중 내용이 바뀌지 않도록 특정 revision을 복사해 고정한 파일 |
| 등록심의 | 프로젝트를 시작해도 되는지 검토하는 첫 번째 Gate |
| 완료평가 | 처음 승인한 목표와 실제 결과를 비교하는 두 번째 Gate |
| HITL | Agent 초안을 사람이 확인하고 최종 결정을 내리는 절차 |
| P / WP / G | Phase는 큰 개발 구간, Work Package는 납품 단위, Gate는 통과 확인점 |
| provider proxy | 실제 배포 모델과 같다고 보장하지 않는 개인환경의 모델 연결 경로 |
| transaction journal | 여러 파일을 바꾸는 작업의 준비·적용·완료 상태를 남기는 복구 기록 |
| reconciliation | 중단 뒤 관련 파일을 다시 대조해 빠진 기록이나 불일치를 안전하게 복구하는 절차 |
| API pipeline grant | Library에 등록된 pipeline 중 HTTP로 공개해도 된 exact ID/version만 다시 허용하는 목록 |
| queued execution | HTTP 요청 안에서 바로 실행하지 않고 검증된 명령을 job으로 기록해 Worker가 처리하는 방식 |
| queue status | pipeline 결과와 별도로 job이 대기·claim·완료·소진·차단 중인지 보여주는 상태 |
| portable Wiki | main `wiki/` 한 곳에서 작성해 GitHub/GitLab Wiki에 같은 내용으로 배포하는 문서 방식 |

## 3. 2026-07-23 Library/API/Worker + Portable Wiki local checkpoint

- 현재 Phase: P7 Interfaces
- 완료 checkpoint: WP-01.R1.2 + WP-06.I1 + WP-06.I2a/I2b/I2c resource API/read-replay + WP-06.I3 local Worker
- 다음 dependency: WP-06.I4 approved OIDC/assignment/immutable upload boundary (`blocked_policy`)
- 현재 Gate: G4 Interfaces (`in_progress`; CLI/batch/resource API/local Worker contract evidence 확보)
- 최근 전체 검증 수치는 `PROJECT_STATE.md` 7절을 기준으로 확인한다.
- 문서 checkpoint: WP-00.D2 GitHub Wiki live publication, GitLab portable export contract

현재 가능한 것:

- 제공 PPTX를 dossier로 등록하고 revision을 고정한다.
- 등록심의 초안, 관리자 알림, 사람의 승인·반려를 분리해 기록한다.
- 수행 증거를 갱신하고 완료평가 초안과 두 번째 HITL을 진행한다.
- 교육 프로그램에 가입한 학습자의 milestone과 프로젝트 완료 근거를 연결한다.
- Qwen3.5 Plus 또는 다른 OpenAI-compatible 모델의 text/vision 계약을 별도로 probe한다.
- project dossier/audit 저장 중 중단되면 journal을 대조해 중복 없이 복구한다.
- education enrollment/audit 저장 중 중단돼도 별도 journal로 복구한다.
- pipeline run을 checkpoint/replay/cancel하고 strict JSONL batch의 item별 상태를 보존한다.
- Alpha CLI로 allowlisted pipeline list/run/status/cancel, batch와 maintenance를 호출한다.
- stale lock/orphan은 report-only로 확인하고 명시적 apply에서도 quarantine/archive한다.
- clean wheel에서 설치된 CLI와 actual-PPTX 등록심의 `waiting_human` quickstart가 동작한다.
- optional FastAPI에서 bearer verifier와 exact delivery grant를 주입해 같은 registry의
  catalog/run/status/cancel을 호출한다. 기본 verifier와 grant는 닫혀 있다.
- owner/admin은 local path가 아닌 staged artifact ID와 hash로 project를 등록하며, 관리자는
  role·scope·organization·revision이 모두 맞을 때만 두 HITL 결정을 기록할 수 있다. actor는 request가
  아니라 verified principal에서 온다.
- owner/admin은 scope·organization과 owner creation audit를 통과한 project current state를 local URI,
  progress note, mentor identity나 decision rationale 없이 조회한다. 같은 decision key/request는 결과를
  replay하고 다른 actor/resource/payload 재사용은 409로 거부한다.
- learner는 exact program hash로 self enrollment하고, mentor/instructor/admin은 enrollment/program별
  배정 scope와 organization이 맞을 때만 확인·점수·project sync·과정 완료결정을 기록할 수 있다.
  교육 request에도 actor/learner/org field가 없다.
- exact pipeline grant를 `queued`로 지정하면 API가 domain pipeline을 inline 실행하지 않고 202와 stable
  run reference를 반환한다. local Worker는 한 번에 한 job을 claim해 같은 executor로 실행하며 restart,
  retryable-only bounded retry, pre-start cancel과 terminal replay를 보존한다.
- main `wiki/`에서 사용자 매뉴얼·실습·설정·아키텍처·개발 프로세스를 관리하고 GitHub/GitLab 형식으로
  동일 export한다. `PROJECT_STATE.md`는 Wiki Development Ledger로 자동 mirror된다.

현재 운영에 쓰면 안 되는 것:

- Agent의 판정을 자동 인증으로 사용하는 것
- 실제 개인정보나 사내 원문을 승인되지 않은 외부 endpoint로 보내는 것
- provider proxy 결과를 exact on-prem Qwen 검증으로 표시하는 것
- 현재 recording outbox를 실제 GitLab/email 운영 알림으로 간주하는 것
- 공식 rubric과 사람 gold label 없이 모델 품질을 검증 완료로 선언하는 것
- local filesystem lease를 database/distributed worker 보장으로 간주하는 것
- cooperative cancel을 이미 commit된 domain mutation의 rollback으로 간주하는 것
- generic API에서 actor/admin decision을 전달하거나 local Alpha를 운영 OIDC/RBAC/upload/server로 간주하는 것
- GitHub Wiki 성공을 사내 GitLab runner·credential·publication 성공으로 확대 해석하는 것

## 4. 가장 먼저 읽을 문서

1. `README.md`: 설치, 실행 예제와 전체 문서 지도
2. `PROJECT_STATE.md`: 현재 P/WP/G, Active Slice, 검증과 작업 이력
3. `CHANGELOG.md`: 사용자 관점의 주요 변경
4. `AGENTS.md`: 변경할 때 반드시 지킬 안전·품질 계약
5. `WORK_SPEC.md`, `GOAL.md`, `DESIGN.md`: 요구사항, 수용기준과 기술 설계
6. `DECISIONS.md`, `RISK_REGISTER.md`: 이미 내린 결정과 아직 열린 위험
7. `wiki/Home.md`, `docs/operations/wiki-publication.md`: 사용자 Wiki 원본과 두 플랫폼 배포 절차

## 5. 로컬에서 상태 확인하기

```powershell
.\prep.ps1 status
.\prep.ps1 next
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 test unit
.\prep.ps1 test integration
.\prep.ps1 test contract
.\prep.ps1 eval
.\prep.ps1 docling
uv run --no-sync python scripts/wiki/sync_wiki.py validate
uv run --no-sync python tests/wiki_ci_contract.py
```

기본 test/eval은 외부 모델을 호출하지 않는다. optional Docling contract도 저메모리 안전을 위해
`prep.ps1 docling`으로 분리했다. test는 세 process group으로 나뉘므로 중단되면 해당 group만 다시
실행한다. live model은 별도 opt-in이며 승인된 비식별 자료만 사용한다.

## 6. 다음 작업을 시작하는 방법

WP-01.R1.2, Alpha CLI, WP-06.I1 runtime과 WP-06.I2a/I2b/I2c project·education resource/read/replay는
완료됐고 WP-06.I3 local 202 Worker도 완료됐다. 다음 G4 dependency는 운영 identity와 artifact trust
boundary다.

1. Product/Security Owner가 OIDC issuer/claim mapping, organization·assignment source와 revocation 책임을
   승인한다.
2. upload/staging owner가 immutable object version, ACL, malware scan, media/size/hash와 retention을 확정한다.
3. 승인 전에는 실제 계정·업로드·운영 server를 만들지 않고 port/schema/threat-model만 검토한다.
4. distributed worker가 필요하면 broker/database, heartbeat, dead-letter, metrics와 payload encryption/
   retention을 ADR로 분리한다.
5. 승인된 dependency 뒤에만 socket E2E와 penetration/load test를 Gate evidence로 추가한다.

Library 중단 원인과 Alpha 리뷰는
[`wp01-r1-2-library-mvp-alpha-report.md`](evaluation/wp01-r1-2-library-mvp-alpha-report.md), API 권한
리뷰는 [`wp06-i1-minimal-api-parity-report.md`](evaluation/wp06-i1-minimal-api-parity-report.md), project
권한 리뷰는
[`wp06-i2a-principal-bound-project-api-report.md`](evaluation/wp06-i2a-principal-bound-project-api-report.md)에
있고, education 권한 리뷰는
[`wp06-i2b-principal-bound-education-api-report.md`](evaluation/wp06-i2b-principal-bound-education-api-report.md)에
있으며, project read/replay 리뷰는
[`wp06-i2c-project-read-decision-replay-report.md`](evaluation/wp06-i2c-project-read-decision-replay-report.md)에
있고, local Worker 리뷰는
[`wp06-i3-durable-local-worker-report.md`](evaluation/wp06-i3-durable-local-worker-report.md)에 있다.

## 7. 인수인계할 때 남길 내용

- 어떤 WP와 수용기준을 바꿨는가
- 실제로 바꾼 파일은 무엇인가
- 실행한 validate/test/eval과 결과는 무엇인가
- 실패했거나 실행하지 못한 검증은 무엇인가
- 품질 주장을 어디까지 할 수 있는가
- 새 결정·위험과 다음 작업은 무엇인가
- commit과 push가 완료됐는가

비밀정보, 원문 전체, model reasoning과 `output/` 실행 산출물은 Git에 넣지 않는다.
