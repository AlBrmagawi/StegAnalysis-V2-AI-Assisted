import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from steganalysis.api import create_app
from steganalysis.assistant import answer, validate_answer
from steganalysis.engine import create_job, execute_job
from steganalysis.models import AssistantRequest, Budget
from steganalysis.storage import artifact_path, contained, ingest
from steganalysis.tools import executable, run_command

HEADERS = {"X-Steganalysis": "local"}


@pytest.fixture
def api_case(tmp_path):
    app = create_app(tmp_path / "api", start_worker=False)
    store = app.state.store
    case = store.create_case("Release contracts")
    source = ingest(store, case["id"], b"A  B\n", "generated.txt")
    job = create_job(store, case["id"], [source["id"]], "quick")
    execute_job(store, job["id"])
    with TestClient(app) as client:
        yield client, store, case["id"], source, job


@pytest.mark.parametrize(
    "name", ["demo-unicode.txt", "demo-attachment.pdf", "demo-lsb-landscape.png", "demo-sample-lsb.wav"]
)
def test_cli_json_and_reports_for_all_supported_kinds(tmp_path, fixtures, name):
    output = tmp_path / "cli"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "steganalysis.cli",
            "analyze",
            "-f",
            str(fixtures / name),
            "--profile",
            "quick",
            "--json",
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["jobs"][0]["status"] == "completed"
    saved = output / report["case"]["id"]
    assert json.loads((saved / "report.json").read_text()) == report
    html = (saved / "report.html").read_text(encoding="utf-8")
    assert report["artifacts"][0]["sha256"] in html
    assert "Mohamed Abdelgalil" in html and "Spooky" in html


def test_compatibility_cli_and_invalid_input(tmp_path, fixtures):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "script.py"),
            "-f",
            str(fixtures / "demo-unicode.txt"),
            "--profile",
            "quick",
            "-o",
            str(tmp_path / "compat"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0 and "completed:" in result.stdout
    result = subprocess.run(
        [sys.executable, "-m", "steganalysis.cli", "analyze", "-f", str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2 and "ordinary file" in result.stderr


def test_doctor_cli_is_structured_and_honest():
    result = subprocess.run(
        [sys.executable, "-m", "steganalysis.cli", "doctor"], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0
    doctor = json.loads(result.stdout)
    assert doctor["versions"]["steganalysis"] == "2.0.0"
    assert set(doctor["tools"]) == {"binwalk", "steghide", "zsteg"}
    assert "Not used" in doctor["legacy_binaries"]


def test_sse_reconnect_and_unknown_route(api_case):
    client, store, case, _, job = api_case
    event_ids = [event["seq"] for event in store.events(job["id"], 0)]
    response = client.get(
        f"/api/cases/{case}/jobs/{job['id']}/events", headers={"Last-Event-ID": str(event_ids[-2])}
    )
    received = [int(line[4:]) for line in response.text.splitlines() if line.startswith("id: ")]
    assert received == [event_ids[-1]]
    assert "event: done" in response.text
    assert client.get("/api/no-such-route").status_code == 404


def test_cross_case_job_review_and_assistant_access(api_case):
    client, store, _, source, job = api_case
    other = store.create_case("Other case")["id"]
    finding = store.list("findings")[0]
    assert client.get(f"/api/cases/{other}/artifacts/{source['id']}/preview").status_code == 404
    assert client.get(f"/api/cases/{other}/jobs/{job['id']}/events").status_code == 404
    assert client.post(f"/api/cases/{other}/jobs/{job['id']}/cancel", headers=HEADERS).status_code == 404
    assert (
        client.patch(
            f"/api/cases/{other}/findings/{finding['id']}", headers=HEADERS, json={"status": "reviewed"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/cases/{other}/assistant",
            headers=HEADERS,
            json={"question": "Explain", "finding_ids": [finding["id"]]},
        ).status_code
        == 400
    )
    report = client.get(f"/api/cases/{other}/report.json").json()
    assert not report["artifacts"] and not report["findings"] and not report["messages"]


def test_upload_stream_size_and_inert_binary_download(api_case, monkeypatch):
    client, _, case, _, _ = api_case
    monkeypatch.setattr("steganalysis.api.MAX_UPLOAD", 4096)
    assert (
        client.post(
            f"/api/cases/{case}/evidence", headers=HEADERS, files={"file": ("large.txt", b"x" * 4097)}
        ).status_code
        == 413
    )
    chunks = [b'{"name":"', b"x" * (1024 * 1024 + 8192), b'"}']
    response = client.post(
        "/api/cases", headers={**HEADERS, "Content-Type": "application/json"}, content=iter(chunks)
    )
    assert response.status_code == 413
    artifact = client.post(
        f"/api/cases/{case}/evidence",
        headers=HEADERS,
        files={"file": ("active.svg", b'<svg onload="alert(1)">\x00</svg>')},
    ).json()
    response = client.get(f"/api/cases/{case}/artifacts/{artifact['id']}/content")
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "mode,status",
    [
        ("timeout", 504),
        ("connection", 502),
        ("empty_choices", 502),
        ("null_choices", 502),
        ("invalid_json", 502),
        ("uncited", 400),
        ("oversized", 400),
    ],
)
def test_provider_failure_contract_and_no_persisted_fabrication(api_case, monkeypatch, mode, status):
    client, store, case, _, _ = api_case
    monkeypatch.setenv("STEG_HOSTED_MODEL", "contract-stub")
    monkeypatch.setenv("STEG_HOSTED_URL", "https://stub.invalid/chat/completions")
    monkeypatch.setenv("STEG_HOSTED_KEY", "test-fixture-only")
    finding = store.list("findings", case)[0]
    body = {"question": "Explain", "finding_ids": [finding["id"]], "provider": "hosted"}
    body["consent_digest"] = client.post(
        f"/api/cases/{case}/assistant/preview", headers=HEADERS, json=body
    ).json()["digest"]
    original = httpx.AsyncClient

    def respond(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("test", request=request)
        if mode == "connection":
            raise httpx.ConnectError("test", request=request)
        if mode == "invalid_json":
            return httpx.Response(200, content=b"not json")
        if mode == "oversized":
            return httpx.Response(200, content=b"x" * (128 * 1024 + 1))
        if mode in ("empty_choices", "null_choices"):
            return httpx.Response(200, json={"choices": [] if mode == "empty_choices" else None})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "facts": [{"text": "Unverified claim", "citations": []}],
                                    "hypotheses": [],
                                    "actions": [],
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "steganalysis.assistant.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(respond)),
    )
    response = client.post(f"/api/cases/{case}/assistant", headers=HEADERS, json=body)
    assert response.status_code == status
    assert not store.list("messages", case)


def test_local_provider_success_remains_grounded(api_case, monkeypatch):
    _, store, case, _, _ = api_case
    monkeypatch.setenv("STEG_LOCAL_MODEL", "contract-stub")
    finding = store.list("findings", case)[0]
    original = httpx.AsyncClient

    def respond(request):
        assert request.url.host == "127.0.0.1" and request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert not body["stream"] and body["format"]["type"] == "object"
        content = {
            "facts": [{"text": finding["interpretation"], "citations": [finding["id"]]}],
            "hypotheses": [],
            "actions": [],
        }
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    monkeypatch.setattr(
        "steganalysis.assistant.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(respond)),
    )
    result = asyncio.run(
        answer(
            store, case, AssistantRequest(question="Explain", finding_ids=[finding["id"]], provider="local")
        )
    )
    assert result["provider"] == "local"
    assert result["content"]["facts"][0]["citations"] == [finding["id"]]
    with pytest.raises(ValueError):
        validate_answer(
            {"facts": [], "hypotheses": [], "actions": [], "tools": [{"shell": "echo injected"}]},
            {finding["id"]},
        )


def test_symlink_rejection(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    target = root / "real.txt"
    target.write_text("safe")
    alias = root / "link.txt"
    try:
        alias.symlink_to(target)
    except OSError:
        pytest.skip("Creating real symlinks requires Windows developer mode or elevated permission")
    with pytest.raises(ValueError, match="Symlinks"):
        contained(root, "link.txt")


def test_repository_executable_rejection(monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("steganalysis.tools.shutil.which", lambda _: str(repo / "ensteg"))
    assert executable("ensteg") is None


def test_external_process_strips_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_RELEASE_API_KEY", "do-not-forward")
    monkeypatch.setenv("TEST_RELEASE_TOKEN", "do-not-forward")
    result = run_command(
        [
            sys.executable,
            "-c",
            "import os; print(os.getenv('TEST_RELEASE_API_KEY')); print(os.getenv('TEST_RELEASE_TOKEN'))",
        ],
        cwd=tmp_path,
    )
    assert result["status"] == "completed" and result["stdout"].splitlines() == ["None", "None"]


def test_pdf_nested_extraction_respects_depth(store, fixtures):
    case = store.create_case("Bounded recursion")
    source = ingest(store, case["id"], (fixtures / "demo-attachment.pdf").read_bytes(), "attachment.pdf")
    job = create_job(store, case["id"], [source["id"]], "standard", Budget(max_depth=0))
    execute_job(store, job["id"])
    assert all(run["artifact_id"] == source["id"] for run in store.list("runs"))
    assert artifact_path(store, source).read_bytes() == (fixtures / "demo-attachment.pdf").read_bytes()
