# WP-00.D2 Portable Dual-Wiki Harness Report

- Date: 2026-07-23
- Scope: documentation distribution control
- Product Gate impact: none; G4 remains in progress and WP-06.I4 remains policy-blocked

## Outcome

AXCalib main repository now contains a platform-neutral `wiki/` source for manuals, tutorials, project and
development information. The same source can be validated and exported for GitHub or GitLab Wiki. The project
ledger is rendered into the Wiki automatically, so append-only development history does not require manual
copying.

## Implemented contract

- allowlisted pages, mirrors, assets and sidebar in `wiki/wiki-manifest.json`
- required manual/tutorial/config/security/development content validation
- portable local-link validation and repository-bound asset validation
- GitHub `_Sidebar.md` / GitLab `_sidebar.md` target transform
- deterministic `Development-Ledger.md` mirror from `PROJECT_STATE.md`
- deployed manifest with managed files, source commit and ledger history ID
- atomic export and manifest-scoped stale file pruning
- remote URL from environment only, remote mismatch/dirty checkout guards and redacted errors
- dry-run publication by default; explicit `--push` for commit and network write
- opt-in GitHub Action and GitLab Self-Managed CI jobs

## Code-review findings and controls

1. Main repository push does not copy a separate Wiki repository. Separate publication is required.
2. Direct Wiki editing would create three sources of truth. The deployed banner and governance page forbid it.
3. Platform sidebar names differ only by case and cannot coexist safely on Windows. Export performs the rename.
4. A publisher that deletes the target directory could remove team-owned pages. Only files listed in the previous
   AXCalib deployment manifest are pruned.
5. Remote URLs may contain credentials. The CLI accepts an environment variable and redacts remote text in errors.
6. Automatic publication before initialization would fail. Both CI systems require explicit enable variables.
7. A dry-run checkout is intentionally dirty. Explicit push may resume it only when every changed path belongs to
   the current or previous AXCalib managed manifest; foreign team files fail closed.

## Verification evidence

| Check | Result |
|---|---|
| Canonical Wiki validation | 0 errors |
| Dependency-free GitHub/GitLab parity contract | 1 passed |
| Targeted Wiki unit/integration harness | 6 passed |
| Split repository tests | 136 passed: unit 86, integration 31, contract 19 |
| Offline evaluation harness | 10 groups passed; no live model or Vector DB |
| Ruff / Pyright | all checks passed / 0 errors, 0 warnings |
| `prep.ps1 validate` | 0 errors, 0 warnings |
| GitHub Action / GitLab CI YAML | both parsed successfully |
| Local bare Wiki repository publication | first push succeeded; second run had no changes |
| GitHub Wiki live publication | `f384648`, pages 4/4 and image assets 3/3 returned HTTP 200 |

The full test command was not run as one long process. Unit, integration and contract groups were executed
separately to preserve the low-memory and interruption-recovery contract.

## Remaining external work

- GitHub main: deployed as `b2c6e48`; Actions run `30014678127` validated the source successfully.
- GitHub Wiki: live push/render and automatic validate/publish jobs verified. The action runtime was upgraded
  to checkout/setup-python v6 after Node.js 20 deprecation annotations; the v6 live run remains to verify.
- GitLab: provide the on-prem Wiki remote, runner, deploy credential and protected variables.
- Verify Markdown and image rendering in the actual GitLab UI.
- Decide retention and review policy for any team-owned Wiki pages outside the AXCalib manifest.

The GitHub main repository and GitHub Wiki were modified by the approved deployment. The GitLab Wiki was not
modified because the on-prem deployment environment is not available here.
