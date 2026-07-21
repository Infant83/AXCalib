# Synthetic education project lifecycle fixture

이 폴더는 실제 제공 PPTX를 등록심의 제안서로 참조하고, 별도로 생성한 synthetic 완료보고서를
사용해 교육 프로그램 → 마일스톤 → 프로젝트 dossier → 관리자 HITL → 과정 완료 확인을
검증한다.

- `program.yaml`: 과정 기획자가 만든 versioned program blueprint
- `completion_report.synthetic.pptx`: 실제 수행결과가 아닌 테스트 전용 완료자료
- `completion_report.synthetic.axcalib.json`: 완료자료 SHA-256에 고정된 검토 sidecar

이 fixture의 점수, 마일스톤, 기준은 공식 정책이나 실제 학습자 평가를 뜻하지 않는다.
