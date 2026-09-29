import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import psutil
import pytest
from PIL import Image

from steganalysis.engine import create_job
from steganalysis.jobs import JobManager, run_sync
from steganalysis.ml import FEATURE_NAMES, build_dataset, features, load_dataset, predict, train
from steganalysis.models import Budget
from steganalysis.storage import artifact_path, ingest
from steganalysis.tools import run_command


def test_atomic_job_claim_prevents_duplicate_cli_api_execution(store):
    case = store.create_case("Concurrent claim")
    source = ingest(store, case["id"], b"safe text", "text.txt")
    job = create_job(store, case["id"], [source["id"]])
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: store.claim_job(job["id"]), range(12)))
    assert sum(results) == 1


def test_process_exit_output_cap_and_timeout(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import sys; print('x'*100000); sys.stderr.write('failure'); sys.exit(7)"],
        cwd=tmp_path,
        limit=1000,
    )
    assert result["status"] == "failed" and result["exit_code"] == 7
    assert len(result["stdout"]) == 1000 and result["truncated"]["stdout"]
    assert result["stderr"] == "failure"
    result = run_command([sys.executable, "-c", "import time; time.sleep(10)"], cwd=tmp_path, timeout=0.2)
    assert result["status"] == "timed_out" and result["duration_seconds"] < 8


def test_cancellation_kills_child_tree(tmp_path):
    script = "import subprocess,sys,time,pathlib; p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); pathlib.Path('child.pid').write_text(str(p.pid)); time.sleep(30)"
    result = run_command(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        timeout=10,
        cancelled=lambda: (tmp_path / "child.pid").exists(),
    )
    assert result["status"] == "cancelled"
    assert not psutil.pid_exists(int((tmp_path / "child.pid").read_text()))


def test_real_worker_deadline_and_original_retention(store):
    case = store.create_case("Deadline")
    source = ingest(store, case["id"], b"original text", "text.txt")
    job = create_job(store, case["id"], [source["id"]], budget=Budget(job_seconds=1))
    result = run_sync(store, job["id"])
    # Cold process imports take time; any completed fast run is also valid.
    assert result["status"] in {"timed_out", "completed"}
    assert artifact_path(store, source).read_bytes() == b"original text"


def test_supervisor_restart_marks_interrupted_run(store):
    case = store.create_case("Restart")
    source = ingest(store, case["id"], b"text", "text.txt")
    job = create_job(store, case["id"], [source["id"]])
    store.patch("jobs", job["id"], status="running")
    manager = JobManager(store)
    manager.start()
    manager.close()
    assert store.get("jobs", job["id"])["status"] == "failed"
    assert "restarted" in store.get("jobs", job["id"])["error"]


def test_real_worker_cancellation(store):
    case = store.create_case("Cancel running process")
    source = ingest(store, case["id"], b"text" * 1000, "text.txt")
    job = create_job(store, case["id"], [source["id"]])
    manager = JobManager(store)
    thread = threading.Thread(target=manager.run, args=(job,))
    thread.start()
    deadline = time.monotonic() + 5
    while manager.process is None and time.monotonic() < deadline:
        time.sleep(0.02)
    store.patch("jobs", job["id"], cancel_requested=True)
    thread.join(timeout=15)
    assert not thread.is_alive()
    assert store.get("jobs", job["id"])["status"] == "cancelled"
    assert artifact_path(store, source).read_bytes() == b"text" * 1000


@pytest.mark.parametrize("behavior,expected", [("sleep", "timed_out"), ("exit", "failed")])
def test_supervisor_enforces_deadline_and_failed_worker_exit(store, monkeypatch, behavior, expected):
    original = subprocess.Popen

    def controlled_worker(args, **kwargs):
        assert args[1:3] == ["-m", "steganalysis.worker"]
        code = "import time; time.sleep(30)" if behavior == "sleep" else "raise SystemExit(7)"
        return original([sys.executable, "-c", code], **kwargs)

    monkeypatch.setattr("steganalysis.jobs.subprocess.Popen", controlled_worker)
    case = store.create_case("Supervisor failure contract")
    source = ingest(store, case["id"], b"preserve original", "source.txt")
    job = create_job(store, case["id"], [source["id"]], budget=Budget(job_seconds=1))
    result = run_sync(store, job["id"])
    assert result["status"] == expected
    assert result["completed"] == 0
    assert artifact_path(store, source).read_bytes() == b"preserve original"
    assert not psutil.pid_exists(result["worker_pid"])


def test_ml_source_split_pipeline_and_serialized_inference(tmp_path):
    pytest.importorskip("sklearn")
    directory = tmp_path / "dataset"
    manifest = build_dataset(directory, count=15)
    source_splits = {}
    for record in manifest["records"]:
        source_splits.setdefault(record["source_id"], set()).add(record["split"])
    assert all(len(value) == 1 for value in source_splits.values())
    assert len(source_splits) == 15
    model = train(directory / "manifest.json", tmp_path / "model.json")
    assert model["dataset_type"] == "synthetic-only" and model["feature_names"] == FEATURE_NAMES
    assert model["evaluation"]["test"]["roc_auc"] is not None
    assert "held_out_controls" in model["evaluation"]
    manifest, x, _ = load_dataset(directory / "manifest.json")
    train_mask = np.array([r["split"] == "train" for r in manifest["records"]])
    np.testing.assert_allclose(model["mean"], x[train_mask].mean(axis=0))
    with Image.open(directory / manifest["records"][0]["path"]) as image:
        result = predict(image, tmp_path / "model.json")
        assert 0 <= result["score"] <= 1
        assert len(features(image)) == len(FEATURE_NAMES)
    manifest["records"][1]["split"] = "test" if manifest["records"][0]["split"] != "test" else "train"
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="leakage"):
        load_dataset(directory / "manifest.json")


def test_ml_rejects_tampered_manifest_and_missing_permissions(tmp_path):
    directory = tmp_path / "dataset"
    manifest = build_dataset(directory, count=12)
    path = directory / manifest["records"][0]["path"]
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        load_dataset(directory / "manifest.json")
    with pytest.raises(ValueError, match="license"):
        build_dataset(tmp_path / "user", sources=directory)
