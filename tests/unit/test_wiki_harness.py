from __future__ import annotations

import json
import shutil
from pathlib import Path

from harness.wiki import (
    DEPLOYED_MANIFEST_NAME,
    export_wiki,
    load_wiki_manifest,
    validate_wiki,
)

ROOT = Path(__file__).resolve().parents[2]


def _copy_wiki_contract(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "wiki", root / "wiki")
    shutil.copyfile(ROOT / "PROJECT_STATE.md", root / "PROJECT_STATE.md")
    manifest = load_wiki_manifest(ROOT)
    for item in manifest.assets:
        destination = root / item.source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / item.source, destination)
    return root


def test_repository_wiki_contract_validates() -> None:
    assert validate_wiki(ROOT) == []


def test_missing_portable_page_link_is_rejected(tmp_path: Path) -> None:
    root = _copy_wiki_contract(tmp_path)
    home = root / "wiki" / "Home.md"
    home.write_text(
        home.read_text(encoding="utf-8") + "\n[깨진 링크](Missing-Page)\n",
        encoding="utf-8",
    )

    errors = validate_wiki(root)

    assert "wiki/Home.md: missing portable Wiki link target Missing-Page" in errors


def test_export_prunes_only_previously_managed_files(tmp_path: Path) -> None:
    output = tmp_path / "wiki"
    output.mkdir()
    stale = output / "Old-Managed.md"
    foreign = output / "Team-Notes.md"
    stale.write_text("old", encoding="utf-8")
    foreign.write_text("keep", encoding="utf-8")
    (output / DEPLOYED_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema_version": "axcalib.wiki/v1",
                "managed_files": ["Old-Managed.md", DEPLOYED_MANIFEST_NAME],
            }
        ),
        encoding="utf-8",
    )

    result = export_wiki(ROOT, "gitlab", output)

    assert not stale.exists()
    assert foreign.read_text(encoding="utf-8") == "keep"
    assert "_sidebar.md" in result.managed_files
    assert "_Sidebar.md" not in result.managed_files
