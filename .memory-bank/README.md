# AXCalib Memory Bank

이 폴더는 다음 작업자가 빠르게 문맥을 복구하기 위한 **읽기용 요약 캐시**다. 진행상태를 여기서
독립적으로 관리하지 않는다. 정보가 다르면 아래 기준정보를 우선한다.

1. 최신 사용자 지시와 `AGENTS.md`
2. `WORK_SPEC.md`, `GOAL.md`, `DESIGN.md`
3. `PROJECT_STATE.md`의 현재 상태와 append-only history
4. `DECISIONS.md`, `RISK_REGISTER.md`, `CHANGELOG.md`
5. 코드, 테스트와 evaluation 결과

## Resume card - 2026-07-23

- 제품: AXCalib, AX Certification Agent Library
- 핵심 경계: Agent는 심의 초안을 만들고 승인된 사람이 최종 결정한다.
- 현재 위치: P7 / WP-06.I3 completed local Alpha / G4 Interfaces
- 완료 checkpoint: R1.2 + WP-06.I1 runtime API + WP-06.I2a/I2b/I2c resource API/read-replay + I3 local Worker
- 다음 dependency: WP-06.I4 approved OIDC/assignment/immutable upload boundary `blocked_policy`
- 문서 전달: WP-00.D2 portable `wiki/` source, PROJECT_STATE mirror와 GitHub/GitLab export contract;
  GitHub Wiki live render와 Node.js 24 automatic publish/annotation 0 완료, 사내 GitLab은 대기
- 최근 증거: 136 lightweight tests(unit 86/integration 31/contract 19), 10 eval groups,
  Wiki targeted 6/6와 parity 1/1, Ruff check, Pyright 0/0, validation 0/0; 직전 Worker API 27/27
- 최근 해결: SkillBoss proxy의 `json_object` HTTP 500 원인을 JSON keyword/schema contract로 복구
- 최근 구현: project/education recovery, pipeline checkpoint/result hash/cancel, JSONL batch,
  non-destructive maintenance, Alpha CLI, fail-closed runtime API, principal-bound project register/HITL,
  education enrollment/milestone/completion, project safe GET/decision replay, queued 202/local job lease/retry/
  terminal replay Worker, portable dual-Wiki harness와 clean-wheel actual-PPTX quickstart
- 중단 원인: Windows `os.kill(pid, 0)` self-termination; read-only Win32 query로 해결. Docling은 별도
  `prep.ps1 docling` contract로 분리
- 모델 경계: Qwen3.5 Plus/GPT-4o provider proxy만 확인; exact `Qwen3.5-397B-A17B`는 미검증
- 데이터 경계: synthetic 또는 승인된 비식별 fixture만 사용
- API 경계: injected verifier/grant; project/education command는 principal·resource scope·org·revision,
  staged/program hash에 bind하고 project GET은 URI/free-text redacted. queued grant의 202/local Worker는
  구현됐지만 OIDC/JWKS·실제 교육 배정, immutable upload와 distributed queue/heartbeat는 미구현
- 다음 읽기: `../PROJECT_STATE.md` → `../docs/evaluation/wp06-i3-durable-local-worker-report.md` →
  `../docs/evaluation/wp00-d2-portable-wiki-harness-report.md` → `../docs/HANDOFF.md` → `../CHANGELOG.md`

## 재개 체크리스트

```powershell
git status -sb
.\prep.ps1 status
.\prep.ps1 next
.\prep.ps1 validate
```

- working tree의 사용자 변경을 먼저 확인한다.
- `PROJECT_STATE.md`의 Active Slice와 Exit Evidence를 한 문장으로 고정한다.
- external model, actual data, deployment, commit/push가 필요한지 승인 범위를 확인한다.
- 가장 작은 offline end-to-end slice부터 구현한다.
- 단계 종료 시 `PROJECT_STATE.md`, `CHANGELOG.md`와 필요한 diagram/module board를 갱신한다.
- 공개 API·workflow·설정·구조가 바뀌면 관련 `../wiki/` page와 dual-target parity를 함께 갱신한다.

## 작업 기록 위치

- 실행 일정·검증·특이사항·append-only 이력: `../PROJECT_STATE.md`
- 사용자 관점 변경 요약: `../CHANGELOG.md`
- 쉬운 인수인계: `../docs/HANDOFF.md`
- 기술 결정: `../DECISIONS.md`, `../docs/adr/`
- 열린 위험: `../RISK_REGISTER.md`
- 단계별 개발리포트: `../docs/evaluation/`
- 사용자 Wiki 단일 원본과 배포 runbook: `../wiki/`, `../docs/operations/wiki-publication.md`

이 파일에는 API key, 개인정보, 원문, model reasoning 또는 ignored `output/` 내용을 복사하지 않는다.
