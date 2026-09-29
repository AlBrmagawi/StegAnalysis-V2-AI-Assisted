from __future__ import annotations

import builtins
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import now, uid

TABLES = {"cases", "artifacts", "jobs", "runs", "findings", "messages"}

# Ordered, transactional migrations. JSON records preserve analyzer-specific locations.
MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
    INSERT INTO schema_version VALUES(1);
    CREATE TABLE cases(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, data TEXT NOT NULL);
    CREATE TABLE artifacts(id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), data TEXT NOT NULL);
    CREATE TABLE jobs(id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), data TEXT NOT NULL);
    CREATE TABLE runs(id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), data TEXT NOT NULL);
    CREATE TABLE findings(id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), data TEXT NOT NULL);
    CREATE TABLE messages(id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), data TEXT NOT NULL);
    CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, data TEXT NOT NULL);
    CREATE INDEX artifacts_case ON artifacts(case_id);
    CREATE INDEX jobs_case ON jobs(case_id);
    CREATE INDEX runs_case ON runs(case_id);
    CREATE INDEX findings_case ON findings(case_id);
    CREATE INDEX messages_case ON messages(case_id);
    CREATE INDEX events_job ON events(job_id,seq);
    """
]


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "workbench.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            present = db.execute("SELECT name FROM sqlite_master WHERE name='schema_version'").fetchone()
            version = db.execute("SELECT version FROM schema_version").fetchone()[0] if present else 0
            for migration in MIGRATIONS[version:]:
                db.executescript("BEGIN IMMEDIATE;\n" + migration + "\nCOMMIT;")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=20)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=NORMAL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def put(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        if table not in TABLES:
            raise ValueError("Unknown table")
        with self.connect() as db:
            db.execute(
                f"INSERT INTO {table}(id,case_id,data) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (
                    data["id"],
                    data.get("case_id", data["id"]),
                    json.dumps(data, ensure_ascii=True, allow_nan=False),
                ),
            )
        return data

    def get(self, table: str, id: str, case_id: str | None = None) -> dict[str, Any]:
        if table not in TABLES:
            raise ValueError("Unknown table")
        with self.connect() as db:
            row = db.execute(f"SELECT case_id,data FROM {table} WHERE id=?", (id,)).fetchone()
        if not row or (case_id is not None and row[0] != case_id):
            raise KeyError(id)
        return json.loads(row[1])

    def patch(self, table: str, id: str, **changes: Any) -> dict[str, Any]:
        if table not in TABLES:
            raise ValueError("Unknown table")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(f"SELECT data FROM {table} WHERE id=?", (id,)).fetchone()
            if not row:
                raise KeyError(id)
            data = json.loads(row[0])
            data.update(changes)
            db.execute(f"UPDATE {table} SET data=? WHERE id=?", (json.dumps(data, allow_nan=False), id))
        return data

    def list(self, table: str, case_id: str | None = None) -> list[dict[str, Any]]:
        if table not in TABLES:
            raise ValueError("Unknown table")
        with self.connect() as db:
            rows = db.execute(
                f"SELECT data FROM {table}" + (" WHERE case_id=?" if case_id else "") + " ORDER BY rowid",
                (case_id,) if case_id else (),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def event(self, job_id: str, stage: str, **data: Any) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(job_id,data) VALUES(?,?)",
                (job_id, json.dumps({"time": now(), "stage": stage, **data})),
            )

    def events(self, job_id: str, after: int = 0) -> builtins.list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT seq,data FROM events WHERE job_id=? AND seq>? ORDER BY seq LIMIT 300", (job_id, after)
            ).fetchall()
        return [{"seq": row[0], **json.loads(row[1])} for row in rows]

    def create_case(self, name: str, description: str = "") -> dict[str, Any]:
        return self.put(
            "cases",
            {
                "id": uid("c"),
                "name": name,
                "description": description,
                "created_at": now(),
                "notes": "",
                "report_draft": "",
                "report_author": "analyst",
            },
        )

    def claim_job(self, job_id: str) -> bool:
        """Atomically claim a queued job, including when CLI and API share storage."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            job = json.loads(row[0])
            if job["status"] != "queued":
                return False
            job.update(status="running", started_at=now())
            db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
        return True

    def snapshot(self, case_id: str) -> dict[str, Any]:
        # Keep every table at one WAL revision while a worker adds derived evidence.
        with self.connect() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT data FROM cases WHERE id=?", (case_id,)).fetchone()
            if not row:
                raise KeyError(case_id)
            snapshot = {"case": json.loads(row[0])}
            for table in ("artifacts", "jobs", "runs", "findings", "messages"):
                rows = db.execute(
                    f"SELECT data FROM {table} WHERE case_id=? ORDER BY rowid", (case_id,)
                ).fetchall()
                snapshot[table] = [json.loads(row[0]) for row in rows]
        return snapshot

    def interrupt_job(self, job_id: str, status: str, error: str) -> None:
        """Finalize a stopped worker atomically, without replacing a terminal result."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            job = json.loads(row[0])
            if job["status"] not in {"queued", "running"}:
                return
            finished = now()
            rows = db.execute("SELECT data FROM runs WHERE case_id=?", (job["case_id"],)).fetchall()
            for row in rows:
                run = json.loads(row[0])
                if run["job_id"] == job_id and run["status"] == "running":
                    run.update(status=status, finished_at=finished, error=error)
                    db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(run), run["id"]))
            job.update(status=status, finished_at=finished, error=error)
            db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
            db.execute(
                "INSERT INTO events(job_id,data) VALUES(?,?)",
                (job_id, json.dumps({"time": finished, "stage": status, "error": error})),
            )
