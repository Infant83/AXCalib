# Schema exports

- [runtime-config.schema.json](runtime-config.schema.json): default/expert TOML의 허용 구조와 범위
- [axcalib.dossier.v1alpha2.schema.json](axcalib.dossier.v1alpha2.schema.json): canonical project dossier
- [axcalib.education-program.v1alpha1.schema.json](axcalib.education-program.v1alpha1.schema.json):
  immutable education program
- [axcalib.education-enrollment.v1alpha1.schema.json](axcalib.education-enrollment.v1alpha1.schema.json):
  revisioned learner enrollment
- [axcalib.case-status.v1alpha1.schema.json](axcalib.case-status.v1alpha1.schema.json):
  현재 단계와 다음 action read projection
- [axcalib.case-summary.v1alpha1.schema.json](axcalib.case-summary.v1alpha1.schema.json):
  등록·수행·완료와 사람 결정을 연결한 lifecycle projection
- [axcalib.gold-benchmark-manifest.v1alpha1.schema.json](axcalib.gold-benchmark-manifest.v1alpha1.schema.json):
  rubric, gold labels, Owner 승인, evaluation split과 threshold의 hash-bound manifest
- [axcalib.gold-case-label.v1alpha1.schema.json](axcalib.gold-case-label.v1alpha1.schema.json):
  project-stage별 criterion 정답과 evidence locator
- [axcalib.evaluation-owner-approval.v1alpha1.schema.json](axcalib.evaluation-owner-approval.v1alpha1.schema.json):
  사람이 읽는 승인 Markdown frontmatter 계약
- [axcalib.gold-benchmark-report.v1alpha1.schema.json](axcalib.gold-benchmark-report.v1alpha1.schema.json):
  고정 test split의 agreement, locator와 위험한 긍정 제안 품질지표

모든 generated artifact는 Pydantic model과 Draft 2020-12로 export하며 `prep validate`가 drift를
검사한다. Case schema는 local Library projection 계약이고 remote API authorization/redaction
계약을 대신하지 않는다.
