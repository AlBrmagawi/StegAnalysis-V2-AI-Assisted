from __future__ import annotations

import hashlib
import json
import wave
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def demo_frame(payload: bytes) -> np.ndarray:
    frame = b"SADEMO1" + len(payload).to_bytes(4, "big") + payload + zlib.crc32(payload).to_bytes(4, "big")
    return np.unpackbits(np.frombuffer(frame, dtype=np.uint8), bitorder="big")


def make_fixtures(destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1729)
    yy, xx = np.mgrid[:320, :480]
    base = (
        np.stack([36 + yy / 9 + xx / 20, 72 + yy / 6 + xx * 0, 83 + xx / 7 + yy * 0], axis=-1)
        .clip(0, 255)
        .astype(np.uint8)
    )
    image = Image.fromarray(base)
    draw = ImageDraw.Draw(image)
    draw.ellipse((330, 32, 390, 92), fill=(192, 222, 204))
    draw.polygon([(0, 255), (130, 97), (285, 302)], fill=(36, 74, 75))
    draw.polygon([(110, 320), (321, 135), (480, 320)], fill=(50, 110, 103))
    draw.polygon([(130, 97), (94, 141), (131, 134), (169, 150)], fill=(202, 224, 208))
    for y in range(275, 320, 8):
        draw.line((0, y, 480, y), fill=(73, 132, 120), width=2)
    image.save(destination / "clean-landscape.png")
    pixels = np.array(image)
    bits = demo_frame(b"Benign StegAnalysis demonstration. Known RGB LSB payload; seed 1729.")
    flat = pixels.reshape(-1)
    flat[: len(bits)] = (flat[: len(bits)] & 254) | bits
    Image.fromarray(pixels).save(destination / "demo-lsb-landscape.png")
    Image.fromarray(rng.integers(0, 256, (160, 240, 3), dtype=np.uint8)).save(
        destination / "clean-noise.jpg", quality=85
    )
    image.convert("L").save(destination / "clean-grayscale.bmp")
    (destination / "demo-unicode.txt").write_text(
        "Investigation note\nThis  document contains a zero\u200bwidth marker.\nA normal explanation\u00a0is typography.\nTrailing spaces here.   \n",
        encoding="utf-8",
    )
    (destination / "clean-text.txt").write_text(
        "A benign control document.\nNo unusual whitespace or invisible characters.\n", encoding="utf-8"
    )
    samples = (np.sin(2 * np.pi * 440 * np.arange(16000) / 8000) * 12000).astype(np.int16)
    for name, stego in (("clean-tone.wav", False), ("demo-sample-lsb.wav", True)):
        values = samples.copy()
        if stego:
            bits = demo_frame(b"Benign sample-level LSB demonstration; integer PCM, 8000 Hz.")
            values[: len(bits)] = (values[: len(bits)] & -2) | bits.astype(np.int16)
        with wave.open(str(destination / name), "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(8000)
            file.writeframes(values.astype("<i2").tobytes())
    for name, attachment in (("clean-document.pdf", False), ("demo-attachment.pdf", True)):
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 18 Tf 60 720 Td (StegAnalysis - benign generated fixture) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(content)
        writer.add_metadata(
            {"/Title": "Benign reproducible demonstration", "/Author": "StegAnalysis fixture generator"}
        )
        if attachment:
            writer.add_attachment(
                "known-attachment.txt", b"Known benign PDF attachment. No program execution.\n"
            )
        writer.write(destination / name)
    base_pdf = destination / "clean-document.pdf"
    updated = PdfWriter(base_pdf, incremental=True)
    updated.add_metadata({"/Subject": "Normal incremental update control"})
    updated.write(destination / "clean-incremental.pdf")
    (destination / "demo-trailing.pdf").write_bytes(base_pdf.read_bytes() + b"\nBENIGN TRAILING FIXTURE\n")
    manifest = {
        "generator": "steganalysis.fixtures.v1",
        "seed": 1729,
        "provenance": "Generated locally from mathematical shapes, tones and text. No committed legacy samples used.",
        "files": [
            {
                "name": p.name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "size": p.stat().st_size,
                "label": "demonstration" if p.name.startswith("demo-") else "clean control",
            }
            for p in sorted(destination.iterdir())
            if p.is_file() and p.name != "manifest.json"
        ],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
