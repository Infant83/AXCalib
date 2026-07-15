# Excalibur 비유로 이해하는 AXCalib

## 먼저 기억할 문장

> 근거가 자격을 만들고, 보정이 판단을 맞추며, 권한 있는 사람이 인증한다.

AXCalib의 `Calib`는 Certification + Agent + Library와 Calibration을 함께 떠올리게 한다.
Excalibur는 이를 기억하기 위한 시각적 비유다. **공식 어원이나 상표 선언이 아니며, Agent가
사람 대신 인증한다는 뜻도 아니다.**

![권한 중심 철학](assets/axcalib-authority-hero.jpg)

## 그림 읽기

1. 왼쪽의 증거 조각은 dossier로 수집된다.
2. 승인된 rubric과 calibration이 비교 기준과 편차를 정렬한다.
3. Agent는 인용 가능한 근거와 불확실성을 포함한 **제안 리포트**를 만든다.
4. 알림이 전달되고 관리자 HITL이 checklist를 수행한다.
5. 권한 있는 사람만 승인·반려 또는 수용·미수용을 확정한다.
6. snapshot, notification, 사람 결정은 서로 구분된 감사기록으로 남는다.

정확한 계약은 [권한 구조도](diagrams/authority-model.svg)에서 확인한다.

## 절대 넘지 않는 선

- Agent의 `pass`는 제안이지 최종 상태가 아니다.
- 근거가 없으면 유추하지 않고 `insufficient_evidence`로 남긴다.
- 과거 사례 유사도는 일관성 점검 자료이지 인증 정답이 아니다.
- 등록과 완료의 HITL 알림이 기록되지 않으면 다음 상태로 전이하지 않는다.
- 관리자만 하는 결정을 TOML이나 API 옵션으로 끌 수 없다.
