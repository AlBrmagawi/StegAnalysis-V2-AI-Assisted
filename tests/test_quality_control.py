import hashlib
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from steganalysis.api import create_app
from steganalysis.engine import create_job
from steganalysis.jobs import finish_interrupted
from steganalysis.storage import CaseCapacityError, artifact_path, ingest
from steganalysis.tools import kill_tree


@pytest.mark.parametrize("damage", ["changed", "missing"])
def test_duplicate_upload_verifies_stored_original(store, damage):
    case = store.create_case("Duplicate integrity")
    original = ingest(store, case["id"], b"recorded evidence", "source.txt")
    path = artifact_path(store, original)
    if damage == "changed":
        path.write_bytes(b"changed outside the application")
    else:
        path.unlink()
    with pytest.raises(ValueError, match="integrity"):
        ingest(store, case["id"], b"recorded evidence", "duplicate.txt")
    assert len(store.list("artifacts", case["id"])) == 1
    if damage == "changed":
        assert path.read_bytes() == b"changed outside the application"
    else:
        assert not path.exists()  # Do not conceal missing evidence by replacing it.


def test_concurrent_original_uploads_preserve_one_identity(store):
    case = store.create_case("Concurrent uploads")
    ready = threading.Barrier(8)
    data = b"same bytes from concurrent clients" * 20000

    def upload(index):
        ready.wait(timeout=10)
        return ingest(store, case["id"], data, f"upload-{index}.txt")

    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(upload, range(8)))
    assert len({record["id"] for record in records}) == 1
    assert sum(record.get("duplicate", False) for record in records) == 7
    assert len(store.list("artifacts", case["id"])) == 1
    assert artifact_path(store, records[0]).read_bytes() == data
    assert records[0]["sha256"] == hashlib.sha256(data).hexdigest()


def test_derived_duplicate_bytes_retain_distinct_provenance(store):
    case = store.create_case("Distinct extraction edges")
    source = ingest(store, case["id"], b"original", "source.txt")
    children = [
        ingest(
            store,
            case["id"],
            b"same extracted bytes",
            "child.txt",
            role="extracted",
            parent_id=source["id"],
            location={"object": index},
        )
        for index in (10, 20)
    ]
    assert children[0]["id"] != children[1]["id"]
    assert children[0]["sha256"] == children[1]["sha256"]
    assert children[1]["duplicate_of"] == children[0]["id"]
    assert [child["location"]["object"] for child in children] == [10, 20]


@pytest.mark.parametrize("operation", ["fsync", "link"])
def test_failed_publication_leaves_no_partial_evidence_and_retry_succeeds(store, monkeypatch, operation):
    case = store.create_case("Interrupted object publication")
    data = b"complete evidence" * 1000
    digest = hashlib.sha256(data).hexdigest()
    objects = store.root / case["id"] / "objects"

    def fail(*args):
        if operation == "link":
            assert args[0].read_bytes() == data
        raise OSError("Simulated storage failure")

    with monkeypatch.context() as patch:
        patch.setattr(os, operation, fail)
        with pytest.raises(OSError, match="Simulated storage failure"):
            ingest(store, case["id"], data, "source.txt")
    assert not store.list("artifacts", case["id"])
    assert not (objects / digest).exists()
    assert list(objects.iterdir()) == []
    source = ingest(store, case["id"], data, "retry.txt")
    assert artifact_path(store, source).read_bytes() == data


def test_case_capacity_is_atomic_and_duplicates_remain_idempotent(store):
    case = store.create_case("Bounded concurrent uploads")
    ready = threading.Barrier(6)

    def upload(index):
        ready.wait(timeout=10)
        try:
            return ingest(store, case["id"], f"source {index}".encode(), f"{index}.txt", max_originals=2)
        except CaseCapacityError:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        records = [record for record in pool.map(upload, range(6)) if record]
    assert len(records) == len(store.list("artifacts", case["id"])) == 2
    record = records[0]
    duplicate = ingest(
        store, case["id"], artifact_path(store, record).read_bytes(), "again.txt", max_originals=2
    )
    assert duplicate["duplicate"] and duplicate["id"] == record["id"]
    assert len(list((store.root / case["id"] / "objects").iterdir())) == 2


def test_upload_api_reports_capacity_and_damaged_duplicate(tmp_path):
    app = create_app(tmp_path, start_worker=False)
    store = app.state.store
    case = store.create_case("Upload error contract")
    records = [ingest(store, case["id"], str(index).encode(), f"{index}.txt") for index in range(128)]
    with TestClient(app) as client:
        url = f"/api/cases/{case['id']}/evidence"
        headers = {"X-Steganalysis": "local"}
        assert (
            client.post(url, headers=headers, files={"file": ("extra.txt", b"over capacity")}).status_code
            == 409
        )
        duplicate = client.post(url, headers=headers, files={"file": ("again.txt", b"0")})
        assert duplicate.status_code == 201 and duplicate.json()["duplicate"]
        artifact_path(store, records[0]).write_bytes(b"tampered")
        rejected = client.post(url, headers=headers, files={"file": ("again.txt", b"0")})
        assert rejected.status_code == 400 and "integrity" in rejected.json()["detail"]
        assert len(store.list("artifacts", case["id"])) == 128


@pytest.mark.parametrize("status", ["completed", "failed", "timed_out", "cancelled"])
def test_interruption_preserves_terminal_job_and_event_history(store, status):
    case = store.create_case("Completed before shutdown")
    source = ingest(store, case["id"], b"source", "source.txt")
    job = create_job(store, case["id"], [source["id"]])
    final = store.patch("jobs", job["id"], status=status, finished_at="already finished", error=None)
    store.event(job["id"], status)
    history = store.events(job["id"])
    finish_interrupted(store, job["id"], "cancelled", "Late supervisor shutdown")
    assert store.get("jobs", job["id"]) == final
    assert store.events(job["id"]) == history


def test_interruption_finalizes_only_active_runs_once(store):
    case = store.create_case("Interrupted analysis")
    source = ingest(store, case["id"], b"source", "source.txt")
    job = create_job(store, case["id"], [source["id"]])
    store.claim_job(job["id"])
    for id, status in [("r_done", "completed"), ("r_active", "running")]:
        store.put("runs", {"id": id, "case_id": case["id"], "job_id": job["id"], "status": status})
    finish_interrupted(store, job["id"], "cancelled", "Analyst cancelled")
    finish_interrupted(store, job["id"], "failed", "Late worker exit")
    result = store.snapshot(case["id"])
    assert result["jobs"][0]["status"] == "cancelled"
    assert [run["status"] for run in result["runs"]] == ["completed", "cancelled"]
    assert result["runs"][1]["finished_at"] == result["jobs"][0]["finished_at"]
    assert len(store.events(job["id"])) == 1


def test_snapshot_is_consistent_while_analysis_adds_evidence(store, monkeypatch):
    case = store.create_case("Export during analysis")
    source = ingest(store, case["id"], b"source", "source.txt")
    original_connect = store.connect
    wrote = False

    def concurrent_write(statement):
        nonlocal wrote
        if "SELECT data FROM findings" not in statement or wrote:
            return
        wrote = True
        child = ingest(store, case["id"], b"extracted", "child.txt", role="extracted", parent_id=source["id"])
        store.put("findings", {"id": "f_concurrent", "case_id": case["id"], "supporting": [child["id"]]})

    @contextmanager
    def interleaved_read():
        with original_connect() as db:
            db.set_trace_callback(concurrent_write)
            yield db

    monkeypatch.setattr(store, "connect", interleaved_read)
    snapshot = store.snapshot(case["id"])
    assert wrote, "The writer must commit while the snapshot is being read"
    ids = {artifact["id"] for artifact in snapshot["artifacts"]}
    assert all(set(finding["supporting"]) <= ids for finding in snapshot["findings"])
    current = store.snapshot(case["id"])
    assert len(current["artifacts"]) == 2 and len(current["findings"]) == 1


def test_occupied_server_port_preserves_existing_job(store):
    case = store.create_case("Second server must not interrupt this job")
    source = ingest(store, case["id"], b"source", "source.txt")
    job = create_job(store, case["id"], [source["id"]])
    before = store.patch("jobs", job["id"], status="running")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = subprocess.run(
            [sys.executable, "-m", "steganalysis.cli", "serve", "--port", str(port)],
            env={**os.environ, "STEG_DATA_DIR": str(store.root)},
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    assert result.returncode != 0
    assert store.get("jobs", job["id"]) == before
    assert not store.events(job["id"])


def test_cli_server_serves_http_and_releases_port(tmp_path):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    with (tmp_path / "server.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "steganalysis.cli", "serve", "--port", str(port)],
            env={**os.environ, "STEG_DATA_DIR": str(tmp_path / "case-data")},
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 60
            while True:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/cases", timeout=1) as response:
                        assert response.status == 200 and response.read() == b"[]"
                    break
                except OSError:
                    assert process.poll() is None, (tmp_path / "server.log").read_text()
                    assert time.monotonic() < deadline, "CLI server did not become ready"
                    time.sleep(0.1)
        finally:
            if os.name == "nt":
                kill_tree(process)  # Windows venv launchers can own a second Python process.
            else:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                kill_tree(process)
                process.wait(timeout=10)
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0
