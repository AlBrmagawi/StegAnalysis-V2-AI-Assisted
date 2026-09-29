import json

import pytest
from PIL import Image

from steganalysis.engine import create_job, execute_job
from steganalysis.ml import build_dataset, load_dataset, predict, train
from steganalysis.storage import artifact_path, ingest


@pytest.mark.parametrize("status", ["completed", "failed", "timed_out", "cancelled"])
def test_external_adapter_preserves_bounded_output_and_actual_status(analyze, store, monkeypatch, status):
    calls = []
    monkeypatch.setattr("steganalysis.analyzers.executable", lambda _: "/trusted/stub/binwalk")

    def command(args, **kwargs):
        calls.append((args, kwargs))
        version = "--version" in args
        return {
            "status": "completed" if version else status,
            "invocation": args,
            "exit_code": 0 if version or status == "completed" else 7,
            "stdout": "Contract stub 1.0"
            if version
            else "Untrusted tool text <script>never execute</script>",
            "stderr": "",
            "duration_seconds": 0.01,
            "truncated": {"stdout": False, "stderr": False},
        }

    monkeypatch.setattr("steganalysis.analyzers.run_command", command)
    result = analyze(b"Safe text for adapter contract", "tool-input.txt", profile="deep")
    run = next(r for r in result["runs"] if r["analyzer"] == "binwalk")
    assert run["status"] == status
    artifact = next(a for a in result["artifacts"] if a["name"] == "binwalk-output.json")
    captured = json.loads(artifact_path(store, artifact).read_bytes())
    assert captured["tool_version"]["stdout"] == "Contract stub 1.0"
    assert captured["status"] == status
    assert calls[1][1]["timeout"] <= 20 and calls[1][1]["limit"] == 65536
    assert not any(arg in {"-e", "--extract"} for arg in calls[1][0])
    assert any(f["title"] == "binwalk completed" for f in result["findings"]) == (status == "completed")


@pytest.fixture(scope="module")
def trained_model(tmp_path_factory):
    pytest.importorskip("sklearn")
    root = tmp_path_factory.mktemp("trained-contract-model")
    manifest = build_dataset(root / "dataset", count=15, seed=2026)
    model = root / "model.json"
    train(root / "dataset" / "manifest.json", model)
    return model, root / "dataset" / manifest["records"][0]["path"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("feature_version", "unsupported"),
        ("scale", [0] * 18),
        ("coef", [float("nan")] * 18),
        ("threshold", 1),
    ],
)
def test_invalid_model_is_rejected(trained_model, tmp_path, field, value):
    source, image = trained_model
    model = json.loads(source.read_text())
    model[field] = value
    modified = tmp_path / "invalid.json"
    modified.write_text(json.dumps(model))
    with Image.open(image) as pixels, pytest.raises(ValueError):
        predict(pixels, modified)


def test_real_trained_model_integration_is_separate_from_heuristics(store, trained_model, monkeypatch):
    model, image = trained_model
    monkeypatch.setenv("STEG_ML_MODEL", str(model))
    monkeypatch.setattr("steganalysis.analyzers.executable", lambda _: None)
    case = store.create_case("Experimental inference contract")
    source = ingest(store, case["id"], image.read_bytes(), image.name)
    job = create_job(store, case["id"], [source["id"]], "deep")
    execute_job(store, job["id"])
    run = next(r for r in store.list("runs") if r["analyzer"] == "experimental-ml")
    assert run["status"] == "completed"
    finding = next(f for f in store.list("findings") if f["category"] == "experimental")
    assert 0 <= finding["measurements"]["score"] <= 1
    assert "not calibrated" in finding["limitations"]
    assert finding["supporting"] and finding["source_sha256"] == source["sha256"]


def test_dataset_manifest_rejects_traversal(tmp_path):
    manifest = build_dataset(tmp_path / "dataset", count=12)
    manifest["records"][0]["path"] = "../outside.png"
    path = tmp_path / "dataset" / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="escapes"):
        load_dataset(path)
