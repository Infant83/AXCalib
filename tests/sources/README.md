# Supplied PPTX test source

`oled_qc_project_outline.pptx`는 사용자가 제공한 local workflow test 입력이다. 외부 endpoint로
전송하지 않으며 파일 자체를 테스트에서 수정하지 않는다.

이 deck은 표준 OOXML text node가 없는 image-only 형식이다. 따라서
`oled_qc_project_outline.axcalib.json`은 원본 SHA-256에 고정된 검토 sidecar다. sidecar는
시각 의미를 전부 재현하는 OCR 결과가 아니라 offline pipeline을 검증하기 위한 제한된
요약·tag이며, checksum이 다르면 parser가 거부한다.
