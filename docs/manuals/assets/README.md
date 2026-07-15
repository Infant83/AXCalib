# AXCalib manual visual assets

| 파일 | 용도 | 생성 기준 |
|---|---|---|
| `axcalib-authority-hero.jpg` | 제품 철학 hero와 concept manual | text-free Excalibur 기억 장치, 사람만 승인 장치 사용 |
| `axcalib-six-panel-tutorial.jpg` | 등록~완료 6컷 교육자료 | 3×2 panel, Agent는 사람 Gate에서 대기 |

## 생성 기록

- 날짜: 2026-07-15
- 도구/model: imagegen CLI, `gpt-image-1.5`
- 원본: 1536×1024 PNG, `quality=high`
- 문서용: 최대 1440 px, JPEG quality 88
- taxonomy: `illustration-story`
- 공통 제약: 문자·logo·watermark 없음, AI 단독 승인 없음, 공식 LG 자산 없음
- 데이터: synthetic concept only; 실제 과제 자료나 AXCalib live model endpoint 사용 없음

긴 문구와 정확한 역할명은 생성 이미지에 넣지 않고 Markdown caption과
`../diagrams/authority-model.svg`에서 관리한다. 이미지가 caption과 충돌하면 문서와 SVG가
기준이다.
