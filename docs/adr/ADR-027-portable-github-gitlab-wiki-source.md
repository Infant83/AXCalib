# ADR-027: Portable GitHub and GitLab Wiki Source

- Status: Accepted
- Date: 2026-07-23
- Decision owners: AXCalib product and documentation owners

## Context

AXCalib의 개발 기준은 GitHub main 저장소에서 관리하지만 사내 사용자는 GitHub 내용을 pull한 뒤
on-prem GitLab에 push한 결과를 사용한다. GitHub와 GitLab Wiki는 코드 저장소와 분리된 별도 Git
저장소다. 두 Wiki를 화면에서 독립적으로 편집하면 사용 매뉴얼, 개발과정과 실제 코드 사이에 세 방향
drift가 생긴다.

사내 GitLab URL, runner와 credential은 이 public 저장소에서 알 수 없으며 secret을 commit할 수 없다.
또한 GitHub Wiki는 최초 Home page가 만들어지기 전에는 `.wiki.git` clone이 불가능할 수 있다.

## Decision

1. 메인 저장소의 `wiki/`를 플랫폼 중립 사용자 문서의 단일 원본으로 사용한다.
2. `PROJECT_STATE.md`는 export 시 `Development-Ledger.md`로 frontmatter를 제외하고 mirror한다.
3. `wiki/wiki-manifest.json`이 page, mirror, asset과 sidebar를 allowlist한다.
4. GitHub의 `_Sidebar.md`와 GitLab의 `_sidebar.md` 차이는 export에서만 변환한다.
5. `harness/wiki.py`와 `scripts/wiki/sync_wiki.py`가 validate, export와 명시적 publish를 제공한다.
6. publish는 remote URL을 환경변수로만 받고 `--push`가 없으면 commit/push하지 않는다.
7. 배포 manifest에 관리 파일, main source commit과 ledger history ID를 기록한다. 이전 manifest에
   등록된 관리 파일만 prune하고 다른 Wiki page는 삭제하지 않는다.
8. GitHub Action과 GitLab CI는 enable variable이 `true`일 때만 publish하는 opt-in 계약이다.
9. Wiki의 실제 원격 push 성공은 별도 운영 증거이며 local export 통과와 구분한다.

## Consequences

### Positive

- GitHub와 사내 GitLab 사용자가 같은 매뉴얼과 개발 이력을 본다.
- 코드와 문서를 한 pull/push 체인으로 전달할 수 있다.
- 개발 원장을 다시 작성하지 않고 Wiki에서 최신 append-only history를 읽을 수 있다.
- 원격 자격증명과 사내 주소가 저장소에 남지 않는다.
- direct Wiki edit나 알 수 없는 file deletion을 피할 수 있다.

### Cost and limitations

- 공개 API, workflow, 설정 또는 운영법을 바꾸는 change set은 `wiki/`도 검토해야 한다.
- GitHub와 GitLab에서 각각 최초 Wiki Home, runner/permission/credential을 한 번 구성해야 한다.
- 플랫폼별 Markdown renderer의 세부 차이는 계속 parity smoke와 실제 화면 확인이 필요하다.
- 현재 local contract는 실제 GitHub/GitLab Wiki publication 성공을 증명하지 않는다.

## Rejected alternatives

- 두 Wiki를 각각 수동 편집: 내용과 history가 빠르게 분기된다.
- GitHub Wiki를 사내 GitLab의 external Wiki로만 링크: on-prem 독립성과 내부 접근 요구를 만족하지 못한다.
- main 저장소의 전체 `docs/`를 그대로 복사: 사용자용 정보와 내부 기준 문서가 섞이고 상대 링크가 깨진다.
- CI에 token 또는 on-prem URL을 hard-code: credential·환경정보 유출 위험이 있다.
