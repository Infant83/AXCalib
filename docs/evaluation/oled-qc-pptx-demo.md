---
document_type: offline_vertical_slice_record
project: AXCalib
updated_at: 2026-07-16
status: verified
---

# 제공 PPTX 등록심의·완료평가 Demo

## 입력과 해석 경계

| 항목 | 값 |
|---|---|
| Source | `tests/sources/oled_qc_project_outline.pptx` |
| SHA-256 | `cb0a21ca59330921855f8e7ce4eb6496c47383750332682160ad48188018bd76` |
| Slide | 16장 |
| OOXML text | 없음 |
| 시각 근거 | 원본 hash에 묶인 수동 검토 sidecar |
| Live model/OCR | 사용하지 않음 |
| Embedding/Vector DB | 사용하지 않음 |
| Retrieval | stage별 synthetic lexical corpus, portion `0.0` |

sidecar는 OCR 정답이나 실제 평가 label이 아니다. 현재 image-only 파일을 외부 endpoint로 보내지
않으면서 workflow 계약을 검증하기 위한 제한된 요약과 tag다. checksum이 다르거나 sidecar가
없으면 시각 의미를 만들어내지 않는다.

## 등록심의 Agent 초안

| Criterion | 결과 | 핵심 이유 |
|---|---|---|
| 문제와 AX 목표 | met | 문제·목표 tag와 slide locator 존재 |
| 범위와 접근방법 | met | scope/method 근거 존재 |
| 로드맵과 검증계획 | met | roadmap/validation plan 근거 존재 |
| 정량 KPI와 측정방법 | partially_met | KPI 계획은 있으나 수치 target·unit·period 없음 |
| 위험과 한계 | met | risk/limitation 근거 존재 |
| 데이터·보안·윤리 | partially_met | 데이터 언급은 있으나 보안·접근·외부전송 정책 없음 |
| 역할과 자원 | insufficient_evidence | 과제 owner·인력·예산·시스템 자원 배정 근거 없음 |

Agent recommendation은 `needs_changes`다. 전체 demo에서는 이 판단을 숨기지 않고,
`admin:local-reviewer`라는 **인증되지 않은 local actor 입력**이 “동일 파일 완료평가 실패 경로를
검증하는 offline demo”라는 제한된 이유로 등록 승인 command를 전달한다. 이 예제는 실제
관리자 인증이나 실제 과제의 등록 승인 근거가 아니다.

## 동일 파일 완료평가 Agent 초안

등록 제안서와 완료 제출 파일의 SHA-256이 동일하다. AXCalib는 이를 수행 결과물로 자동
간주하지 않는다.

| Criterion | 결과 | 핵심 이유 |
|---|---|---|
| 등록 baseline 연결 | met | 등록 report와 snapshot ID를 비교 기준으로 연결 |
| 완료 산출물과 작동 증거 | not_met | 등록안과 완료안 content hash 동일 |
| KPI 관측값과 달성도 | insufficient_evidence | observed value·unit·period·measurement 없음 |
| 수행·재현 증거 | insufficient_evidence | 실행 로그·환경·버전·재실행 절차 없음 |
| 등록안 대비 변경 | insufficient_evidence | 승인된 change 기록 없음 |
| 완료 시점 위험과 후속계획 | met | 제안서에 위험·한계는 있으나 수행결과 증거는 아님 |

Agent recommendation은 `not_accept`다. demo의 인증되지 않은 local actor 입력도 동일 hash와
수행증거 부재를 이유로 `not_accept` command를 전달한다.

## 생성되는 감사 산출물

지정한 `--workspace` 아래에 다음이 생성된다.

~~~text
dossiers/AXC-{project_id}.axc.yaml
snapshots/snap-{project_id}-{revision}-{hash}.json
reports/{project_id}/registration/{report_id}.json|md
reports/{project_id}/completion/{report_id}.json|md
audit/events.jsonl
~~~

두 report는 Agent 제안이고, 관리자 결정은 dossier의 별도 `decision` 객체와 audit event로
보존된다. 두 HITL 진입에는 `registration_admin_approval_requested`와
`completion_admin_approval_requested` recording event가 각각 하나씩 필요하다.

## 검증 명령

~~~powershell
.\prep.ps1 validate
.\prep.ps1 test
.\prep.ps1 eval
uv run --no-sync ruff check src scripts harness evals tests
uv run --no-sync pyright src scripts harness evals tests
~~~

`prep.ps1 eval`의 이 demo 수용기준은 등록 `needs_changes`, 완료 `not_accept`, 동일 hash guard,
두 알림, stage leakage 없음, similarity portion `0.0`, criterion locator 보존이다. 이는 workflow
회귀 품질만 뜻하며 실제 의미평가·검색 품질·인증정책의 적정성을 주장하지 않는다.
