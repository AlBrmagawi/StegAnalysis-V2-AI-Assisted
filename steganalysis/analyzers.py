from __future__ import annotations

import io
import itertools
import json
import os
import re
import unicodedata
import warnings
import wave
import zlib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from scipy.signal import spectrogram
from scipy.stats import chi2

from .engine import CancelledError, Context, SkippedError, UnsupportedError, register
from .pdf import ProvenancePdfReader
from .storage import LimitError, sniff
from .tools import TOOLS, executable, run_command


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
    p = counts[counts > 0] / len(data)
    return float(-(p * np.log2(p)).sum())


def json_artifact(ctx: Context, value: Any, name: str, location: dict | None = None):
    return ctx.derive(
        json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False).encode(),
        name,
        "visualization",
        location or {},
    )


@register("bytes", "Identity, strings & entropy", ("*",))
def analyze_bytes(ctx: Context) -> dict[str, Any]:
    data = ctx.read()
    b = ctx.budget
    windows: list[dict[str, Any]] = []
    for start in range(0, len(data), b.entropy_stride):
        ctx.check()
        if len(windows) >= 4096:
            break
        segment = data[start : start + b.entropy_window]
        windows.append({"offset": start, "length": len(segment), "entropy": round(entropy(segment), 6)})
    strings = []
    for match in re.finditer(rb"[\x20-\x7e]{6,}", data):
        strings.append(
            {
                "offset": match.start(),
                "length": len(match.group()),
                "text": match.group()[:240].decode("ascii"),
            }
        )
        if len(strings) >= 300:
            break
    stats = {
        "sha256": ctx.artifact["sha256"],
        "bytes": len(data),
        "signature_mime": ctx.artifact["mime"],
        "entropy": entropy(data),
        "window": b.entropy_window,
        "stride": b.entropy_stride,
        "windows": windows,
        "windows_truncated": len(windows) >= 4096,
        "strings": strings,
        "strings_capped": len(strings) >= 300,
    }
    artifact = json_artifact(ctx, stats, "byte-inspection.json", {"byte_start": 0, "byte_end": len(data)})
    ctx.finding(
        "File identity and byte distribution",
        f"{len(data):,} bytes; Shannon entropy {stats['entropy']:.3f} bits per byte.",
        measurements={"entropy": stats["entropy"], "bytes": len(data)},
        supporting=[artifact["id"]],
        location={"byte_start": 0, "byte_end": len(data)},
        limitations="Entropy describes byte distribution, not the probability of steganography. Compressed and encrypted content commonly has high entropy.",
        contradictory="Normal compression, random noise and encryption can produce the same distribution.",
    )
    suffix = ctx.artifact["name"].lower().rsplit(".", 1)[-1]
    expected = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "bmp": "image/bmp",
        "wav": "audio/wav",
        "pdf": "application/pdf",
        "txt": "text/plain",
    }
    if suffix in expected and expected[suffix] != ctx.artifact["mime"]:
        ctx.finding(
            "Filename and signature differ",
            f"The .{suffix} extension differs from the measured {ctx.artifact['mime']} signature.",
            category="heuristic",
            contradictory="The file may simply have been renamed.",
        )
    if ctx.artifact["kind"] == "binary":
        ctx.finding(
            "No supported format signature",
            "Only byte-level inspection is available for this artifact.",
            limitations="The payload was not decoded. An unsupported signature is not proof of hidden content.",
        )
    return stats


def text_indicators(ctx: Context, text: str, location: dict[str, Any] | None = None) -> dict[str, Any]:
    findings = []
    byte_offset = 0
    line = column = 1
    for index, char in enumerate(text):
        ctx.check() if index % 4096 == 0 else None
        category = unicodedata.category(char)
        if (
            category == "Cf"
            or char in "\u00a0\u034f\u180e\u2028\u2029"
            or (category == "Cc" and char not in "\n\r\t")
        ):
            findings.append(
                {
                    "character_index": index,
                    "utf8_byte_offset": byte_offset,
                    "line": line,
                    "column": column,
                    "codepoint": f"U+{ord(char):04X}",
                    "name": unicodedata.name(char, "CONTROL"),
                    "context": text[max(0, index - 25) : index + 26],
                }
            )
        byte_offset += len(char.encode("utf-8"))
        if char == "\n":
            line, column = line + 1, 1
        else:
            column += 1
        if len(findings) >= 200:
            break
    whitespace = [
        {
            "character_index": m.start(),
            "line": text.count("\n", 0, m.start()) + 1,
            "length": len(m.group()),
            "sequence": repr(m.group()),
        }
        for m in itertools.islice(re.finditer(r"[ \t]{2,}|[ \t]+(?=\r?$)", text, re.M), 200)
    ]
    result = {
        "characters_inspected": min(len(text), 1_000_000),
        "invisible_characters": findings,
        "whitespace_sequences": whitespace,
        "locations": "1-based line/column; 0-based Unicode index and UTF-8 byte offset in extracted text",
        "truncated": len(findings) == 200 or len(whitespace) == 200,
    }
    a = json_artifact(ctx, result, "text-locations.json", location)
    if findings:
        ctx.finding(
            "Invisible Unicode characters",
            f"Found {len(findings)} invisible/control characters in inspected text.",
            category="heuristic",
            location={**(location or {}), **findings[0]},
            supporting=[a["id"], ctx.artifact["id"]],
            contradictory="Bidirectional writing, typography and normal document generation legitimately use these characters.",
            limitations="Locations refer to UTF-8 text, not PDF byte offsets. The list is capped at 200 indicators.",
        )
    if whitespace:
        ctx.finding(
            "Unusual whitespace sequences",
            f"Found {len(whitespace)} repeated or trailing whitespace sequences.",
            category="heuristic",
            location={**(location or {}), **whitespace[0]},
            supporting=[a["id"]],
            contradictory="Indentation, alignment and PDF text layout often create this pattern.",
            limitations="A whitespace pattern is an indicator to inspect; it does not establish steganography or decode a message.",
        )
    if not findings and not whitespace:
        ctx.finding(
            "Text inspection completed",
            "No targeted invisible characters or repeated/trailing whitespace in inspected text.",
            supporting=[a["id"]],
            limitations="Other text-based encodings and semantic concealment are outside this check.",
        )
    return result


@register("text", "Unicode & whitespace inspection", ("text",))
def analyze_text(ctx: Context) -> dict[str, Any]:
    data = ctx.read()
    # UTF-8 BOM is kept so byte references remain exact.
    text = data.decode("utf-8")
    result = text_indicators(ctx, text[:1_000_000], ctx.artifact.get("location"))
    result["input_truncated"] = len(text) > 1_000_000
    return result


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def pair_chi_square(values: np.ndarray) -> dict[str, Any]:
    counts = np.bincount(values.astype(np.uint8).ravel(), minlength=256).reshape(128, 2)
    eligible = counts.sum(axis=1) >= 10  # Expected count at least five in each bin.
    paired = counts[eligible].astype(float)
    if not len(paired):
        return {"statistic": None, "p_value": None, "degrees_of_freedom": 0, "eligible_pairs": 0}
    expected = paired.sum(axis=1, keepdims=True) / 2
    statistic = float(((paired - expected) ** 2 / expected).sum())
    return {
        "statistic": statistic,
        "p_value": float(chi2.sf(statistic, len(paired))),
        "degrees_of_freedom": len(paired),
        "eligible_pairs": int(eligible.sum()),
    }


def framed_payload(values: np.ndarray) -> bytes | None:
    # Explicit demo framing; no invented general-purpose decoder.
    raw = np.packbits(values.ravel()[:1_000_000].astype(np.uint8) & 1, bitorder="big").tobytes()
    if not raw.startswith(b"SADEMO1") or len(raw) < 15:
        return None
    size = int.from_bytes(raw[7:11], "big")
    if size > 65536 or len(raw) < 15 + size:
        return None
    payload = raw[11 : 11 + size]
    return payload if zlib.crc32(payload) == int.from_bytes(raw[11 + size : 15 + size], "big") else None


def recover_demo(ctx: Context, values: np.ndarray, location: dict[str, Any]) -> None:
    payload = framed_payload(values)
    if payload:
        derived = ctx.derive(payload, "recovered-demo-payload.txt", "extracted", location)
        ctx.finding(
            "Verified demonstration payload recovered",
            "Recovered a SADEMO1 frame with valid CRC-32 from sequential least-significant bits.",
            category="recovered",
            supporting=[derived["id"]],
            location=location,
            limitations="This decoder recognizes only the documented benign demo framing, not arbitrary steganographic schemes. CRC is an integrity check, not authentication.",
        )


@register("image", "Image channels, residuals & LSB statistics", ("image",))
def analyze_image(ctx: Context) -> dict[str, Any]:
    data = ctx.read()
    if data.startswith(b"\x89PNG") and len(data) > 24 and data[24] > 8:
        raise UnsupportedError(
            "16-bit PNG: byte inspection available; pixel analysis requires <=8-bit channels"
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        Image.MAX_IMAGE_PIXELS = ctx.budget.max_pixels
        with Image.open(io.BytesIO(data), formats=("PNG", "JPEG", "BMP")) as source:
            if source.width * source.height > ctx.budget.max_pixels:
                raise LimitError("Decoded image dimensions exceed pixel budget")
            if source.mode not in ("1", "L", "LA", "P", "RGB", "RGBA", "CMYK"):
                raise UnsupportedError(f"Unsupported pixel mode: {source.mode}")
            source.load()
            mode, format_name = source.mode, source.format
            metadata = {
                str(k): str(v)[:2000] for k, v in source.info.items() if k not in ("icc_profile", "exif")
            }
            exif = {str(k): str(v)[:500] for k, v in source.getexif().items()}
            alpha = source.mode in ("RGBA", "LA") or "transparency" in source.info
            image = source.convert("RGBA" if alpha else "RGB")
    pixels = np.array(image)
    names = list("RGBA" if alpha else "RGB")
    preview = ctx.derive(
        png_bytes(image),
        "decoded-original.png",
        "preview",
        {"pixel_domain": "decoded", "mode": mode},
        {"view": "original"},
    )
    histograms = {
        name: np.bincount(pixels[:, :, i].ravel(), minlength=256).tolist() for i, name in enumerate(names)
    }
    bounded = pixels[:, :, :3].reshape(-1)[: ctx.budget.max_samples]
    statistics = pair_chi_square(bounded)
    result = {
        "format": format_name,
        "source_mode": mode,
        "analysis_mode": image.mode,
        "width": image.width,
        "height": image.height,
        "alpha": alpha,
        "metadata": metadata,
        "exif": exif,
        "histograms": histograms,
        "samples_inspected": len(bounded),
        "lsb_one_fraction": float((bounded & 1).mean()),
        "pair_chi_square": statistics,
        "preview_id": preview["id"],
        "domain": "decoded pixels",
    }
    stats = json_artifact(ctx, result, "image-statistics.json")
    limitation = "Null hypothesis: eligible adjacent value bins have equal expected counts (>=5 per bin). Pixel dependence and sampling invalidate calibrated detection probabilities; the p-value is NOT the probability of hidden data."
    if format_name == "JPEG":
        limitation += (
            " JPEG pixels are decoded/quantized; no DCT coefficient-domain steganalysis is performed."
        )
    ctx.finding(
        "Decoded pixel and LSB measurements",
        f"{image.width} × {image.height} {mode} image; measured LSB one-fraction {result['lsb_one_fraction']:.4f} across {len(bounded):,} channel values.",
        supporting=[stats["id"], preview["id"]],
        location={"channels": "RGB", "plane": 0, "sample_start": 0, "sample_end": len(bounded)},
        measurements={"lsb_one_fraction": result["lsb_one_fraction"], **statistics},
        limitations=limitation,
        contradictory="Sensor noise, dithering, compression and normal image processing affect the same statistics.",
    )
    recover_demo(
        ctx,
        bounded,
        {"channels": "RGB", "plane": 0, "order": "row-major interleaved RGB, MSB-first packed bytes"},
    )
    if ctx.job["profile"] != "quick":
        planes = range(8) if ctx.job["profile"] == "deep" else (0, 1, 7)
        for i, name in enumerate(names):
            channel = pixels[:, :, i]
            ctx.derive(
                png_bytes(Image.fromarray(channel)),
                f"channel-{name}.png",
                "visualization",
                {"channel": name},
                {"view": "channel", "channel": name},
            )
            for plane in planes:
                ctx.derive(
                    png_bytes(Image.fromarray(((channel >> plane) & 1) * 255)),
                    f"{name}-bit-{plane}.png",
                    "visualization",
                    {"channel": name, "plane": plane},
                    {"view": "bit-plane", "channel": name, "plane": plane},
                )
        gray = ImageOps.grayscale(image)
        median = np.asarray(gray.filter(ImageFilter.MedianFilter(3)), dtype=np.int16)
        residual = np.clip(abs(np.asarray(gray, dtype=np.int16) - median) * 8, 0, 255).astype(np.uint8)
        for name, view in (
            ("grayscale", gray),
            ("negative", ImageOps.invert(image.convert("RGB"))),
            ("residual", Image.fromarray(residual)),
        ):
            ctx.derive(
                png_bytes(view),
                name + ".png",
                "visualization",
                {"transform": name, "residual_gain": 8 if name == "residual" else None},
                {"view": name},
            )
    return result


@register("pdf", "PDF structure & bounded extraction", ("pdf",))
def analyze_pdf(ctx: Context) -> dict[str, Any]:
    from pypdf import overwrite_configuration

    stream_limit = min(32 * 1024 * 1024, ctx.budget.max_extracted_bytes)
    overwrite_configuration(
        maximum_declared_stream_length=stream_limit,
        array_based_stream_maximum_output_length=stream_limit,
        zlib_maximum_output_length=stream_limit,
        lzw_maximum_output_length=stream_limit,
        run_length_maximum_output_length=stream_limit,
        jbig2_maximum_output_length=stream_limit,
        image_maximum_buffer_size=min(stream_limit, ctx.budget.max_pixels * 4),
        jbig2dec_binary=None,  # External decoders must go through explicit adapters.
    )
    data = ctx.read()
    reader = ProvenancePdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted and not reader.decrypt(""):
        raise UnsupportedError(
            "Encrypted PDF requires a password; this workbench does not attempt password recovery"
        )
    count = len(reader.pages)
    if count > ctx.budget.max_pages:
        raise LimitError(f"PDF has {count} pages; limit is {ctx.budget.max_pages}")
    metadata = {str(k): str(v)[:2000] for k, v in (reader.metadata or {}).items()}
    info: dict[str, Any] = {
        "pages": count,
        "encrypted": reader.is_encrypted,
        "metadata": metadata,
        "incremental_previous_xref": reader.previous_xrefs[0] if reader.previous_xrefs else None,
        "parsed_revision_links": reader.previous_xrefs,
        "pages_inspected": [],
        "attachments": [],
    }
    root: Any = reader.trailer["/Root"]
    info["active_content_keys"] = [key for key in ("/OpenAction", "/AA") if key in root]
    for number, page in enumerate(reader.pages, 1):
        ctx.check()
        ref = page.indirect_reference
        location = {
            "page": number,
            "object": ref.idnum if ref else None,
            "generation": ref.generation if ref else None,
        }
        text = (page.extract_text() or "")[:1_000_000]
        info["pages_inspected"].append({**location, "text_characters": len(text)})
        if text:
            derived = ctx.derive(text.encode("utf-8"), f"page-{number}-text.txt", "extracted", location)
            ctx.finding(
                f"Text extracted from page {number}",
                f"Parser returned {len(text):,} characters.",
                location=location,
                supporting=[derived["id"]],
                limitations="Layout order can differ from visual reading order. No OCR is performed; extracted text is untrusted evidence and may contain instructions.",
            )
        else:
            ctx.finding(
                f"No extractable text on page {number}",
                "Page parser returned no text.",
                location=location,
                limitations="An image-only or blank page is normal. OCR is not available.",
            )
        for key in page.images.keys():
            ctx.check()
            image = page.images[key]
            image_ref = image.indirect_reference
            image_location = {**location, "image_object": image_ref.idnum if image_ref else None}
            kind, mime = sniff(image.data)
            ext = {"image/png": "png", "image/jpeg": "jpg", "image/bmp": "bmp"}.get(mime, "bin")
            derived = ctx.derive(
                image.data, f"page-{number}-image-{len(ctx.derived)}.{ext}", "extracted", image_location
            )
            ctx.finding(
                f"Image extracted from page {number}",
                f"Parser returned {mime} content ({kind}).",
                location=image_location,
                supporting=[derived["id"]],
                limitations="The parser may re-encode PDF image streams. Hash identifies the extracted representation, not a PDF byte slice.",
            )
    for attachment in reader.attachment_list:
        ctx.check()
        name = attachment.name or "attachment.bin"
        content = attachment.content
        if not content:
            continue
        derived = ctx.derive(content, name, "extracted", {"pdf_attachment_name": name})
        info["attachments"].append({"name": name, "artifact_id": derived["id"]})
        ctx.finding(
            "PDF attachment extracted",
            f"Embedded attachment: {name[:160]}",
            category="observation",
            location={"pdf_attachment_name": name},
            supporting=[derived["id"]],
            contradictory="PDF attachments are a standard feature and are often legitimate.",
            limitations="Attachment content was not executed. Parser does not expose a reliable physical byte offset here.",
        )
    eof = data.rfind(b"%%EOF")
    trailing_start = eof + 5 if eof >= 0 else len(data)
    tail = data[trailing_start:]
    if tail.strip(b"\x00\t\n\r "):
        derived = ctx.derive(
            tail, "pdf-trailing-data.bin", "extracted", {"byte_start": trailing_start, "byte_end": len(data)}
        )
        ctx.finding(
            "Bytes after final PDF EOF marker",
            f"{len(tail)} bytes follow the final lexical %%EOF marker.",
            category="heuristic",
            supporting=[derived["id"]],
            location={"byte_start": trailing_start, "byte_end": len(data)},
            limitations="This checks only the final lexical marker after successful parser inspection. Earlier EOF markers are allowed in incremental updates. Marker placement alone is not conclusive.",
            contradictory="Transport padding, application quirks and benign appended data can explain this.",
        )
    structural = json_artifact(ctx, info, "pdf-structure.json")
    ctx.finding(
        "PDF structure inspected",
        f"{count} pages, {len(info['attachments'])} attachments; previous cross-reference pointer {'present' if info['incremental_previous_xref'] else 'absent'}.",
        supporting=[structural["id"]],
        limitations="Object parsing uses pypdf; no JavaScript, embedded program, link or attachment is executed. Incremental revisions are normal PDF behavior.",
    )
    return info


@register("audio", "PCM waveform, spectrum & sample bits", ("audio",))
def analyze_audio(ctx: Context) -> dict[str, Any]:
    try:
        wav_file = wave.open(io.BytesIO(ctx.read()), "rb")
    except wave.Error as exc:
        if "unknown format" in str(exc):
            raise UnsupportedError(f"Unsupported WAV encoding: {exc}; integer PCM only") from exc
        raise
    with wav_file as wav:
        channels, width, rate, frames = (
            wav.getnchannels(),
            wav.getsampwidth(),
            wav.getframerate(),
            wav.getnframes(),
        )
        if wav.getcomptype() != "NONE" or width not in (1, 2, 3, 4) or channels > 8 or not rate:
            raise UnsupportedError(
                "Only uncompressed integer PCM WAV, 8/16/24/32-bit, 1–8 channels is supported"
            )
        count = min(frames, ctx.budget.max_samples // channels)
        raw = wav.readframes(count)
    if not raw:
        raise UnsupportedError("WAV contains no readable sample frames")
    if width == 1:
        integer = np.frombuffer(raw, np.uint8).astype(np.int32) - 128
    elif width == 3:
        parts = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        integer = parts[:, 0] | (parts[:, 1] << 8) | (parts[:, 2] << 16)
        integer = (integer ^ 0x800000) - 0x800000
    else:
        integer = np.frombuffer(raw, dtype="<i2" if width == 2 else "<i4").astype(np.int64)
    samples = integer.reshape(-1, channels)
    normalized = samples.astype(float) / (2 ** (width * 8 - 1))
    mono = normalized.mean(axis=1)
    step = max(1, len(mono) // 800)
    waveform = [
        {"time": i / rate, "min": float(mono[i : i + step].min()), "max": float(mono[i : i + step].max())}
        for i in range(0, len(mono), step)
    ]
    nperseg = min(512, len(mono))
    frequency, times, power = spectrogram(mono, fs=rate, nperseg=nperseg, noverlap=nperseg // 2)
    db = 10 * np.log10(power + 1e-12)
    scaled = np.clip((db + 100) / 100, 0, 1)
    color = np.stack([scaled * 70, scaled * 220, scaled * 190], axis=-1).astype(np.uint8)
    plot = Image.fromarray(np.flipud(color)).resize((800, 280))
    loc = {
        "sample_start": 0,
        "sample_end": len(samples),
        "time_start": 0,
        "time_end": len(samples) / rate,
        "channels": channels,
    }
    spec = ctx.derive(
        png_bytes(plot),
        "spectrogram.png",
        "visualization",
        loc,
        {
            "view": "spectrogram",
            "frequency_max": rate / 2,
            "duration": len(samples) / rate,
            "db_range": [-100, 0],
        },
    )
    planes = [
        {"plane": bit, "one_fraction": float(((integer >> bit) & 1).mean())}
        for bit in range(min(8, width * 8))
    ]
    result = {
        "channels": channels,
        "sample_width_bits": width * 8,
        "sample_rate": rate,
        "frames": frames,
        "duration": frames / rate,
        "frames_inspected": len(samples),
        "truncated": len(samples) < frames,
        "waveform": waveform,
        "bit_planes": planes,
        "spectrogram_id": spec["id"],
        "spectrum": {"frequency_bins": len(frequency), "time_bins": len(times), "nperseg": nperseg},
    }
    stats = json_artifact(ctx, result, "audio-statistics.json", loc)
    # Sample-level bit raster, distinct from container bytes. Rows are successive 256-sample chunks.
    bits = ((integer[:65536] & 1) * 255).astype(np.uint8)
    padded = np.pad(bits, (0, (-len(bits)) % 256)).reshape(-1, 256)
    plane = ctx.derive(
        png_bytes(Image.fromarray(padded)),
        "sample-lsb.png",
        "visualization",
        {**loc, "plane": 0, "sample_values_shown": len(bits)},
        {"view": "sample-bit-plane"},
    )
    ctx.finding(
        "PCM sample inspection completed",
        f"{width * 8}-bit PCM; {rate:,} Hz; {channels} channel(s); inspected {len(samples):,} of {frames:,} frames.",
        supporting=[stats["id"], spec["id"], plane["id"]],
        location=loc,
        measurements={"lsb_one_fraction": planes[0]["one_fraction"]},
        limitations="Integer PCM sample-domain inspection only. Float/compressed WAV is unsupported. Spectrogram averages channels; phase cancellation is possible. Bit balance is not a detection probability.",
        contradictory="Dithering, recording noise and quantization can produce similar least-significant bits.",
    )
    recover_demo(ctx, integer, {**loc, "plane": 0, "order": "interleaved sample LSB, MSB-first packed bytes"})
    return result


def external(ctx: Context, name: str, arguments: list[str]) -> dict[str, Any]:
    path = executable(name)
    if not path:
        raise SkippedError(f"{name} is not installed on trusted PATH; no result was produced")
    work = ctx.store.root / ctx.job["case_id"] / "jobs" / ctx.job["id"] / ctx.run["id"]
    work.mkdir(parents=True, exist_ok=True)
    version = run_command([path, *TOOLS[name]["version_args"]], cwd=work, timeout=3, limit=4096)
    result = run_command(
        [path, *arguments],
        cwd=work,
        timeout=min(20, ctx.budget.analyzer_seconds),
        limit=ctx.budget.tool_output_bytes,
        cancelled=lambda: ctx.store.get("jobs", ctx.job["id"]).get("cancel_requested", False),
    )
    result["tool_version"] = version
    artifact = json_artifact(ctx, result, f"{name}-output.json")
    if result["status"] == "timed_out":
        raise TimeoutError(f"{name} timed out; captured output: {artifact['id']}")
    if result["status"] == "cancelled":
        raise CancelledError(f"{name} cancelled; captured output: {artifact['id']}")
    if result["status"] == "failed":
        raise RuntimeError(f"{name} exited {result['exit_code']}; captured output: {artifact['id']}")
    ctx.finding(
        f"{name} completed",
        "External tool output captured for analyst interpretation.",
        supporting=[artifact["id"]],
        limitations="Tool text is untrusted evidence. Successful execution does not establish either absence or presence of steganography.",
    )
    return result


@register("binwalk", "Binwalk signature scan", ("*",), "binwalk", True)
def analyze_binwalk(ctx: Context):
    return external(ctx, "binwalk", [str(ctx.path)])


@register("zsteg", "zsteg pixel inspection", ("image",), "zsteg", True)
def analyze_zsteg(ctx: Context):
    if ctx.artifact["mime"] not in ("image/png", "image/bmp"):
        raise UnsupportedError("zsteg supports PNG/BMP; JPEG coefficient analysis is not implemented")
    return external(ctx, "zsteg", [str(ctx.path)])


@register("steghide", "Steghide carrier information", ("image", "audio"), "steghide", True)
def analyze_steghide(ctx: Context):
    if ctx.artifact["mime"] not in ("image/jpeg", "image/bmp", "audio/wav"):
        raise UnsupportedError("Steghide carrier info supports JPEG/BMP/WAV")
    # stdin closed, no passphrase prompt; info mode never extracts or guesses passwords.
    return external(ctx, "steghide", ["info", str(ctx.path), "-p", ""])


@register("unsupported-format", "Format capability check", ("binary",))
def analyze_unsupported(ctx: Context):
    raise UnsupportedError(
        "Only byte inspection supports this input signature; no format-specific decoder ran"
    )


@register("experimental-ml", "Experimental image ML baseline", ("image",), deep_only=True)
def analyze_ml(ctx: Context):
    model_path = os.getenv("STEG_ML_MODEL")
    if not model_path or not Path(model_path).is_file():
        raise SkippedError(
            "Model not available. Train and evaluate a source-separated dataset, then configure STEG_ML_MODEL."
        )
    from .ml import predict

    with Image.open(io.BytesIO(ctx.read()), formats=("PNG", "JPEG", "BMP")) as image:
        result = predict(image, Path(model_path))
    artifact = json_artifact(ctx, result, "experimental-model-output.json")
    ctx.finding(
        "Experimental LSB model inference",
        f"Logistic model score {result['score']:.4f}; {result['experimental_label']}. Evaluated dataset: {result['dataset_type']}.",
        category="experimental",
        supporting=[artifact["id"]],
        measurements={"score": result["score"], "threshold": result["threshold"]},
        location={"image_region": "top-left up to 256×256 decoded RGB pixels"},
        limitations=result["limitations"],
        contradictory="Unseen sources, noisy images, compression and other embedding methods may cause false positives or misses.",
    )
    return result
