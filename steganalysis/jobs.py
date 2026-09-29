from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from datetime import datetime

import psutil

from .db import Store
from .models import now
from .tools import kill_tree

TERMINAL = {"completed", "failed", "cancelled", "timed_out", "unsupported"}


def finish_interrupted(store: Store, job_id: str, status: str, error: str) -> None:
    store.interrupt_job(job_id, status, error)


class JobManager:
    """One worker, bounded persistent queue. Each job owns a killable parser process."""

    def __init__(self, store: Store):
        self.store = store
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="steganalysis-worker")
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        for job in self.store.list("jobs"):
            if job["status"] == "running":
                pid = job.get("worker_pid")
                if pid:
                    try:
                        process = psutil.Process(pid)
                        # Only kill a surviving worker with the recorded job argument and creation time.
                        if (
                            job["id"] in process.cmdline()
                            and abs(process.create_time() - job.get("worker_created", 0)) < 1
                        ):
                            for child in process.children(recursive=True):
                                child.kill()
                            process.kill()
                    except psutil.Error:
                        pass
                finish_interrupted(
                    self.store,
                    job["id"],
                    "failed",
                    "Service restarted during analysis; retry preserves previous runs",
                )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.thread.join(timeout=10)

    def loop(self) -> None:
        while not self.stop.is_set():
            queued = [j for j in self.store.list("jobs") if j["status"] == "queued"]
            if not queued:
                self.stop.wait(0.2)
                continue
            job = queued[0]
            if job.get("cancel_requested"):
                finish_interrupted(self.store, job["id"], "cancelled", "Cancelled before execution")
                continue
            try:
                self.run(job)
            except Exception as exc:
                if self.process and self.process.poll() is None:
                    kill_tree(self.process)
                finish_interrupted(
                    self.store, job["id"], "failed", f"Worker supervisor: {type(exc).__name__}: {exc}"
                )

    def run(self, job: dict) -> None:
        if not self.store.claim_job(job["id"]):
            return
        workspace = self.store.root / job["case_id"] / "jobs" / job["id"]
        workspace.mkdir(parents=True, exist_ok=True)
        environment = {
            k: v
            for k, v in os.environ.items()
            if not any(
                word in k.upper()
                for word in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "STEG_HOSTED", "STEG_LOCAL")
            )
        }
        environment.update({"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "PYTHONUNBUFFERED": "1"})
        # Installed package imports are independent of evidence workspace contents.
        with (workspace / "worker.log").open("wb") as log:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "steganalysis.worker", str(self.store.root), job["id"]],
                cwd=workspace,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
            self.store.patch(
                "jobs",
                job["id"],
                worker_pid=self.process.pid,
                worker_created=psutil.Process(self.process.pid).create_time(),
            )
            start = time.monotonic()
            while self.process.poll() is None:
                current = self.store.get("jobs", job["id"])
                reason = None
                if self.stop.is_set():
                    reason = ("cancelled", "Service shutdown interrupted analysis; retry available")
                elif current.get("cancel_requested"):
                    reason = ("cancelled", "Cancelled by analyst")
                elif time.monotonic() - start > job["budget"]["job_seconds"]:
                    reason = ("timed_out", "Job wall-clock deadline exceeded")
                elif (workspace / "worker.log").stat().st_size > 1024 * 1024:
                    reason = ("failed", "Worker diagnostic output exceeded 1 MiB")
                else:
                    runs = [
                        r
                        for r in self.store.list("runs", job["case_id"])
                        if r["job_id"] == job["id"] and r["status"] == "running"
                    ]
                    if (
                        runs
                        and (
                            datetime.fromisoformat(now()) - datetime.fromisoformat(runs[-1]["started_at"])
                        ).total_seconds()
                        > job["budget"]["analyzer_seconds"]
                    ):
                        reason = (
                            "timed_out",
                            f"Analyzer {runs[-1]['analyzer']} wall-clock deadline exceeded",
                        )
                    try:
                        worker = psutil.Process(self.process.pid)
                        rss = sum(p.memory_info().rss for p in [worker, *worker.children(recursive=True)])
                        if rss > 1536 * 1024 * 1024:
                            reason = ("failed", "Worker memory budget exceeded (1.5 GiB)")
                    except psutil.NoSuchProcess:
                        pass
                if reason:
                    kill_tree(self.process)
                    finish_interrupted(self.store, job["id"], *reason)
                    return
                self.stop.wait(0.1)
            final = self.store.get("jobs", job["id"])
            if final["status"] not in TERMINAL:
                finish_interrupted(
                    self.store,
                    job["id"],
                    "failed",
                    f"Worker exited {self.process.returncode}; parser did not finish",
                )
            self.process = None


def run_sync(store: Store, job_id: str) -> dict:
    manager = JobManager(store)
    try:
        manager.run(store.get("jobs", job_id))
        while store.get("jobs", job_id)["status"] not in TERMINAL:
            time.sleep(0.1)  # Another supervisor won the atomic claim; wait for its actual result.
    except KeyboardInterrupt:
        store.patch("jobs", job_id, cancel_requested=True)
        if manager.process:
            kill_tree(manager.process)
            finish_interrupted(store, job_id, "cancelled", "CLI interrupted")
    return store.get("jobs", job_id)
