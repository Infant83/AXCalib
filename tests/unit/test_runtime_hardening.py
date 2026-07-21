import json
from pathlib import Path

import pytest

from axcalib.dossier import FileLockTimeoutError, exclusive_file_lock
from axcalib.notifications.base import NotificationEvent, RecordingNotifier
from axcalib.notifications.outbox import DurableNotificationOutbox
from axcalib.runtime import RuntimeConfigError, load_runtime_config

ROOT = Path(__file__).resolve().parents[2]


class FailingNotifier:
    def send(self, event: NotificationEvent) -> None:
        del event
        raise RuntimeError("offline delivery failed")


def test_outbox_records_failure_and_can_retry(tmp_path: Path) -> None:
    event = NotificationEvent(
        "registration_admin_approval_requested",
        "project-001",
        "registration",
        revision=7,
        report_ref="report-registration-001",
    )
    failed = DurableNotificationOutbox(tmp_path / "outbox", FailingNotifier())
    with pytest.raises(RuntimeError, match="delivery failed"):
        failed.send(event)
    record = failed.entries()[0]
    assert record["delivery_status"] == "failed"
    assert record["attempts"] == 1
    assert record["revision"] == 7
    assert record["report_ref"] == "report-registration-001"
    assert record["last_error"] == "RuntimeError"
    assert "offline delivery failed" not in json.dumps(record)

    recording = RecordingNotifier()
    recovered = DurableNotificationOutbox(tmp_path / "outbox", recording)
    assert recovered.retry_failed() == 1
    assert recording.events == [event]
    assert recovered.entries()[0]["delivery_status"] == "recorded"
    recovered.send(event)
    assert recording.events == [event]


def test_effective_config_manifest_excludes_api_key_value(tmp_path: Path) -> None:
    loaded = load_runtime_config(
        ROOT / "config" / "axcalib.expert.example.toml",
        manifest_path=tmp_path / "effective-config.json",
        environ={
            "OPENAI_API_KEY": "must-not-be-written",
            "OPENAI_MODEL": "Qwen3.5-397B-A17B",
        },
    )
    text = (tmp_path / "effective-config.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert "must-not-be-written" not in text
    assert manifest["safe_environment"]["OPENAI_API_KEY"] == {"present": True}
    assert loaded.reference.profile_name == "onprem"


def test_local_file_lock_times_out_instead_of_racing(tmp_path: Path) -> None:
    target = tmp_path / "record.yaml"
    with exclusive_file_lock(target):
        with pytest.raises(FileLockTimeoutError):
            with exclusive_file_lock(
                target,
                timeout_seconds=0.01,
                poll_seconds=0.001,
            ):
                raise AssertionError("unreachable")


def test_runtime_loader_rejects_unknown_keys_before_writing_manifest(
    tmp_path: Path,
) -> None:
    config = tmp_path / "invalid.toml"
    config.write_text(
        (ROOT / "config" / "axcalib.toml").read_text(encoding="utf-8")
        + "\n[workflow]\nskip_hitl = true\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "effective-config.json"

    with pytest.raises(RuntimeConfigError, match="unknown runtime config keys"):
        load_runtime_config(config, manifest_path=manifest)
    assert not manifest.exists()


def test_runtime_loader_rejects_literal_secret_in_environment_field(
    tmp_path: Path,
) -> None:
    config = tmp_path / "literal-secret.toml"
    config.write_text(
        (ROOT / "config" / "axcalib.expert.example.toml")
        .read_text(encoding="utf-8")
        .replace('api_key_env = "OPENAI_API_KEY"', 'api_key_env = "sk-not-an-env-name"'),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeConfigError, match="environment variable"):
        load_runtime_config(config, manifest_path=tmp_path / "manifest.json")
