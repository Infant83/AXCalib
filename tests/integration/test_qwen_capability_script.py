import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from axcalib.cli import app

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pipelines" / "probe_qwen35_capabilities.py"
GENERIC_SCRIPT = ROOT / "scripts" / "pipelines" / "probe_multimodal_capabilities.py"


@contextmanager
def _exact_qwen_server(
    reported_model: str = "Qwen/Qwen3.5-397B-A17B",
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    captured: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
            length = int(self.headers["Content-Length"])
            body = json.loads(self.rfile.read(length))
            captured.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "body": body,
                }
            )
            content = body["messages"][1]["content"]
            is_vision = any(item.get("type") == "image_url" for item in content)
            output = (
                {
                    "left_panel": "red",
                    "right_panel": "blue",
                    "two_equal_panels": True,
                }
                if is_vision
                else {
                    "probe_token": "AXCALIB_MULTIMODAL_TEXT_OK",
                    "structured_output": True,
                }
            )
            envelope = {
                "id": f"fake-qwen-{len(captured)}",
                "model": reported_model,
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(output),
                            "reasoning_content": "PRIVATE_REASONING_MUST_NOT_PERSIST",
                        }
                    }
                ],
            }
            payload = json.dumps(envelope).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = server.server_address
        host, port = str(address[0]), int(address[1])
        yield f"http://{host}:{port}/v1", captured
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_script_uses_canonical_openai_environment_and_confirms_exact_model() -> None:
    with _exact_qwen_server() as (base_url, captured):
        env = os.environ.copy()
        env.update(
            {
                "OPENAI_API_KEY": "dummy-onprem-secret",
                "OPENAI_BASE_URL": base_url,
                "OPENAI_MODEL": "Qwen3.5-397B-A17B",
                "OPENAI_API_MODE": "chat_completions",
            }
        )
        env.pop("OPENAPI_API_KEY", None)
        env.pop("OPENAPI_BASE_URL", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["deployment_ready"] is True
    assert report["checkpoint_identity_confirmed"] is True
    assert report["structured_text_passed"] is True
    assert report["structured_vision_passed"] is True
    assert len(captured) == 2
    assert all(item["path"] == "/v1/chat/completions" for item in captured)
    assert all(item["authorization"] == "Bearer dummy-onprem-secret" for item in captured)
    serialized = json.dumps(captured)
    assert "dummy-onprem-secret" not in json.dumps([item["body"] for item in captured])
    assert "PRIVATE_REASONING_MUST_NOT_PERSIST" not in result.stdout
    assert "response_format" in serialized


def test_cli_exposes_the_same_exact_qwen_probe(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    output = tmp_path / "qwen-capability.json"
    with _exact_qwen_server() as (base_url, captured):
        monkeypatch.setenv("OPENAI_API_KEY", "dummy-cli-secret")
        monkeypatch.setenv("OPENAI_BASE_URL", base_url)
        monkeypatch.setenv("OPENAI_MODEL", "Qwen3.5-397B-A17B")
        monkeypatch.setenv("OPENAI_API_MODE", "chat_completions")
        result = CliRunner().invoke(
            app,
            [
                "verify",
                "qwen",
                "--expected-checkpoint",
                "Qwen3.5-397B-A17B",
                "--scope",
                "deployment",
                "--output",
                str(output),
            ],
        )

    assert result.exit_code == 0, result.output
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["deployment_ready"] is True
    assert report["structured_text_passed"] is True
    assert report["structured_vision_passed"] is True
    assert len(captured) == 2
    assert "dummy-cli-secret" not in output.read_text(encoding="utf-8")
    assert "PRIVATE_REASONING_MUST_NOT_PERSIST" not in result.output


def test_cli_fails_closed_without_canonical_environment(monkeypatch: Any) -> None:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "OPENAPI_API_KEY",
        "OPENAPI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    result = CliRunner().invoke(app, ["verify", "qwen", "--text-only"])

    assert result.exit_code == 2
    assert "OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL" in result.output
    assert "Traceback" not in result.output


def test_generic_script_checks_an_alternate_proxy_without_claiming_deployment() -> None:
    with _exact_qwen_server("glm-4.5v") as (base_url, captured):
        env = os.environ.copy()
        env.update(
            {
                "OPENAI_API_KEY": "dummy-proxy-secret",
                "OPENAI_BASE_URL": base_url,
                "OPENAI_MODEL": "glm/glm-4.5v",
                "OPENAI_API_MODE": "chat_completions",
                "OPENAI_STRUCTURED_OUTPUT_MODE": "json_object",
            }
        )
        result = subprocess.run(
            [sys.executable, str(GENERIC_SCRIPT)],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["validation_scope"] == "provider_proxy"
    assert report["scope_passed"] is True
    assert report["structured_text_passed"] is True
    assert report["structured_vision_passed"] is True
    assert report["deployment_ready"] is False
    assert len(captured) == 2
    assert all(
        "Return exactly one valid JSON object" in item["body"]["messages"][0]["content"]
        for item in captured
    )


def test_script_fails_closed_when_canonical_environment_is_missing() -> None:
    env = os.environ.copy()
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "OPENAPI_API_KEY",
        "OPENAPI_BASE_URL",
    ):
        env.pop(name, None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--text-only"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert "OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL" in result.stderr
