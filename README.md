# AXCalib

**AX Certification Agent Library**

AXCalib는 하나의 과제 dossier에 등록심의, 수행기록, 멘토링, 산출물, KPI, 완료평가를 연결하고, 평가기준·과거 유사사례·다중 모델 분석을 근거로 사람의 AX 인증 판단을 지원하는 Library다.

> Calibrate Assessment. Certify AX.

## 현재 상태

현재는 **P0 기획 초안 작성 완료, 관계자 승인 및 executable harness 구현 전** 단계다.

- Python package와 CLI/API는 아직 없다.
- prep.ps1 명령은 계약만 정의되어 있고 아직 실행되지 않는다.
- 실제 사내 데이터와 live model은 사용하지 않았다.
- 이 폴더는 상위 Git 저장소에서 아직 추적되지 않은 상태다.

## 기준 문서

| 문서 | 역할 |
|---|---|
| [AXCalib_Concept_Overview.md](AXCalib_Concept_Overview.md) | 이름의 의미와 장기 제품개념 |
| [WORK_SPEC.md](WORK_SPEC.md) | 제품·기능·비기능·데이터 요구사항 |
| [GOAL.md](GOAL.md) | 첫 Target, 기술선택, 단계별 Gate와 수용기준 |
| [DESIGN.md](DESIGN.md) | dossier, pipeline, Vector DB, model, backend/frontend, LG UI 설계 |
| [AGENTS.md](AGENTS.md) | 사람과 coding Agent가 지킬 작업계약 |

## 핵심 결정

- **Library first**: Core Library → CLI/Evaluation Harness → API/Batch → Web App 순서
- **Two gates**: 등록심의와 완료평가를 분리
- **One dossier**: project_id별 AXC-{uuid}.axc.yaml 한 파일을 지속 갱신
- **Immutable evaluation**: 평가 요청 시 revision과 SHA-256 snapshot을 고정
- **Evidence first**: criterion별 원문 locator 또는 판단불가 기록
- **Historical comparison**: stage-aware embedding, hybrid retrieval, rerank
- **On-prem first**: Qwen3.5 logical default, BASE_URL/API_KEY/model은 설정 주입
- **Calibrated panel**: 여러 model의 평균보다 criterion별 편차와 근거차이를 노출
- **Human accountable**: Agent가 최종 합격·인증 상태를 직접 확정하지 않음
- **LG-based Web UI**: 공식 색상 token을 사용하되 logo/font 자산은 권한 확인 후 적용

## 첫 구현 Target

실제 데이터와 network 없이 synthetic dossier로 다음 흐름을 관통한다.

~~~text
dossier 생성
→ 등록심의 snapshot/평가초안/사람 승인
→ 수행·멘토링·KPI 갱신
→ 완료평가 snapshot/등록 baseline 비교/사람 판정
→ Markdown·JSON report
~~~

세부 수용기준은 GOAL.md의 **Target T1**을 따른다.

## 다음 단계

1. Product Owner와 Evaluation Owner가 GOAL.md의 Target 및 제안 지표를 승인한다.
2. P1에서 pyproject.toml, src/axcalib, prep.ps1, PROJECT_STATE를 구축한다.
3. P2에서 dossier schema/state/snapshot과 paired synthetic fixture를 구현한다.
4. P3 이후 Docling, Qdrant, Qwen3.5 endpoint를 각각 독립 spike하고 evaluation한다.

Git 초기화, 실제 데이터 반입, live model 대량 호출, 배포는 별도 승인 전 진행하지 않는다.
