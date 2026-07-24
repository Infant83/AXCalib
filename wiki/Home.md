# AXCalib Wiki

AXCalib는 **AX Certification Agent Library**다. 프로젝트 제안과 수행 증거를 한 기록철인
Dossier에 모으고, 등록심의와 완료평가를 근거 중심으로 지원한다.

> 근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다.

![AXCalib 생태계와 적용 구조](assets/axcalib-ecosystem-infographic.png)

## 무엇을 제공하는가

- Python Library에서 live `Case` 하나로 등록, 현재 상태, 평가초안, 사람 승인 대기, 수행과
  완료평가 요약을 일관되게 확인한다.
- 평가 기준과 참고자료를 version/hash-bound review policy로 주입한다.
- API, Worker, 향후 Web Review App이 같은 application service와 상태 기계를 사용한다.
- 모델은 제안과 근거 요약을 만들지만 최종 승인·반려·완료 수용은 권한 있는 사람이 결정한다.
- 로컬 synthetic 기준선과 실제 운영 품질을 구분해 기록한다.

## 처음 보는 사람의 추천 경로

1. [5분 시작](Getting-Started)으로 가장 작은 실행을 확인한다.
2. [Library 매뉴얼](Library-Manual)에서 Dossier, Case와 공개 인터페이스를 이해한다.
3. [두 Gate 실습](Two-Gate-Tutorial)으로 등록심의부터 완료평가까지 따라간다.
4. [설정과 On-prem](Configuration-and-On-Prem)에서 OpenAI-compatible endpoint 경계를 확인한다.
5. 운영자와 개발자는 [보안과 HITL](Security-and-HITL), [개발 프로세스](Development-Process)를 읽는다.

## 현재 공개 범위

현재 저장소는 readable Case view가 포함된 Library MVP/Alpha, local API/Worker와 signed OIDC/JWKS validation reference를
제공한다. 실제 사내 issuer·remote key rotation/revocation·교육 배정, immutable upload, distributed
broker, 운영 Web App, 실제 사내 rubric·gold·Vector DB 품질은 완료되지 않았다. Wiki의 설명은 운영
인증 완료 선언이 아니라 현재 구현과 검증 경계를 보여 주는 사용 안내다.

상세 진행상태와 append-only 이력은 자동으로 배포되는 [개발 실행 원장](Development-Ledger)에서
확인한다.

## Wiki의 관리 방식

이 Wiki의 단일 원본은 메인 코드 저장소의 `wiki/`다. GitHub와 사내 GitLab Wiki에서 직접
내용을 따로 편집하지 않는다. 변경·검증·배포 방법은 [문서 운영 규칙](Documentation-Governance)을
따른다.
