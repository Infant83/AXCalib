# Web review app

Frontend stack과 주 디자인은 아직 선택되지 않았다. 현재 권장안은 React + Vite + React
Router Data Mode와 Enterprise Evidence Cockpit이지만 사용자 선택 전에는 scaffold하지 않는다.

Web App은 API가 제공하는 workflow run, 현재 node, wait reason, checklist와 allowed command를
표시한다. 브라우저에서 다음 상태나 최종 승인 여부를 계산하지 않는다.

Onboarding은 [사용 안내서](../../docs/manuals/README.md)의 사람 권한 서사를 사용하되,
실제 review 화면은 비유보다 evidence locator, rubric, revision, notification과 allowed command를
우선한다.
