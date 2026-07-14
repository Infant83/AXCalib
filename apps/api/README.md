# API runtime

향후 `axcalib.api`의 FastAPI factory를 조립하는 얇은 실행 진입점이다. P1에서는 API와
운영 endpoint를 구현하지 않는다.

Route는 HTTP/auth 입력을 typed command로 변환하고 `src/axcalib`의 versioned
pipeline/workflow facade를 직접 호출한다. working Python script를 subprocess로 실행하거나
등록·완료 평가 로직을 이 폴더에 복제하지 않는다.
