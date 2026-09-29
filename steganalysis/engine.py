from __future__ import annotations

import hashlib
import importlib.metadata
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import __version__
from .db import Store
from .models import Budget, Status, now, stable_id, uid
from .storage import LimitError, artifact_path, ingest


class UnsupportedError(ValueError):
    pass


class SkippedError(ValueError):
    pass


class CancelledError(Exception):
    pass


@dataclass(frozen=True)
class Analyzer:
    id: str
    name: str
    kinds: tuple[str, ...]
    function: Callable[[Context], dict[str, Any]]
    dependency: str | None = None
    deep_only: bool = False

    def describe(self) -> dict[str, Any]:
        from .tools import tool_health

        return {
            "id": self.id,
            "name": self.name,
            "kinds": self.kinds,
            "version": __version__,
            "dependency": self.dependency,
            "capability": tool_health(self.dependency) if self.dependency else {"available": True},
            "deep_only": self.deep_only,
            "configuration_schema": Budget.model_json_schema(),
        }


REGISTRY: list[Analyzer] = []


def register(
    id: str, name: str, kinds: tuple[str, ...], dependency: str | None = None, deep_only: bool = False
):
    def decorator(function: Callable[[Context], dict[str, Any]]):
        REGISTRY.append(Analyzer(id, name, kinds, function, dependency, deep_only))
        return function

    return decorator


class Context:
    def __init__(self, store: Store, job: dict[str, Any], artifact: dict[str, Any], run: dict[str, Any]):
        self.store, self.job, self.artifact, self.run = store, job, artifact, run
        self.budget = Budget.model_validate(job["budget"])
        self.path = artifact_path(store, artifact)
        self.started = time.monotonic()
        self.derived: list[dict[str, Any]] = []

    def check(self) -> None:
        if self.store.get("jobs", self.job["id"]).get("cancel_requested"):
            raise CancelledError("Cancelled by analyst")
        if time.monotonic() - self.started > self.budget.analyzer_seconds:
            raise TimeoutError("Analyzer deadline exceeded")

    def read(self) -> bytes:
        self.check()
        if self.path.stat().st_size > self.budget.max_file_bytes:
            raise LimitError("Input exceeds configured byte limit")
        data = self.path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.artifact["sha256"]:
            raise ValueError("Evidence integrity check failed; original bytes changed")
        return data

    def derive(
        self,
        data: bytes,
        name: str,
        role: str,
        location: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.check()
        artifacts = [
            a
            for a in self.store.list("artifacts", self.job["case_id"])
            if a.get("run_id")
            in {
                r["id"] for r in self.store.list("runs", self.job["case_id"]) if r["job_id"] == self.job["id"]
            }
        ]
        if (
            len(artifacts) >= self.budget.max_artifacts
            or sum(a["size"] for a in artifacts) + len(data) > self.budget.max_extracted_bytes
        ):
            raise LimitError("Derived artifact count/byte budget reached; partial results retained")
        artifact = ingest(
            self.store,
            self.job["case_id"],
            data,
            name,
            parent_id=self.artifact["id"],
            run_id=self.run["id"],
            role=role,
            location=location,
            depth=self.artifact["depth"] + 1,
            metadata=metadata,
            max_bytes=self.budget.max_extracted_bytes,
        )
        self.derived.append(artifact)
        return artifact

    def finding(
        self,
        title: str,
        interpretation: str,
        *,
        category: str = "observation",
        location: dict[str, Any] | None = None,
        limitations: str = "This observation alone does not establish hidden content.",
        supporting: list[str] | None = None,
        contradictory: str = "",
        measurements: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        location = location or {}
        fingerprint = stable_id("f", self.artifact["sha256"], self.run["analyzer"], title, location)
        item = {
            "id": stable_id("f", fingerprint, self.run["id"]),
            "fingerprint": fingerprint,
            "case_id": self.job["case_id"],
            "job_id": self.job["id"],
            "run_id": self.run["id"],
            "artifact_id": self.artifact["id"],
            "source_sha256": self.artifact["sha256"],
            "analyzer": self.run["analyzer"],
            "analyzer_version": __version__,
            "parameters": self.run["parameters"],
            "title": title,
            "interpretation": interpretation,
            "category": category,
            "location": location,
            "limitations": limitations,
            "supporting": supporting or [self.artifact["id"]],
            "contradictory": contradictory,
            "measurements": measurements or {},
            "created_at": now(),
            "review": {"status": "unreviewed", "note": ""},
        }
        return self.store.put("findings", item)


def load_analyzers() -> None:
    from . import analyzers  # noqa: F401


def versions() -> dict[str, str]:
    return {
        "steganalysis": __version__,
        **{p: importlib.metadata.version(p) for p in ("pillow", "pypdf", "numpy", "scipy")},
    }


def execute_job(store: Store, job_id: str) -> None:
    load_analyzers()
    job = store.get("jobs", job_id)
    budget = Budget.model_validate(job["budget"])
    store.patch("jobs", job_id, status=Status.RUNNING, started_at=now(), versions=versions())
    store.event(job_id, "Starting analysis", completed=0, total=0)
    queue = [store.get("artifacts", id, job["case_id"]) for id in job["artifact_ids"]]
    seen: set[str] = set()
    total = completed = 0
    outcomes: list[str] = []
    started = time.monotonic()
    while queue:
        artifact = queue.pop(0)
        if artifact["sha256"] in seen:
            store.event(job_id, "Duplicate content skipped", artifact_id=artifact["id"])
            continue
        seen.add(artifact["sha256"])
        selected = [
            a
            for a in REGISTRY
            if ("*" in a.kinds or artifact["kind"] in a.kinds)
            and (not a.deep_only or job["profile"] == "deep")
        ]
        total += len(selected)
        store.patch("jobs", job_id, total=total)
        for analyzer in selected:
            if store.get("jobs", job_id).get("cancel_requested"):
                store.patch("jobs", job_id, status=Status.CANCELLED, finished_at=now())
                store.event(job_id, "Cancelled", completed=completed, total=total)
                return
            if time.monotonic() - started > budget.job_seconds:
                store.patch(
                    "jobs", job_id, status=Status.TIMED_OUT, finished_at=now(), error="Job deadline exceeded"
                )
                return
            run = {
                "id": uid("r"),
                "case_id": job["case_id"],
                "job_id": job_id,
                "artifact_id": artifact["id"],
                "source_sha256": artifact["sha256"],
                "analyzer": analyzer.id,
                "version": __version__,
                "status": Status.RUNNING,
                "started_at": now(),
                "parameters": {"profile": job["profile"], **budget.model_dump()},
                "result": {},
                "error": None,
            }
            store.put("runs", run)
            store.event(
                job_id,
                analyzer.name,
                completed=completed,
                total=total,
                artifact_id=artifact["id"],
                run_id=run["id"],
            )
            context = Context(store, job, artifact, run)
            status, error, result = Status.COMPLETED, None, {}
            try:
                context.read()  # Verify immutable source before every analyzer.
                result = analyzer.function(context)
            except CancelledError as exc:
                status, error = Status.CANCELLED, str(exc)
            except TimeoutError as exc:
                status, error = Status.TIMED_OUT, str(exc)
            except UnsupportedError as exc:
                status, error = Status.UNSUPPORTED, str(exc)
            except SkippedError as exc:
                status, error = Status.SKIPPED, str(exc)
            except Exception as exc:
                # Analyzer failures are persisted, never interpreted as a negative result.
                status, error = Status.FAILED, f"{type(exc).__name__}: {str(exc)[:2000]}"
            store.patch(
                "runs",
                run["id"],
                status=status,
                error=error,
                result=result,
                finished_at=now(),
                duration_seconds=round(time.monotonic() - context.started, 4),
            )
            for derived in context.derived:
                if derived["role"] == "extracted" and derived["depth"] <= budget.max_depth:
                    queue.append(derived)
            completed += 1
            outcomes.append(status)
            store.patch("jobs", job_id, completed=completed, total=total)
            store.event(
                job_id, f"{analyzer.name}: {status}", completed=completed, total=total, run_id=run["id"]
            )
    status = Status.CANCELLED if Status.CANCELLED in outcomes else Status.COMPLETED
    if Status.FAILED in outcomes or Status.TIMED_OUT in outcomes:
        status = Status.FAILED
    store.patch(
        "jobs",
        job_id,
        status=status,
        finished_at=now(),
        error="Some analyzers failed; inspect run history." if status == Status.FAILED else None,
    )
    store.event(job_id, str(status), completed=completed, total=total)


def create_job(
    store: Store,
    case_id: str,
    artifact_ids: list[str],
    profile: str = "standard",
    budget: Budget | None = None,
) -> dict[str, Any]:
    if profile not in {"quick", "standard", "deep"}:
        raise ValueError("Unknown analysis profile")
    store.get("cases", case_id)
    for id in artifact_ids:
        store.get("artifacts", id, case_id)
    return store.put(
        "jobs",
        {
            "id": uid("j"),
            "case_id": case_id,
            "artifact_ids": list(dict.fromkeys(artifact_ids)),
            "profile": profile,
            "budget": (budget or Budget()).model_dump(),
            "status": Status.QUEUED,
            "created_at": now(),
            "completed": 0,
            "total": 0,
            "cancel_requested": False,
        },
    )
