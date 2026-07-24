"""Machine-check the offline EX-01..EX-12 usage and negative-case catalog."""

from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "examples" / "catalog.yaml"
PIPELINE_SCRIPTS = ROOT / "scripts" / "pipelines"


def test_example_catalog_is_complete_offline_and_points_to_executable_evidence() -> None:
    raw = YAML(typ="safe").load(CATALOG.read_text(encoding="utf-8"))

    assert raw["schema_version"] == "axcalib.example-catalog/v1alpha1"
    assert raw["default_mode"] == "synthetic_offline"
    examples = raw["examples"]
    assert [item["id"] for item in examples] == [f"EX-{index:02d}" for index in range(1, 13)]
    for item in examples:
        for key in (
            "title",
            "persona",
            "fixture",
            "command",
            "expected",
            "evidence",
            "cleanup",
        ):
            assert isinstance(item[key], str) and item[key].strip()
        command = item["command"]
        assert "uv run --no-sync" in command
        assert "--live-model" not in command
        assert "OPENAI_API_KEY" not in command
        assert "http://" not in command and "https://" not in command
        for evidence in item["evidence"].split(" + "):
            path_text = evidence.split("::", maxsplit=1)[0]
            assert (ROOT / path_text).is_file(), (item["id"], path_text)


def test_repository_pipeline_scripts_bootstrap_src_before_importing_axcalib() -> None:
    for path in sorted(PIPELINE_SCRIPTS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "from axcalib" not in source and "import axcalib" not in source:
            continue
        bootstrap = source.find("sys.path.insert")
        first_import = min(
            index
            for index in (source.find("from axcalib"), source.find("import axcalib"))
            if index >= 0
        )
        assert bootstrap >= 0 and bootstrap < first_import, path.name
