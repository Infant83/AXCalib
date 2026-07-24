from __future__ import annotations

import subprocess

from harness import prep


def test_docling_contract_fails_fast_when_available_memory_is_low(
    monkeypatch,
    capsys,
) -> None:
    called = False

    def unexpected_run(*args, **kwargs) -> int:
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(prep, "_available_memory_bytes", lambda: 1024 * 1024 * 1024)
    monkeypatch.setattr(prep, "_run", unexpected_run)
    monkeypatch.delenv("AXCALIB_DOCLING_MIN_AVAILABLE_MB", raising=False)

    result = prep.run_docling_contract()

    assert result == 3
    assert called is False
    assert "docling: BLOCKED_RESOURCE" in capsys.readouterr().err


def test_docling_contract_uses_bounded_isolated_process(
    monkeypatch,
    tmp_path,
) -> None:
    observed: dict[str, object] = {}

    def recording_run(command: list[str], *, timeout_seconds: int | None = None) -> int:
        observed["command"] = command
        observed["timeout_seconds"] = timeout_seconds
        return 0

    monkeypatch.setattr(prep, "_available_memory_bytes", lambda: 4 * 1024**3)
    monkeypatch.setattr(prep, "_run", recording_run)
    monkeypatch.setattr(prep, "ROOT", tmp_path)
    monkeypatch.setenv("AXCALIB_DOCLING_TIMEOUT_SECONDS", "123")

    result = prep.run_docling_contract()

    assert result == 0
    assert observed["timeout_seconds"] == 123
    command = observed["command"]
    assert isinstance(command, list)
    assert "tests/contract/test_docling_adapter.py" in command


def test_docling_contract_rejects_invalid_guard_configuration(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("AXCALIB_DOCLING_MIN_AVAILABLE_MB", "not-an-integer")

    assert prep.run_docling_contract() == 2
    assert "invalid integer resource-guard configuration" in capsys.readouterr().err


def test_run_returns_124_on_timeout(monkeypatch, capsys) -> None:
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(subprocess, "run", timeout)

    assert prep._run(["python", "-V"], timeout_seconds=1) == 124
    assert "process timed out after 1 seconds" in capsys.readouterr().err
