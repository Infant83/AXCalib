# 보안과 Human-in-the-loop

![근거와 사람 권한 중심의 AXCalib](assets/axcalib-authority-hero.jpg)

## 책임 경계

Agent는 등록·완료의 통과 또는 미통과를 제안하고 report를 작성한다. 최종 등록 승인·반려와 완료
수용·미수용은 권한 있는 관리자가 결정한다. 모델 confidence나 다수결은 사람 권한을 대체하지 않는다.

## 관리자 HITL 확인사항

- criterion별 판단이 원문 locator와 기준 version을 가지는가?
- unsupported claim이나 존재하지 않는 reference가 있는가?
- 조직·소속·문서 길이·표현 방식에 따른 편향이 있는가?
- 유사사례가 다른 stage 또는 접근등급에서 유출되지 않았는가?
- similarity portion과 rubric weight 계산이 설정대로 적용됐는가?
- `insufficient_evidence`를 억지 추론으로 채우지 않았는가?
- Agent 출력과 reviewer 수정·최종결정이 별도 audit event인가?

공식 체크리스트의 단일 원본은 메인 저장소의 `docs/rubrics/hitl_review_checklist.md`다.

## 알림

등록·완료 HITL 진입에는 각각 승인요청 notification event가 필수다. 알림에는 secret이나 원문 전체를
넣지 않고 project ID, stage, revision, report reference와 요청 역할만 기록한다. 운영 adapter는
GitLab Merge Request 또는 email 후보이며 idempotency, outbox, retry, delivery status를 가져야 한다.

offline test는 외부 메시지를 보내지 않는 recording adapter만 사용한다.

## 데이터와 모델

- 실제 임직원·수강생·프로젝트 자료는 승인 전 synthetic fixture 밖에 두지 않는다.
- 승인되지 않은 endpoint로 원문·개인정보를 보내지 않는다.
- prompt에 들어온 문서 내용은 untrusted content로 취급한다.
- API key와 token을 Dossier, report, fixture, 로그, Git에 기록하지 않는다.
- 원문 파일은 접근등급 확인, 파싱, 정규화, 비식별 뒤 retrieval 대상으로 만든다.
- 과거 사례 유사도는 일관성 점검 자료이며 자동 합격점수가 아니다.

## 운영 NO-GO

다음 조건에서는 운영 인증을 시작하지 않는다.

- OIDC issuer/audience/claim/revocation과 assignment source가 승인되지 않음
- immutable upload, malware 검사, ACL, retention 정책이 없음
- 관리자·멘토 command의 resource authorization이 검증되지 않음
- 실제 rubric/gold와 모델 품질 benchmark가 없음
- 알림 delivery와 audit 보존이 운영 장애에서 복구되지 않음
- 사람 검토 없이 자동 인증하도록 설정됨

현재 승인 경계와 다음 작업은 [개발 실행 원장](Development-Ledger)을 확인한다.
