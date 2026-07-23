# GitHub / GitLab Wiki 운영 규칙

## 단일 원본

메인 저장소의 `wiki/`가 사용자용 Wiki 콘텐츠의 **단일 원본**이다. GitHub Wiki와 사내 GitLab Wiki는
별도 Git 저장소지만 배포 결과로만 취급한다. 플랫폼 화면에서 직접 수정한 내용은 다음 동기화 때
충돌하거나 사라질 수 있으므로 반드시 `wiki/`에 먼저 반영한다.

`PROJECT_STATE.md`는 `Development-Ledger.md`로 자동 mirror된다. 따라서 개발과정과 append-only 이력은
원장을 갱신하고 Wiki publication을 실행하면 함께 반영된다.

## 로컬 검증과 미리보기

```powershell
uv run --no-sync python scripts/wiki/sync_wiki.py validate
uv run --no-sync python scripts/wiki/sync_wiki.py export `
  --target github --output output/wiki-preview/github
uv run --no-sync python scripts/wiki/sync_wiki.py export `
  --target gitlab --output output/wiki-preview/gitlab
```

GitHub는 `_Sidebar.md`, GitLab은 `_sidebar.md`를 사용한다. export가 파일명만 변환하며 본문과 asset은
동일하다. 배포 manifest에 관리 파일, main source commit과 ledger history ID를 기록한다.

## GitHub Wiki 최초 설정

GitHub 공식 Wiki 화면에서 최초 `Home` page를 한 번 생성해야 `.wiki.git` 저장소를 clone할 수 있다.
그 뒤 repository variable `AXCALIB_WIKI_PUBLISH_ENABLED=true`를 설정하면 `.github/workflows/wiki.yml`의
publish job을 opt-in할 수 있다. workflow는 먼저 두 target export와 parity test를 통과해야 한다.

GitHub Wiki가 초기화되기 전에는 자동 publish를 켜지 않는다. 현재 `AXCalib.wiki.git`이 clone되지 않는
상태라면 최초 Home이 없거나 권한이 없는지 확인한다.

## 사내 GitLab Wiki 설정

사내 흐름은 다음과 같다.

```text
개발 PC → GitHub main → 사내 개발서버 pull → 사내 GitLab main push
                                             └→ GitLab Wiki publish
```

GitLab 프로젝트에서 Wiki를 활성화하고 최초 Home을 만든다. CI/CD variable은 다음처럼 구성한다.

- `AXCALIB_WIKI_CI_ENABLED=true`: Wiki validate job 활성화
- `AXCALIB_WIKI_PUBLISH_ENABLED=true`: 기본 branch에서 publish job 활성화
- `AXCALIB_GITLAB_WIKI_URL`: `group/project.wiki.git` remote. SSH deploy key 방식을 권장

URL, token, private key는 저장소에 commit하지 않는다. variable은 Protected/Masked로 관리하고 Wiki를
push할 최소 권한만 부여한다. 사내 runner에 Python 3.12와 Git이 있어야 한다.

## 수동 dry-run과 명시적 push

원격 URL은 환경변수로만 주입한다.

```powershell
$env:AXCALIB_GITHUB_WIKI_URL = "https://github.com/ORG/REPO.wiki.git"
uv run --no-sync python scripts/wiki/sync_wiki.py publish `
  --target github `
  --remote-url-env AXCALIB_GITHUB_WIKI_URL `
  --checkout output/wiki-checkouts/github
```

위 명령은 dry-run이며 commit/push하지 않는다. 검토 후에만 `--push`를 추가한다. 기존 checkout에
미커밋 변경이 있거나 origin이 요청한 remote와 다르면 fail-closed한다. 과거 배포 manifest에 기록된
AXCalib 관리 파일만 정리하며 다른 팀이 만든 Wiki 파일은 삭제하지 않는다.

## 변경 시 함께 갱신할 Page

| 변경 | Wiki 갱신 |
|---|---|
| 공개 Library API·상태 | Library 매뉴얼, 예제 |
| 등록·완료 Workflow | 두 Gate 실습, 보안과 HITL |
| config·model·on-prem | 설정과 On-prem |
| API·Worker·Web | API / Web / App 적용 |
| module·directory | 아키텍처와 프로젝트 구조 |
| 개발 단계·검증 | PROJECT_STATE 원장; 자동 Development Ledger mirror |
| Wiki 배포 방식 | 이 문서와 CI/script test |

publication 실패는 제품 기능 실패와 분리해 기록하되, Wiki가 갱신되지 않은 상태에서 문서 배포 완료를
선언하지 않는다.
