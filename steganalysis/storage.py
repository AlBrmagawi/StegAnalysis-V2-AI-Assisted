from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .db import Store
from .models import now, uid


class LimitError(ValueError):
    pass


class CaseCapacityError(LimitError):
    pass


def verify_object(path: Path, digest: str) -> None:
    try:
        with path.open("rb") as file:
            valid = hashlib.file_digest(file, "sha256").hexdigest() == digest
    except OSError as exc:
        raise ValueError("Stored evidence integrity check failed: object is unavailable") from exc
    if not valid:
        raise ValueError("Stored evidence integrity check failed: hash mismatch")


def publish_object(path: Path, data: bytes, digest: str) -> None:
    """Publish complete bytes without ever overwriting an existing evidence object."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            verify_object(path, digest)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def sniff(data: bytes) -> tuple[str, str]:
    if data.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if data.startswith(b"BM"):
        return "image", "image/bmp"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio", "audio/wav"
    try:
        text = data.decode("utf-8-sig")
        if "\x00" not in text and all(ord(c) >= 32 or c in "\r\n\t\f" for c in text):
            return "text", "text/plain"
    except UnicodeDecodeError:
        pass
    return "binary", "application/octet-stream"


def safe_name(name: str) -> str:
    return re.sub(r"[^\w.() -]", "_", name.replace("\\", "/").split("/")[-1])[:160] or "evidence.bin"


def contained(root: Path, relative: str) -> Path:
    path = root / relative
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Storage path escapes its case")
    # Reject even in-root symlink traversal: evidence files are ordinary files only.
    for part in [path, *path.parents]:
        if part == root.parent:
            break
        if part.is_symlink():
            raise ValueError("Symlinks are not accepted in evidence storage")
    return resolved


def artifact_path(store: Store, artifact: dict[str, Any]) -> Path:
    case_root = contained(store.root, artifact["case_id"])
    return contained(case_root, artifact["path"])


def ingest(
    store: Store,
    case_id: str,
    data: bytes,
    name: str,
    *,
    parent_id: str | None = None,
    run_id: str | None = None,
    role: str = "original",
    location: dict[str, Any] | None = None,
    depth: int = 0,
    metadata: dict[str, Any] | None = None,
    max_bytes: int = 32 * 1024 * 1024,
    max_originals: int | None = None,
) -> dict[str, Any]:
    store.get("cases", case_id)
    if not data:
        raise ValueError("Empty files are not evidence inputs")
    if len(data) > max_bytes:
        raise LimitError(f"File exceeds the {max_bytes} byte limit")
    digest = hashlib.sha256(data).hexdigest()
    # Serialize duplicate detection and publication across API, CLI and parser processes.
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = [
            json.loads(row[0])
            for row in db.execute("SELECT data FROM artifacts WHERE case_id=? ORDER BY rowid", (case_id,))
        ]
        matching = [item for item in existing if item["sha256"] == digest]
        case_root = contained(store.root, case_id)
        path = contained(case_root, f"objects/{digest}")
        if matching or path.exists():
            verify_object(path, digest)
        # Originals deduplicate; derived records retain every provenance edge.
        if role == "original":
            duplicate = next((item for item in matching if item["role"] == "original"), None)
            if duplicate:
                return {**duplicate, "duplicate": True}
            if max_originals is not None and sum(a["role"] == "original" for a in existing) >= max_originals:
                raise CaseCapacityError(
                    f"Case has reached {max_originals} original files; create another case"
                )
        if not path.exists():
            publish_object(path, data, digest)
        kind, mime = sniff(data)
        record = {
            "id": uid("a"),
            "case_id": case_id,
            "name": safe_name(name),
            "sha256": digest,
            "size": len(data),
            "kind": kind,
            "mime": mime,
            "path": f"objects/{digest}",
            "parent_id": parent_id,
            "run_id": run_id,
            "role": role,
            "location": location or {},
            "depth": depth,
            "metadata": metadata or {},
            "created_at": now(),
            "duplicate_of": matching[0]["id"] if matching else None,
        }
        db.execute(
            "INSERT INTO artifacts(id,case_id,data) VALUES(?,?,?)",
            (record["id"], case_id, json.dumps(record, ensure_ascii=True, allow_nan=False)),
        )
    return record
