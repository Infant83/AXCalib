---
title: AXCalib Product Brief
status: predevelopment_candidate
baseline: v0.3-p1
updated_at: 2026-07-15
---

# AXCalib 제품 브리프

## 한 문장

**근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다.**

> Evidence qualifies. Calibration aligns. Authorized humans certify.

AXCalib는 과제 증거를 구조화하고 두 단계 평가를 일관되게 보정하여, 권한 있는 사람이
추적 가능한 근거로 AX 인증 결정을 내리도록 돕는 **AX Certification Agent Library**다.

## Excalibur 기억 장치

Excalibur의 “아무나 뽑을 수 없는 칼” 이미지는 제품을 쉽게 기억하기 위한 비유다. 공식 어원,
제품명 변경 또는 자동 인증 알고리즘을 뜻하지 않는다.

| 비유 | AXCalib에서의 의미 | 책임 주체 |
|---|---|---|
| 돌에 고정된 칼 | 승인된 rubric과 인증 정책으로 보호된 인증 권한 | 조직/정책 책임자 |
| 흩어진 조각 | dossier에 들어오는 과제 증거 | 과제 수행자 |
| 정렬 고리 | 기준·모델·평가자 편차를 다루는 calibration | Library와 평가자 |
| 칼을 건네는 조력자 | 근거를 모으고 제안 리포트를 만드는 Agent | Agent |
| 칼을 뽑는 사람 | 관리자 HITL을 거쳐 결정을 확정하는 권한자 | 승인된 사람 |
| 칼집의 기록 | snapshot, report, notification, decision audit | 시스템 |

Agent는 칼을 뽑지 않는다. Agent는 **근거를 정렬하고, 불확실성을 표시하고, 사람이 결정할 수
있는 상태를 만든다.**

![AXCalib 권한 모델 일러스트](../manuals/assets/axcalib-authority-hero.jpg)

## 사용자 약속

- 5분 안에 synthetic dossier로 첫 평가 제안을 실행한다.
- 근거가 없으면 채우지 않고 `insufficient_evidence`로 보인다.
- 결과마다 criterion, source locator, rubric version, snapshot을 따라갈 수 있다.
- 등록심의와 완료평가 모두 Agent 제안 뒤 관리자 HITL을 거친다.
- 기본 설정은 안전하고 작다. 전문 설정은 profile로 단계적으로 연다.
- Library, CLI, API, worker, Web App에서 같은 상태와 결과 의미를 유지한다.

## 점진적 사용 경험

| 층 | 대상 | 인터페이스 | 노출 범위 |
|---|---|---|---|
| 0. 기본 | 처음 쓰는 개발자 | `AXCalib().evaluate(...)` | stage와 dossier만 |
| 1. 업무 | 평가 운영자 | CLI/Web command | 허용된 상태 전이와 HITL checklist |
| 2. 전문 | 플랫폼 엔지니어 | TOML profile | model/retrieval/storage/notification adapter |
| 3. 통합 | 시스템 개발자 | OpenAPI JSON | allowlist된 per-request options와 idempotency |
| 보호층 | 모든 사용자 | 코드 소유 invariant | 사람 최종결정, 알림, stale/mentor guard는 변경 불가 |

## MVP 범위

MVP는 단일 dossier, revision freeze, 등록·완료 두 Gate, criterion별 근거, stage별 retrieval,
평가 제안 리포트, 필수 notification, 사람 wait/resume, optional mentor guard와 감사기록을
library-first 방식으로 제공한다.

다음은 MVP 완료 주장이 아니다.

- Agent 단독 인증 또는 자동 AX Level 확정
- 실제 사내 데이터 품질 검증
- 운영 Vector DB·메일·GitLab delivery
- 특정 프론트엔드나 모델 공급자 종속
- fine-tuning을 전제로 한 설치

## 개발 진입 조건

사용자의 2026-07-16 지시 범위에서 제공 PPTX local/offline slice는 구현됐다.
`docs/readiness/development-readiness-audit.md`의 남은 조건과 Product/Evaluation Owner의 공식
승인 전에는 live model, 실제 데이터, 운영 알림 또는 Web 구현으로 범위를 확장하지 않는다.
