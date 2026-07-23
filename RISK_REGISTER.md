# AXCalib Risk Register

| ID | 위험 | 영향 | 현재 통제 | 상태 |
|---|---|---|---|---|
| R-001 | Agent의 hallucination 또는 unsupported claim | 잘못된 통과·탈락 제안 | criterion evidence와 관리자 HITL checklist | Open |
| R-002 | historical case 편향과 outcome leakage | 과거 판단을 답처럼 복제 | stage filter, commonality/difference, 관리자 검토 | Open |
| R-003 | similarity portion 과대 설정 | 평가기준보다 검색값이 지배 | 기본 0, 0.25 초과 warning, human final decision | Open |
| R-004 | 승인요청 알림 실패 | 관리자 검토 누락 | 알림 성공 전 HITL pending 전이 금지, durable local outbox·dedupe·retry test | Mitigated locally; operational adapter open |
| R-005 | 선택적 멘토 흐름의 승인 우회 | 완료자료 품질 저하 | mentor가 배정되면 mentor 승인 강제 및 scenario test | Mitigated offline |
| R-006 | 평가 중 dossier 변경 | stale 결과 자동 반영 | revision/hash snapshot, multi-process CAS lock, revision-aware freeze/update, stale result와 stale-lock quarantine | Mitigated locally; distributed lease open |
| R-007 | 실제 데이터 또는 secret 유출 | 개인정보·보안 사고 | synthetic-only 기본, env 이름만 기록, default test에서 live 제외; 사용자 승인 비식별 smoke만 별도 수행 | Open |
| R-008 | GitLab MR 또는 email provider 종속 | 운영 이식성 저하 | NotificationPort와 adapter 분리 | Planned |
| R-009 | 국소 pipeline 과분할 | 경계·버전·운영 복잡도 증가 | 독립 업무결과와 재사용자가 있을 때만 pipeline 승격 | Planned |
| R-010 | script, CLI, API별 로직 복제 | interface마다 판정과 오류 의미가 달라짐 | working script, Alpha CLI, local FastAPI와 one-job Worker가 같은 `AXCalib` registry/executor/request/result를 호출 | Local interfaces mitigated; distributed adapter parity open |
| R-011 | 범용 workflow engine 조기개발 | Domain MVP 지연과 보안 surface 확대 | 명시적 Python composition과 allowlisted registry 구현 | Mitigated for slice |
| R-012 | pipeline 사이 부분 side effect | 중복 평가·알림·불일치 상태 | atomic replace, durable outbox, project/education journal, hash-bound prerequisite, executor terminal replay와 expired-claim recovery | Locally mitigated; producer/distributed transaction open |
| R-013 | 구조도·module board와 코드 drift | 잘못된 작업순서와 완료판단 | 필수 문서 validation, same-change-set 규칙, Exit Evidence 기반 상태승격 | Mitigated in harness contract |
| R-014 | Excalibur 비유가 Agent 자동인증으로 해석됨 | 사람 책임 약화·제품 신뢰 훼손 | 고정 문장, 권한 diagram, HITL 경계와 교육용 caption | Mitigated in predev contract |
| R-015 | 옵션 과다로 첫 사용과 운영 구성이 실패 | adoption 저하·오설정 | minimal facade/default와 별도 expert profile | Mitigated in predev contract |
| R-016 | TOML/API로 필수 HITL·알림을 우회 | 무권한 인증 상태 전이 | protected config, domain guard, generic authority field 거부와 principal-bound project/education resource command | Mitigated for local project/education API; full API open |
| R-017 | OpenAPI/schema/구현 drift | SDK와 API 결과 불일치 | target/implemented artifact 분리, FastAPI-generated runtime schema exact contract test | Runtime API mitigated; full target parity open |
| R-018 | 최신 표준을 성급히 채택해 toolchain 불일치 | 생성기/validator 상호운용 실패 | OpenAPI 3.1/TOML 1.0 baseline, 3.2/1.1 spike | Open |
| R-019 | tutorial이 구현되지 않은 기능을 완료처럼 보임 | 잘못된 기대와 감사 오류 | pre-implementation 라벨, PROJECT_STATE/Exit Evidence 연동 | Mitigated in docs |
| R-020 | image-only PPTX sidecar의 요약·tag 편향 | 잘못된 criterion 근거와 과대평가 | source와 sidecar hash 고정, 평가 전 변경 탐지, reviewed-sidecar 표기, 부재 시 insufficient | Open until parser/model benchmark |
| R-021 | local actor ID를 실제 관리자 인증으로 오해 | demo 결과가 운영 승인처럼 사용됨 | demo actor label, injected verifier/grant, generic actor 거부, project/education audit actor의 verified principal binding | Local API mitigated; approved OIDC/JWKS open |
| R-022 | model의 근거 없는 긍정·부정 판정 | 자동 통과 또는 부당한 탈락 제안 | strict criterion set, source locator 검증, locator 없는 판정 insufficient 하향, 관리자 HITL | Mitigated in reference; gold benchmark open |
| R-023 | 사업부·소속별 기준 선택이 편향을 숨김 | 차별적 기준과 감사 실패 | ReviewContext와 explicit policy selector 분리, 자동 context mapping 금지, policy hash/owner/approval 기록 | Open until mapping policy approved |
| R-024 | 임의 model endpoint로 원문 전송 또는 capability 오판 | data egress와 잘못된 평가 | live opt-in, secret-free manifest, structured contract; allowlist/capability probe는 미구현 | Operational open |
| R-025 | project ID를 이용한 저장경로 이탈 | dossier 외 파일 조회·변조 | schema와 repository 경계에서 strict ID pattern 검증 및 traversal 회귀 test | Mitigated locally |
| R-026 | 다른 학습자 또는 program version의 과제가 milestone에 연결됨 | 잘못된 진도·인증 근거 | program/version/enrollment/milestone/learner exact-context binding과 회귀 test | Mitigated locally; identity auth open |
| R-027 | 과정 기획자 config가 임의 code/표현식을 실행 | 보안침해·HITL 우회 | typed requirement union, allowlisted pipeline ID/version, arbitrary import/expression 금지 | Mitigated for reference catalog |
| R-028 | program version 변경이 진행 중 가입을 조용히 바꿈 | 목표·기준 drift와 감사 실패 | immutable program hash, enrollment pin; migration/rollout은 미구현 | Mitigated against silent drift; rollout policy open |
| R-029 | dossier·enrollment·audit·notification의 cross-file commit 일부 실패 | orphan event 또는 감사 누락 | project와 education dossier/enrollment/audit는 hash-chained journal로 reconcile하고 HITL report/outbox는 hash prerequisite로 확인 | Local state mitigated; producer/distributed recovery open |
| R-030 | local actor 문자열을 실제 과정 관리자 권한으로 오해 | 무권한 과정 완료 | library direct call은 `offline_unverified_actor`, API는 verified principal·admin scope·org·revision과 `verified_api_principal` audit를 강제 | Mitigated in local API; approved IdP/RBAC open |
| R-031 | provider alias를 exact Qwen checkpoint로 오인하거나 provider별 structured-output 실패를 숨김 | 다른 모델 검증을 배포 승인으로 오해하거나 평가 실행이 중단됨 | proxy/deployment scope 분리, response model 확인, explicit dialect/output limit, JSON-object schema contract, no-fallback capability report | Proxy registration mitigated; exact on-prem/completion/gold open |
| R-032 | model endpoint 실패가 dossier audit에 기록되지 않음 | 실패 원인·재시도·비용 추적 누락 | 현재 fail-closed 상태전이; request hash와 safe failure kind를 journal/audit에 기록하는 후속 작업 | Open WP-01.R1/WP-05 |
| R-033 | provider가 upstream 4xx를 HTTP 500으로 wrapping하거나 `json_object` 요구를 다르게 구현 | retry 오판·원인 은폐·structured output 중단 | JSON keyword/schema prompt contract, wrapped status/type/code safe parse, dialect별 contract test | Mitigated for observed route; provider matrix open |
| R-034 | 외부 SkillBoss skill pack의 updater/version metadata와 credential 저장 방식 불일치 | 오래된 지침 사용 또는 개발 key 노출 | 공식 repository hash 검증, env 우선, 값 미기록, 제품/on-prem dependency 금지; key rotation은 사용자 계정 작업 | External tool risk open |
| R-035 | local transaction journal이 candidate dossier 구조를 중복 보존 | 민감한 progress note·review context의 보존 범위 증가 | 원본 bytes/reasoning/secret 금지, workspace 내부 경로, hash chain; ACL·retention·compaction은 후속 | Open operational hardening |
| R-036 | Windows에서 POSIX식 PID probe가 테스트 프로세스를 종료 | traceback 없는 pytest·Agent 세션 중단 | Windows는 read-only `OpenProcess`/`GetExitCodeProcess`, POSIX만 `os.kill(pid, 0)`, 현재 PID 회귀 test | Mitigated locally |
| R-037 | Docling과 정적검사 동시 실행이 저메모리 개발환경을 고갈 | 회귀 중단·불완전한 품질 주장 | Docling lazy import와 별도 `prep.ps1 docling`, lightweight default parser, 순차 검증과 512 MiB Pyright cap | Locally mitigated; CI resource sizing open |
| R-038 | Library registry 등록을 HTTP 공개 권한으로 오인 | 임의 local path 실행·actor 가장·사람 Gate 우회 | exact grant, generic authority 거부, 전용 project/education role·resource-scope·org·revision command와 no-path staging | Mitigated for implemented routes; full authorization open |
| R-039 | local Alpha API를 운영 server로 사용 | tenant 간 노출, 과대 request, path/credential 오용 | in-process 라벨, structural URI redaction, project size/hash guard, typed 1 MiB queued payload와 운영 NO-GO | Open until OIDC/RBAC, immutable upload, proxy limits and distributed worker |
| R-040 | optional Docling tree가 yanked `pypdfium2 5.12.0` wheel을 lock | 향후 clean install 또는 parser 재현성 저하 | lock warning 기록, Docling 별도 contract, 기본 test에서 격리 | Open; refresh and 5.12.1 compatibility check before next Docling run |
| R-041 | staged local file이 hash 확인 뒤 교체되거나 resolver ACL이 잘못됨 | 다른 bytes ingest 또는 tenant artifact 노출 | opaque ID, resolver principal/purpose, API size/hash, Library pre-transaction expected hash와 pre-evaluation frozen hash, 기본 deny | Open until immutable object version, ACL review and malware scan |
| R-042 | 관리자 decision commit 뒤 HTTP 응답 유실 | client가 결과를 확인하지 못하거나 무작정 재시도 | authorized safe GET, principal/resource/payload-bound local idempotency result와 decision/audit integrity 재검증 | Locally mitigated; commit-record crash window/distributed store open |
| R-043 | mentor/instructor resource scope가 실제 교육 배정 원장과 다름 | 다른 사람이 확인·점수를 기록하거나 tenant가 섞임 | exact enrollment/program scope, organization, role와 audit actor를 모두 검사하고 기본 verifier는 거부 | Open until approved OIDC claim mapping, assignment source and revocation tests |
| R-044 | local Worker payload 보존·lease 만료 | 민감 업무내용 평문 보존 또는 장시간 실행 중 claim 상실 | validated object, 1 MiB/credential-key deny, payload hash, workspace ACL 전제, executor serialization과 terminal replay; heartbeat/retention/encryption은 운영 adapter 요구 | Local Alpha only; DLP, heartbeat, broker/database queue open |
| R-045 | GitHub/GitLab Wiki와 main 문서 drift 또는 잘못된 remote push | 사용자가 오래된 매뉴얼을 보거나 사내 정보·자격증명이 유출됨 | main `wiki/` 단일 원본, ledger mirror, manifest/link/parity 검증, env-only remote, dirty/origin guard와 opt-in CI; direct edit·force push 금지 | Local export mitigated; actual GitHub/GitLab publication and credential review open |
