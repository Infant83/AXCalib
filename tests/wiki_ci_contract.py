"""Dependency-free dual-Wiki parity checks for GitHub and GitLab CI."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.wiki import (  # noqa: E402
    DEPLOYED_MANIFEST_NAME,
    export_wiki,
    load_wiki_manifest,
    validate_wiki,
)


class WikiCiContract(unittest.TestCase):
    def test_portable_source_and_target_exports_match(self) -> None:
        self.assertEqual(validate_wiki(ROOT), [])
        manifest = load_wiki_manifest(ROOT)
        with tempfile.TemporaryDirectory(prefix="axcalib-wiki-ci-") as temporary:
            output = Path(temporary)
            github = output / "github"
            gitlab = output / "gitlab"
            export_wiki(ROOT, "github", github)
            export_wiki(ROOT, "gitlab", gitlab)

            common = manifest.page_destinations()
            common.update(item.destination for item in manifest.assets)
            for relative in sorted(common):
                self.assertEqual(
                    (github / relative).read_bytes(),
                    (gitlab / relative).read_bytes(),
                    relative,
                )
            self.assertEqual(
                (github / manifest.sidebar.github).read_bytes(),
                (gitlab / manifest.sidebar.gitlab).read_bytes(),
            )
            github_meta = json.loads((github / DEPLOYED_MANIFEST_NAME).read_text("utf-8"))
            gitlab_meta = json.loads((gitlab / DEPLOYED_MANIFEST_NAME).read_text("utf-8"))
            self.assertEqual(github_meta["source_commit"], gitlab_meta["source_commit"])
            self.assertEqual(github_meta["source_history_id"], gitlab_meta["source_history_id"])


if __name__ == "__main__":
    unittest.main()
