import hashlib
import io
import struct
import wave

import numpy as np
import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, EncodedStreamObject, NameObject, NumberObject

from steganalysis.analyzers import entropy, framed_payload, pair_chi_square
from steganalysis.engine import REGISTRY, create_job, execute_job, load_analyzers
from steganalysis.fixtures import demo_frame
from steganalysis.models import Budget
from steganalysis.storage import LimitError, artifact_path, contained, ingest, sniff


def image_bytes(mode="RGB", format="PNG"):
    image = Image.new(mode, (32, 32))
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def test_registry_contract():
    load_analyzers()
    assert len({a.id for a in REGISTRY}) == len(REGISTRY)
    for analyzer in REGISTRY:
        description = analyzer.describe()
        assert description["version"] == "2.0.0"
        assert "max_pixels" in description["configuration_schema"]["properties"]
        assert isinstance(description["capability"]["available"], bool)


@pytest.mark.parametrize(
    "name,kind,mime",
    [
        ("clean-landscape.png", "image", "image/png"),
        ("clean-noise.jpg", "image", "image/jpeg"),
        ("clean-grayscale.bmp", "image", "image/bmp"),
        ("demo-attachment.pdf", "pdf", "application/pdf"),
        ("demo-sample-lsb.wav", "audio", "audio/wav"),
        ("demo-unicode.txt", "text", "text/plain"),
    ],
)
def test_signature(fixtures, name, kind, mime):
    assert sniff((fixtures / name).read_bytes()) == (kind, mime)


def test_duplicate_and_immutable_ingestion(store):
    case = store.create_case("Duplicates")
    original = ingest(store, case["id"], b"safe source", "../../bad\\source.txt")
    duplicate = ingest(store, case["id"], b"safe source", "renamed.txt")
    assert duplicate["duplicate"] and duplicate["id"] == original["id"]
    assert original["name"] == "source.txt"
    assert artifact_path(store, original).read_bytes() == b"safe source"
    assert original["sha256"] == hashlib.sha256(b"safe source").hexdigest()
    with pytest.raises(ValueError):
        contained(store.root, "../escape")
    with pytest.raises(LimitError):
        ingest(store, case["id"], b"A" * 10000, "large", max_bytes=1024)
    with pytest.raises(ValueError):
        ingest(store, case["id"], b"", "empty")


def test_integrity_change_fails(store):
    case = store.create_case("Integrity")
    artifact = ingest(store, case["id"], b"original bytes", "source.txt")
    artifact_path(store, artifact).write_bytes(b"tampered bytes")
    job = create_job(store, case["id"], [artifact["id"]])
    execute_job(store, job["id"])
    assert store.get("jobs", job["id"])["status"] == "failed"
    assert all(r["status"] == "failed" for r in store.list("runs"))
    assert not store.list("findings")


@pytest.mark.parametrize("mode", ["1", "L", "LA", "P", "RGB", "RGBA"])
def test_pixel_modes(analyze, mode):
    snapshot = analyze(image_bytes(mode), mode + ".png", profile="standard")
    assert snapshot["jobs"][0]["status"] == "completed"
    run = next(r for r in snapshot["runs"] if r["analyzer"] == "image")
    assert run["result"]["source_mode"] == mode
    assert not any(f["category"] == "recovered" for f in snapshot["findings"])
    assert all(
        a["mime"] == "image/png" for a in snapshot["artifacts"] if a["kind"] == "image" and a["parent_id"]
    )


def test_image_positive_and_provenance(analyze, fixtures, store):
    snapshot = analyze((fixtures / "demo-lsb-landscape.png").read_bytes(), "demo.png", profile="standard")
    recovered = next(f for f in snapshot["findings"] if f["category"] == "recovered")
    artifact = store.get("artifacts", recovered["supporting"][0])
    assert b"Benign StegAnalysis demonstration" in artifact_path(store, artifact).read_bytes()
    source = snapshot["artifacts"][0]
    assert artifact["parent_id"] == source["id"]
    assert recovered["source_sha256"] == source["sha256"]
    assert recovered["location"]["plane"] == 0
    for finding in snapshot["findings"]:
        assert finding["limitations"] and finding["analyzer_version"]
        assert all(any(a["id"] == id for a in snapshot["artifacts"]) for id in finding["supporting"])


def test_crc_rejects_corruption():
    bits = demo_frame(b"known")
    assert framed_payload(bits) == b"known"
    bits[-1] ^= 1
    assert framed_payload(bits) is None


def test_statistics_assumptions():
    assert entropy(b"") == 0
    assert entropy(b"A" * 100) == 0
    assert entropy(bytes(range(256)) * 50) == 8
    equal = pair_chi_square(np.tile(np.arange(256, dtype=np.uint8), 50))
    assert equal["p_value"] == 1 and equal["statistic"] == 0
    assert pair_chi_square(np.zeros(1000, dtype=np.uint8))["p_value"] < 1e-100
    assert pair_chi_square(np.array([0, 1], dtype=np.uint8))["p_value"] is None


def test_high_entropy_control_not_claimed_hidden(analyze):
    snapshot = analyze(bytes(range(256)) * 50, "clean-noise.bin")
    assert not any(f["category"] in ("recovered", "heuristic") for f in snapshot["findings"])
    assert any(r["status"] == "unsupported" for r in snapshot["runs"])


def test_image_limits_and_16bit(analyze):
    snapshot = analyze(image_bytes(), "image.png", max_pixels=20)
    assert next(r for r in snapshot["runs"] if r["analyzer"] == "image")["status"] == "failed"
    stream = io.BytesIO()
    Image.fromarray(np.zeros((32, 32), dtype=np.uint16)).save(stream, format="PNG")
    snapshot = analyze(stream.getvalue(), "16bit.png")
    assert next(r for r in snapshot["runs"] if r["analyzer"] == "image")["status"] == "unsupported"


def test_extraction_budget_fails_honestly(analyze, fixtures):
    snapshot = analyze(
        (fixtures / "clean-landscape.png").read_bytes(), "image.png", profile="standard", max_artifacts=2
    )
    assert snapshot["jobs"][0]["status"] == "failed"
    assert len(snapshot["artifacts"]) <= 3
    assert any("budget" in (r["error"] or "") for r in snapshot["runs"])


def test_jpeg_scope(analyze, fixtures):
    snapshot = analyze((fixtures / "clean-noise.jpg").read_bytes(), "image.jpg")
    finding = next(f for f in snapshot["findings"] if f["analyzer"] == "image")
    assert "no DCT" in finding["limitations"]
    assert not any(f["category"] == "recovered" for f in snapshot["findings"])


def test_pdf_attachment_and_incremental(analyze, fixtures, store):
    snapshot = analyze((fixtures / "demo-attachment.pdf").read_bytes(), "document.pdf")
    assert snapshot["jobs"][0]["status"] == "completed"
    attachment = next(a for a in snapshot["artifacts"] if a["name"] == "known-attachment.txt")
    assert artifact_path(store, attachment).read_bytes().startswith(b"Known benign PDF attachment")
    assert attachment["location"] == {"pdf_attachment_name": "known-attachment.txt"}
    assert any(a["location"].get("page") == 1 for a in snapshot["artifacts"])
    incremental = analyze((fixtures / "clean-incremental.pdf").read_bytes(), "incremental.pdf")
    assert not any(f["title"] == "Bytes after final PDF EOF marker" for f in incremental["findings"])
    assert next(r for r in incremental["runs"] if r["analyzer"] == "pdf")["result"][
        "incremental_previous_xref"
    ]
    trailing = analyze((fixtures / "demo-trailing.pdf").read_bytes(), "trailing.pdf")
    assert any(f["title"] == "Bytes after final PDF EOF marker" for f in trailing["findings"])


def test_pdf_encryption_malformed_and_image_only(analyze):
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    buffer = io.BytesIO()
    writer.write(buffer)
    blank = analyze(buffer.getvalue(), "blank.pdf")
    assert any(f["title"] == "No extractable text on page 1" for f in blank["findings"])
    writer.encrypt("requires-password")
    buffer = io.BytesIO()
    writer.write(buffer)
    encrypted = analyze(buffer.getvalue(), "encrypted.pdf")
    assert next(r for r in encrypted["runs"] if r["analyzer"] == "pdf")["status"] == "unsupported"
    malformed = analyze(b"%PDF-1.7\nmalformed", "malformed.pdf")
    assert next(r for r in malformed["runs"] if r["analyzer"] == "pdf")["status"] == "failed"


def test_pdf_image_actual_encoding(analyze):
    writer = PdfWriter()
    page = writer.add_blank_page(200, 200)
    obj = EncodedStreamObject()
    obj._data = image_bytes("RGB", "JPEG")
    obj.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(32),
            NameObject("/Height"): NumberObject(32),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
            NameObject("/Filter"): NameObject("/DCTDecode"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im1"): writer._add_object(obj)})}
    )
    buffer = io.BytesIO()
    writer.write(buffer)
    snapshot = analyze(buffer.getvalue(), "image.pdf")
    image = next(a for a in snapshot["artifacts"] if a["role"] == "extracted" and a["kind"] == "image")
    assert image["mime"] == "image/jpeg" and image["name"].endswith(".jpg")
    assert image["location"]["image_object"] is not None


def test_text_exact_location_and_clean_control(analyze, fixtures):
    snapshot = analyze("é\u200b X  Y\n".encode(), "unicode.txt")
    finding = next(f for f in snapshot["findings"] if f["title"] == "Invisible Unicode characters")
    assert finding["location"]["character_index"] == 1
    assert finding["location"]["utf8_byte_offset"] == 2
    assert finding["location"]["line"] == 1 and finding["location"]["column"] == 2
    assert finding["category"] == "heuristic" and finding["contradictory"]
    clean = analyze((fixtures / "clean-text.txt").read_bytes(), "clean.txt")
    assert not any(f["category"] == "heuristic" for f in clean["findings"])


def test_audio_recovery_and_control(analyze, fixtures):
    for name, expected in (("demo-sample-lsb.wav", True), ("clean-tone.wav", False)):
        snapshot = analyze((fixtures / name).read_bytes(), name)
        assert snapshot["jobs"][0]["status"] == "completed"
        assert any(f["category"] == "recovered" for f in snapshot["findings"]) == expected
        result = next(r for r in snapshot["runs"] if r["analyzer"] == "audio")["result"]
        assert result["sample_rate"] == 8000 and result["frames_inspected"] == 16000
        assert result["waveform"] and result["spectrogram_id"]


def test_float_wav_is_explicitly_unsupported(analyze):
    fmt = struct.pack("<HHIIHH", 3, 1, 8000, 32000, 4, 32)
    body = b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", 512) + bytes(512)
    snapshot = analyze(b"RIFF" + struct.pack("<I", len(body)) + body, "float.wav")
    run = next(r for r in snapshot["runs"] if r["analyzer"] == "audio")
    assert run["status"] == "unsupported" and "integer PCM" in run["error"]


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_pcm_sample_widths(analyze, width):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as file:
        file.setnchannels(2)
        file.setsampwidth(width)
        file.setframerate(8000)
        file.writeframes(b"\x00" * 2048 * width)
    snapshot = analyze(buffer.getvalue(), "pcm.wav")
    assert next(r for r in snapshot["runs"] if r["analyzer"] == "audio")["status"] == "completed"


def test_missing_tools_are_not_negative_findings(analyze, monkeypatch):
    monkeypatch.setattr("steganalysis.analyzers.executable", lambda _: None)
    snapshot = analyze(image_bytes(), "image.png", profile="deep")
    for run in snapshot["runs"]:
        if run["analyzer"] in {"binwalk", "zsteg", "experimental-ml"}:
            assert run["status"] == "skipped"
    assert not any(f["analyzer"] in {"binwalk", "zsteg", "steghide"} for f in snapshot["findings"])


def test_reruns_preserve_fingerprints_and_reviews(store):
    case = store.create_case("History")
    source = ingest(store, case["id"], b"A  B", "text.txt")
    for _ in range(2):
        job = create_job(store, case["id"], [source["id"]], "quick")
        execute_job(store, job["id"])
    findings = store.list("findings")
    assert len(findings) == 4 and len({f["id"] for f in findings}) == 4
    assert len({f["fingerprint"] for f in findings}) == 2
    assert len(store.list("jobs")) == 2


def test_cancelled_job_does_not_run(store):
    case = store.create_case("Cancellation")
    source = ingest(store, case["id"], b"A  B", "text.txt")
    job = create_job(store, case["id"], [source["id"]], "quick", Budget())
    store.patch("jobs", job["id"], cancel_requested=True)
    execute_job(store, job["id"])
    assert store.get("jobs", job["id"])["status"] == "cancelled"
    assert not store.list("runs")
