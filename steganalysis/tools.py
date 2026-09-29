from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

TOOLS = {
    "binwalk": {
        "version_args": ["--version"],
        "purpose": "Read-only signature scan; automatic extractors disabled",
    },
    "zsteg": {"version_args": ["--version"], "purpose": "PNG/BMP inspection; no password guessing"},
    "steghide": {
        "version_args": ["--version"],
        "purpose": "Non-interactive carrier information; no extraction/passphrase guessing",
    },
}


def executable(name: str) -> str | None:
    path = shutil.which(name)
    # Never execute binaries in this repository or the evidence directory.
    if path and Path(path).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        return None
    return path


def kill_tree(process: subprocess.Popen) -> None:
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs([parent, *children], timeout=3)
    except psutil.NoSuchProcess:
        pass
    process.wait(timeout=5)


def run_command(
    args: list[str],
    *,
    cwd: Path,
    timeout: float = 15,
    limit: int = 65536,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict[str, Any]:
    started = time.monotonic()
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(secret in k.upper() for secret in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    }
    env.update({"NO_COLOR": "1", "LC_ALL": "C"})
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}

    def drain(stream, key):
        while chunk := stream.read(4096):
            remaining = max(0, limit - len(buffers[key]))
            buffers[key].extend(chunk[:remaining])
            truncated[key] |= len(chunk) > remaining
        stream.close()

    threads = [
        threading.Thread(target=drain, args=(stream, key), daemon=True)
        for stream, key in ((process.stdout, "stdout"), (process.stderr, "stderr"))
    ]
    for thread in threads:
        thread.start()
    status = "completed"
    while process.poll() is None:
        if cancelled() or time.monotonic() - started > timeout:
            status = "cancelled" if cancelled() else "timed_out"
            kill_tree(process)
            break
        time.sleep(0.05)
    for thread in threads:
        thread.join(timeout=2)
    if status == "completed" and process.returncode != 0:
        status = "failed"
    return {
        "invocation": args,
        "exit_code": process.returncode,
        "status": status,
        "duration_seconds": round(time.monotonic() - started, 4),
        "truncated": truncated,
        **{k: bytes(v).decode("utf-8", "replace") for k, v in buffers.items()},
    }


def tool_health(name: str) -> dict[str, Any]:
    path = executable(name)
    return {"available": bool(path), "path": path, "purpose": TOOLS[name]["purpose"]}


def doctor() -> dict[str, Any]:
    from .engine import versions

    result: dict[str, Any] = {
        "versions": versions(),
        "tools": {},
        "legacy_binaries": "Not used; provenance/license unresolved",
        "foremost": "Unavailable: automatic carving is replaced with bounded parser-based PDF extraction",
        "stegsolve": "Replaced by native channels, bit planes and residual views",
    }
    for name, spec in TOOLS.items():
        health = tool_health(name)
        if health["available"]:
            health["version_check"] = run_command(
                [health["path"], *spec["version_args"]], cwd=Path.home(), timeout=3, limit=4096
            )
        result["tools"][name] = health
    return result
