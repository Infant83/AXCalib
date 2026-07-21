from pathlib import Path

import pytest

from axcalib import AXCalib
from axcalib.pipelines import PipelineRegistry, TwoGatePptxPipeline


def test_registry_is_allowlisted_and_rejects_duplicates(tmp_path: Path) -> None:
    client = AXCalib(tmp_path)
    assert client.registry.keys() == (
        ("dossier.freeze", "v1alpha1"),
        ("dossier.initialize", "v1alpha1"),
        ("dossier.update", "v1alpha1"),
        ("education-program-runtime", "v1alpha1"),
        ("two-gate-pptx", "v1alpha1"),
    )
    pipeline = client.registry.create("two-gate-pptx", "v1alpha1")
    assert isinstance(pipeline, TwoGatePptxPipeline)

    with pytest.raises(KeyError, match="not allowlisted"):
        client.registry.create("arbitrary.import.path", "latest")

    registry = PipelineRegistry()
    registry.register("safe", "v1", lambda: pipeline)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("safe", "v1", lambda: pipeline)
