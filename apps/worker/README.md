# Worker runtime

향후 evaluation, retrieval, notification outbox를 bounded batch로 실행한다. P1에서는 외부
queue나 실제 알림을 사용하지 않는다.

Worker는 API와 같은 pipeline/workflow registry를 사용해 checkpoint에서 재개한다. task 함수에
domain 상태전이와 평가 규칙을 별도로 구현하지 않는다.
