# AXCalib 시각자료

이 폴더는 AXCalib 기획 baseline을 이해관계자와 검토하기 위한 최종 발표자료를 보관한다.
제품 요구사항이나 구현상태가 충돌할 때는 `WORK_SPEC.md`, `GOAL.md`, `DESIGN.md`, 실제 코드와
검증 결과가 이 발표자료보다 우선한다.

## 발표자료

- [AXCalib_Workflow_Architecture_v0.3-p1.pptx](AXCalib_Workflow_Architecture_v0.3-p1.pptx)
  - 16:9, 12 slides
  - 두 Gate, 관리자 HITL, 단일 dossier, composable local pipeline, 임베딩 없는 초기 RAG 전략,
    M00~M13 module control board, Delivery Wave와 다음 `dossier.freeze/v1alpha1` slice를 설명한다.
  - 핵심 도형과 텍스트는 PowerPoint에서 편집할 수 있다.

## 표현 경계

- 현재 상태는 P1 offline reference와 G1 검토 대기이며 제품 기능 완료로 표현하지 않는다.
- 실제 사내 데이터, live model 결과, Vector DB 품질수치, 운영 알림 결과를 포함하지 않는다.
- 공식 LG 로고·브랜드 폰트를 사용하거나 공식 브랜드 적합성을 주장하지 않는다.
- similarity는 참고자료이며 자동 통과·탈락 근거가 아니라는 불변조건을 유지한다.

## 유지 규칙

- workflow, module 상태, Wave 또는 다음 slice가 바뀌면 관련 architecture 문서와 발표자료를 함께
  검토한다.
- 발표자료가 세부 기준 문서와 충돌하면 발표자료를 수정하고 기준 문서를 덮어쓰지 않는다.
- 배포 전 `prep.ps1 validate`로 파일 존재, 링크와 12-slide package를 확인한다.

