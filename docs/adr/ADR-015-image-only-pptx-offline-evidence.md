# ADR-015: Image-only PPTX의 hash-bound reviewed sidecar

- Status: Accepted for local/offline slice
- Date: 2026-07-16
- Scope: `two-gate-pptx@v1alpha1`

## Context

제공된 test PPTX 16장은 표준 OOXML text node가 없고 13장이 full-slide image다. 현재 workspace에는
승인된 OCR/VLM/model endpoint가 없으며 원문을 외부로 전송할 권한도 없다. 그림 내용을
텍스트로 읽은 것처럼 가장하면 criterion 근거와 평가 결과가 재현되지 않는다.

동시에 사용자는 현재 파일로 등록심의와 동일 파일 완료평가까지 실행되는 workflow를 요청했다.

## Decision

1. PPTX package는 dependency-light OOXML parser로 안전 한도, macro, slide와 image/text 존재를
   검사한다.
2. image-only slide 의미는 원본 `source_sha256`과 정확히 일치하는 reviewed sidecar가 있을 때만
   사용한다.
3. sidecar summary에서 의미 tag를 재추론하지 않고 명시적으로 검토된 tag만 사용한다.
4. sidecar가 없거나 checksum이 다르면 시각 내용을 만들지 않고 근거 부족으로 처리한다.
5. report의 locator는 원본 PPTX `#slide=N`과 `verified_sidecar` source를 기록한다.
6. proposal과 final hash가 같으면 완료 산출물 criterion을 `not_met`로 제안한다.
7. 어느 Agent recommendation도 관리자 final decision을 대체하지 않는다.
8. local demo decision actor는 인증되지 않았음을 `offline_unverified_actor`로 기록한다.

## Consequences

- network, GPU, model 없이 두 Gate와 evidence locator를 재현할 수 있다.
- sidecar 작성자의 편향이 남으므로 실제 parser/model 품질을 주장할 수 없다.
- 실제 template이 오면 OOXML field mapping fixture를 먼저 만들고, 필요할 때만 Docling,
  slide renderer, OCR/VLM adapter를 별도 contract/eval 뒤에 추가한다.
- sidecar는 운영 데이터의 장기 표준이 아니라 첫 offline 회귀 fixture다.

## Verification

- `tests/unit/test_pptx_ingest.py`
- `tests/integration/test_pptx_two_gate_pipeline.py`
- `evals/pptx_vertical_slice.py`
- `docs/evaluation/oled-qc-pptx-demo.md`
