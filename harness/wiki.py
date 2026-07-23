"""Portable AXCalib Wiki validation, export, and publication helpers.

The main repository's ``wiki/`` directory is the canonical authoring surface.
GitHub and GitLab wikis are deployment targets, not independent sources of truth.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

WikiTarget = Literal["github", "gitlab"]

MANIFEST_NAME = "wiki-manifest.json"
DEPLOYED_MANIFEST_NAME = ".axcalib-wiki-manifest.json"
MANIFEST_SCHEMA = "axcalib.wiki/v1"
SUPPORTED_TARGETS: tuple[WikiTarget, ...] = ("github", "gitlab")
DEFAULT_REMOTE_ENV = {
    "github": "AXCALIB_GITHUB_WIKI_URL",
    "gitlab": "AXCALIB_GITLAB_WIKI_URL",
}
GENERATED_BANNER = (
    "<!-- Managed from the AXCalib main repository wiki/ source. "
    "Do not edit the deployed Wiki directly. -->\n\n"
)
REQUIRED_PAGE_DESTINATIONS = {
    "Home.md",
    "Getting-Started.md",
    "Library-Manual.md",
    "Two-Gate-Tutorial.md",
    "Examples-and-Recipes.md",
    "API-Web-App-Integration.md",
    "Configuration-and-On-Prem.md",
    "Architecture-and-Project.md",
    "Security-and-HITL.md",
    "Development-Process.md",
    "Documentation-Governance.md",
    "Development-Ledger.md",
}


class WikiError(RuntimeError):
    """Base class for portable Wiki failures."""


class WikiManifestError(WikiError):
    """Raised when the canonical Wiki manifest is invalid."""


class WikiPublishError(WikiError):
    """Raised when a Wiki checkout cannot be safely published."""


@dataclass(frozen=True)
class PageSpec:
    """A canonical Markdown page copied from ``wiki/``."""

    source: str
    destination: str


@dataclass(frozen=True)
class MirrorSpec:
    """A repository document rendered as a generated Wiki page."""

    source: str
    destination: str
    strip_frontmatter: bool


@dataclass(frozen=True)
class AssetSpec:
    """A repository asset copied into the deployed Wiki."""

    source: str
    destination: str


@dataclass(frozen=True)
class SidebarSpec:
    """The canonical sidebar and its platform-specific filenames."""

    source: str
    github: str
    gitlab: str

    def destination(self, target: WikiTarget) -> str:
        """Return the sidebar filename required by ``target``."""

        return self.github if target == "github" else self.gitlab


@dataclass(frozen=True)
class WikiManifest:
    """Validated, platform-neutral Wiki publication manifest."""

    pages: tuple[PageSpec, ...]
    mirrors: tuple[MirrorSpec, ...]
    assets: tuple[AssetSpec, ...]
    sidebar: SidebarSpec

    def page_destinations(self) -> set[str]:
        """Return every generated or authored Wiki page destination."""

        return {item.destination for item in (*self.pages, *self.mirrors)}

    def managed_files(self, target: WikiTarget) -> tuple[str, ...]:
        """Return the complete managed file set for a deployment target."""

        files = self.page_destinations()
        files.update(item.destination for item in self.assets)
        files.add(self.sidebar.destination(target))
        files.add(DEPLOYED_MANIFEST_NAME)
        return tuple(sorted(files, key=str.casefold))


@dataclass(frozen=True)
class WikiExportResult:
    """Result metadata for a deterministic Wiki export."""

    target: WikiTarget
    output_dir: Path
    managed_files: tuple[str, ...]
    source_commit: str
    source_history_id: str


@dataclass(frozen=True)
class WikiPublishResult:
    """Result metadata for a dry-run or pushed Wiki publication."""

    target: WikiTarget
    checkout_dir: Path
    changed: bool
    committed: bool
    pushed: bool
    change_lines: tuple[str, ...]


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise WikiManifestError(f"{label} must be an object")
    return value


def _require_string(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WikiManifestError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise WikiManifestError(f"{label} has unknown keys: {', '.join(unknown)}")


def _safe_relative(value: str, *, suffix: str | None = None) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise WikiManifestError(f"unsafe relative path: {value}")
    if ":" in normalized:
        raise WikiManifestError(f"unsafe relative path: {value}")
    if suffix is not None and path.suffix.casefold() != suffix.casefold():
        raise WikiManifestError(f"path must end with {suffix}: {value}")
    return path.as_posix()


def _parse_pages(value: object) -> tuple[PageSpec, ...]:
    if not isinstance(value, list) or not value:
        raise WikiManifestError("pages must be a non-empty array")
    pages: list[PageSpec] = []
    for index, raw in enumerate(value):
        label = f"pages[{index}]"
        item = _require_mapping(raw, label)
        _reject_unknown(item, {"source", "destination"}, label)
        pages.append(
            PageSpec(
                source=_safe_relative(_require_string(item, "source", label), suffix=".md"),
                destination=_safe_relative(
                    _require_string(item, "destination", label), suffix=".md"
                ),
            )
        )
    return tuple(pages)


def _parse_mirrors(value: object) -> tuple[MirrorSpec, ...]:
    if not isinstance(value, list) or not value:
        raise WikiManifestError("mirrors must be a non-empty array")
    mirrors: list[MirrorSpec] = []
    for index, raw in enumerate(value):
        label = f"mirrors[{index}]"
        item = _require_mapping(raw, label)
        _reject_unknown(item, {"source", "destination", "strip_frontmatter"}, label)
        strip_frontmatter = item.get("strip_frontmatter")
        if not isinstance(strip_frontmatter, bool):
            raise WikiManifestError(f"{label}.strip_frontmatter must be a boolean")
        mirrors.append(
            MirrorSpec(
                source=_safe_relative(_require_string(item, "source", label), suffix=".md"),
                destination=_safe_relative(
                    _require_string(item, "destination", label), suffix=".md"
                ),
                strip_frontmatter=strip_frontmatter,
            )
        )
    return tuple(mirrors)


def _parse_assets(value: object) -> tuple[AssetSpec, ...]:
    if not isinstance(value, list):
        raise WikiManifestError("assets must be an array")
    assets: list[AssetSpec] = []
    for index, raw in enumerate(value):
        label = f"assets[{index}]"
        item = _require_mapping(raw, label)
        _reject_unknown(item, {"source", "destination"}, label)
        source = _safe_relative(_require_string(item, "source", label))
        destination = _safe_relative(_require_string(item, "destination", label))
        if not destination.startswith("assets/"):
            raise WikiManifestError(f"{label}.destination must be under assets/")
        assets.append(AssetSpec(source=source, destination=destination))
    return tuple(assets)


def _parse_sidebar(value: object) -> SidebarSpec:
    item = _require_mapping(value, "sidebar")
    _reject_unknown(item, {"source", "github", "gitlab"}, "sidebar")
    return SidebarSpec(
        source=_safe_relative(_require_string(item, "source", "sidebar"), suffix=".md"),
        github=_safe_relative(_require_string(item, "github", "sidebar"), suffix=".md"),
        gitlab=_safe_relative(_require_string(item, "gitlab", "sidebar"), suffix=".md"),
    )


def load_wiki_manifest(root: Path) -> WikiManifest:
    """Load and structurally validate ``wiki/wiki-manifest.json``."""

    path = root / "wiki" / MANIFEST_NAME
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WikiManifestError(f"cannot read {path.relative_to(root)}: {error}") from error
    data = _require_mapping(raw, MANIFEST_NAME)
    _reject_unknown(
        data,
        {"schema_version", "pages", "mirrors", "assets", "sidebar"},
        MANIFEST_NAME,
    )
    if data.get("schema_version") != MANIFEST_SCHEMA:
        raise WikiManifestError(f"schema_version must be {MANIFEST_SCHEMA}")
    manifest = WikiManifest(
        pages=_parse_pages(data.get("pages")),
        mirrors=_parse_mirrors(data.get("mirrors")),
        assets=_parse_assets(data.get("assets")),
        sidebar=_parse_sidebar(data.get("sidebar")),
    )
    _validate_manifest_destinations(manifest)
    return manifest


def _validate_manifest_destinations(manifest: WikiManifest) -> None:
    destinations = [item.destination for item in (*manifest.pages, *manifest.mirrors)]
    destinations.extend(item.destination for item in manifest.assets)
    folded = [item.casefold() for item in destinations]
    if len(folded) != len(set(folded)):
        raise WikiManifestError("page, mirror, and asset destinations must be unique")
    missing = sorted(REQUIRED_PAGE_DESTINATIONS - manifest.page_destinations())
    if missing:
        raise WikiManifestError(f"missing required Wiki pages: {', '.join(missing)}")
    for target in SUPPORTED_TARGETS:
        sidebar = manifest.sidebar.destination(target)
        if sidebar.casefold() in set(folded):
            raise WikiManifestError(f"{target} sidebar collides with another destination")


def _without_fenced_code(markdown: str) -> str:
    return re.sub(r"```.*?```|~~~.*?~~~", "", markdown, flags=re.DOTALL)


def _link_targets(markdown: str) -> tuple[str, ...]:
    cleaned = _without_fenced_code(markdown)
    return tuple(re.findall(r"!?(?:\[[^\]]*\])\(([^)]+)\)", cleaned))


def _validate_link(
    source: str,
    target: str,
    page_destinations: set[str],
    asset_destinations: set[str],
) -> str | None:
    clean = target.strip().strip("<>")
    if not clean or clean.startswith("#"):
        return None
    lowered = clean.casefold()
    if lowered.startswith(("https://", "http://", "mailto:")):
        return None
    if "://" in clean or lowered.startswith(("file:", "javascript:", "data:")):
        return f"{source}: unsupported or unsafe link target {target}"
    path_only = clean.split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
    path = PurePosixPath(path_only)
    if path.is_absolute() or any(part in {"..", "."} for part in path.parts):
        return f"{source}: link must stay inside the portable Wiki: {target}"
    normalized = path.as_posix()
    if normalized in asset_destinations:
        return None
    page_candidate = normalized if normalized.casefold().endswith(".md") else f"{normalized}.md"
    if page_candidate in page_destinations:
        return None
    return f"{source}: missing portable Wiki link target {target}"


def _strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).lstrip() + "\n"
    return text


def _ledger_history_id(root: Path) -> str:
    try:
        ledger = (root / "PROJECT_STATE.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "unknown"
    match = re.search(
        r"^last_history_id:\s*(HIST-\d{4}-\d{2}-\d{2}-\d{3})\s*$",
        ledger,
        re.MULTILINE,
    )
    return match.group(1) if match else "unknown"


def validate_wiki(root: Path) -> list[str]:
    """Return portable Wiki contract errors without changing any files."""

    try:
        manifest = load_wiki_manifest(root)
    except WikiManifestError as error:
        return [f"wiki: {error}"]

    errors: list[str] = []
    wiki_root = root / "wiki"
    declared_sources = {item.source for item in manifest.pages}
    declared_sources.add(manifest.sidebar.source)
    actual_sources = {
        path.relative_to(wiki_root).as_posix() for path in wiki_root.rglob("*.md") if path.is_file()
    }
    undeclared = sorted(actual_sources - declared_sources)
    missing_declared = sorted(declared_sources - actual_sources)
    if undeclared:
        errors.append(f"wiki: undeclared Markdown sources: {', '.join(undeclared)}")
    if missing_declared:
        errors.append(f"wiki: missing declared Markdown sources: {', '.join(missing_declared)}")

    page_destinations = manifest.page_destinations()
    asset_destinations = {item.destination for item in manifest.assets}
    source_specs = [(item.source, wiki_root / item.source) for item in manifest.pages]
    source_specs.append((manifest.sidebar.source, wiki_root / manifest.sidebar.source))
    for relative, path in source_specs:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"wiki/{relative}: cannot read UTF-8 Markdown: {error}")
            continue
        if not re.search(r"^#\s+\S", text, re.MULTILINE) and relative != manifest.sidebar.source:
            errors.append(f"wiki/{relative}: first-level heading is required")
        for target in _link_targets(text):
            error = _validate_link(
                f"wiki/{relative}", target, page_destinations, asset_destinations
            )
            if error is not None:
                errors.append(error)

    for item in manifest.mirrors:
        if not (root / item.source).is_file():
            errors.append(f"wiki mirror source is missing: {item.source}")
    for item in manifest.assets:
        if not (root / item.source).is_file():
            errors.append(f"wiki asset source is missing: {item.source}")

    required_tokens = {
        "Home.md": ("AX Certification Agent Library", "근거가 자격을 만들고"),
        "Library-Manual.md": ("AXCalib", "evaluate", "Dossier"),
        "Development-Process.md": ("PROJECT_STATE.md", "P / WP / G", "append-only"),
        "Documentation-Governance.md": ("wiki/", "GitHub", "GitLab", "단일 원본"),
        "Configuration-and-On-Prem.md": (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "Qwen3.5-397B-A17B",
        ),
    }
    page_by_destination = {item.destination: wiki_root / item.source for item in manifest.pages}
    for destination, tokens in required_tokens.items():
        path = page_by_destination.get(destination)
        if path is None or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                errors.append(f"wiki/{path.name}: missing required token {token}")
    return errors


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_output_path(output_dir: Path, relative: str) -> Path:
    root = output_dir.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise WikiManifestError(f"managed path leaves Wiki output: {relative}") from error
    return candidate


def _source_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _previous_managed_files(output_dir: Path) -> tuple[str, ...]:
    path = output_dir / DEPLOYED_MANIFEST_NAME
    if not path.is_file():
        return ()
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WikiManifestError(f"cannot read prior deployed manifest: {error}") from error
    data = _require_mapping(raw, DEPLOYED_MANIFEST_NAME)
    values = data.get("managed_files")
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise WikiManifestError("prior deployed manifest has invalid managed_files")
    return tuple(_safe_relative(item) for item in values)


def export_wiki(root: Path, target: WikiTarget, output_dir: Path) -> WikiExportResult:
    """Export the canonical Wiki into a platform-specific checkout directory."""

    if target not in SUPPORTED_TARGETS:
        raise WikiManifestError(f"unsupported Wiki target: {target}")
    errors = validate_wiki(root)
    if errors:
        raise WikiManifestError("; ".join(errors))
    manifest = load_wiki_manifest(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    managed = manifest.managed_files(target)
    managed_set = set(managed)
    for stale in _previous_managed_files(output_dir):
        if stale not in managed_set:
            path = _safe_output_path(output_dir, stale)
            if path.is_file():
                path.unlink()

    wiki_root = root / "wiki"
    for item in manifest.pages:
        content = (wiki_root / item.source).read_text(encoding="utf-8")
        _atomic_write_text(
            _safe_output_path(output_dir, item.destination), GENERATED_BANNER + content
        )
    for item in manifest.mirrors:
        content = (root / item.source).read_text(encoding="utf-8")
        if item.strip_frontmatter:
            content = _strip_frontmatter(content)
        _atomic_write_text(
            _safe_output_path(output_dir, item.destination), GENERATED_BANNER + content
        )
    sidebar = (wiki_root / manifest.sidebar.source).read_text(encoding="utf-8")
    _atomic_write_text(
        _safe_output_path(output_dir, manifest.sidebar.destination(target)),
        GENERATED_BANNER + sidebar,
    )
    for item in manifest.assets:
        _atomic_copy(root / item.source, _safe_output_path(output_dir, item.destination))

    source_commit = _source_commit(root)
    source_history_id = _ledger_history_id(root)
    deployment_manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "target": target,
        "source_commit": source_commit,
        "source_history_id": source_history_id,
        "managed_files": list(managed),
    }
    _atomic_write_text(
        output_dir / DEPLOYED_MANIFEST_NAME,
        json.dumps(deployment_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return WikiExportResult(
        target=target,
        output_dir=output_dir,
        managed_files=managed,
        source_commit=source_commit,
        source_history_id=source_history_id,
    )


def _redacted_remote(remote_url: str) -> str:
    split = urlsplit(remote_url)
    if not split.scheme or "@" not in split.netloc:
        return remote_url
    host = split.netloc.rsplit("@", 1)[1]
    return urlunsplit((split.scheme, host, split.path, split.query, split.fragment))


def _redact_output(value: str, remote_url: str) -> str:
    redacted = value.replace(remote_url, "<redacted-wiki-remote>")
    safe_remote = _redacted_remote(remote_url)
    if safe_remote != remote_url:
        redacted = redacted.replace(safe_remote, "<wiki-remote>")
    return redacted


def _run_git(
    args: list[str], *, cwd: Path, remote_url: str, allow_failure: bool = False
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 and not allow_failure:
        detail = _redact_output((completed.stdout + completed.stderr).strip(), remote_url)
        raise WikiPublishError(f"git {' '.join(args[:2])} failed: {detail}")
    return completed


def _normalized_remote(remote_url: str) -> str:
    return _redacted_remote(remote_url).rstrip("/")


def _prepare_checkout(
    remote_url: str,
    checkout_dir: Path,
    *,
    allow_managed_dirty: bool,
) -> bool:
    """Prepare a checkout and return whether it contains a resumed dry-run."""

    if checkout_dir.exists():
        if not (checkout_dir / ".git").is_dir():
            raise WikiPublishError("checkout directory exists but is not a Git repository")
        configured = _run_git(
            ["remote", "get-url", "origin"], cwd=checkout_dir, remote_url=remote_url
        ).stdout.strip()
        if _normalized_remote(configured) != _normalized_remote(remote_url):
            raise WikiPublishError("checkout origin does not match the requested Wiki remote")
        dirty = _run_git(
            ["status", "--porcelain"], cwd=checkout_dir, remote_url=remote_url
        ).stdout.strip()
        if dirty:
            if allow_managed_dirty:
                return True
            raise WikiPublishError("Wiki checkout has uncommitted changes; inspect them first")
        _run_git(["fetch", "--prune", "origin"], cwd=checkout_dir, remote_url=remote_url)
        upstream = _run_git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=checkout_dir,
            remote_url=remote_url,
            allow_failure=True,
        )
        if upstream.returncode == 0:
            _run_git(["merge", "--ff-only", "@{u}"], cwd=checkout_dir, remote_url=remote_url)
        return False

    checkout_dir.parent.mkdir(parents=True, exist_ok=True)
    completed = _run_git(
        ["clone", "--no-tags", remote_url, str(checkout_dir)],
        cwd=checkout_dir.parent,
        remote_url=remote_url,
        allow_failure=True,
    )
    if completed.returncode != 0:
        detail = _redact_output((completed.stdout + completed.stderr).strip(), remote_url)
        raise WikiPublishError(
            "Wiki remote could not be cloned. Enable the Wiki, create its initial Home page, "
            f"and verify credentials. Git detail: {detail}"
        )
    return False


def _change_paths(change_lines: tuple[str, ...]) -> set[str]:
    paths: set[str] = set()
    for line in change_lines:
        payload = line[3:] if len(line) >= 4 else line
        if " -> " in payload:
            paths.update(part.strip() for part in payload.split(" -> ", 1))
        elif payload.strip():
            paths.add(payload.strip())
    return paths


def publish_wiki(
    root: Path,
    target: WikiTarget,
    remote_url: str,
    checkout_dir: Path,
    *,
    push: bool = False,
    commit_message: str | None = None,
) -> WikiPublishResult:
    """Prepare or explicitly push one platform Wiki checkout.

    Without ``push=True`` this is a dry-run: files are exported but no commit or
    network write is performed after the initial clone/fetch.
    """

    if target not in SUPPORTED_TARGETS:
        raise WikiPublishError(f"unsupported Wiki target: {target}")
    if not remote_url.strip():
        raise WikiPublishError("Wiki remote URL is empty")
    resumed_dry_run = _prepare_checkout(
        remote_url,
        checkout_dir,
        allow_managed_dirty=push,
    )
    previous_managed = set(_previous_managed_files(checkout_dir))
    export = export_wiki(root, target, checkout_dir)
    status = _run_git(
        ["status", "--porcelain", "--untracked-files=all"],
        cwd=checkout_dir,
        remote_url=remote_url,
    ).stdout.splitlines()
    change_lines = tuple(line for line in status if line.strip())
    if not change_lines:
        return WikiPublishResult(target, checkout_dir, False, False, False, ())
    if not push:
        return WikiPublishResult(target, checkout_dir, True, False, False, change_lines)

    allowed_changes = set(export.managed_files) | previous_managed
    unexpected = sorted(_change_paths(change_lines) - allowed_changes)
    if unexpected:
        mode = "resumed dry-run" if resumed_dry_run else "Wiki checkout"
        raise WikiPublishError(
            f"{mode} contains changes outside the AXCalib managed manifest: "
            + ", ".join(unexpected)
        )

    _run_git(["add", "--all", "--", "."], cwd=checkout_dir, remote_url=remote_url)
    message = commit_message or f"docs(wiki): sync AXCalib {export.source_history_id}"
    _run_git(
        [
            "-c",
            "user.name=AXCalib Wiki Bot",
            "-c",
            "user.email=wiki-bot@axcalib.local",
            "commit",
            "-m",
            message,
        ],
        cwd=checkout_dir,
        remote_url=remote_url,
    )
    _run_git(["push", "--set-upstream", "origin", "HEAD"], cwd=checkout_dir, remote_url=remote_url)
    return WikiPublishResult(target, checkout_dir, True, True, True, change_lines)
