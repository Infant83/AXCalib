# Schema exports

- [runtime-config.schema.json](runtime-config.schema.json): default/expert TOML의 허용 구조와 범위
- dossier JSON Schema: WP-01에서 Pydantic model과 Draft 2020-12 export를 추가할 예정

runtime schema는 pre-implementation 계약이다. 실제 runtime loader와 schema parity test가
WP-01에서 통과하기 전에는 config 기능이 구현됐다고 표시하지 않는다.
