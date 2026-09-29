from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def now() -> str:
    return datetime.now(UTC).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:20]}"


def stable_id(prefix: str, *parts: Any) -> str:
    return prefix + "_" + hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:24]


class Status(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class Budget(BaseModel):
    max_file_bytes: int = Field(default=32 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024)
    max_pixels: int = Field(default=12_000_000, ge=1, le=24_000_000)
    max_artifacts: int = Field(default=160, ge=1, le=300)
    max_extracted_bytes: int = Field(default=96 * 1024 * 1024, ge=1024, le=256 * 1024 * 1024)
    max_depth: int = Field(default=2, ge=0, le=3)
    max_pages: int = Field(default=100, ge=1, le=200)
    max_samples: int = Field(default=2_000_000, ge=1024, le=4_000_000)
    entropy_window: int = Field(default=4096, ge=256, le=65536)
    entropy_stride: int = Field(default=4096, ge=256, le=65536)
    analyzer_seconds: int = Field(default=45, ge=1, le=120)
    job_seconds: int = Field(default=180, ge=1, le=600)
    tool_output_bytes: int = Field(default=65536, ge=1024, le=262144)


class AnalysisRequest(BaseModel):
    artifact_ids: list[str] = Field(min_length=1, max_length=16)
    profile: Literal["quick", "standard", "deep"] = "standard"
    budget: Budget = Field(default_factory=Budget)


class CaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class CaseUpdate(BaseModel):
    notes: str = Field(default="", max_length=20000)
    report_draft: str = Field(default="", max_length=40000)
    report_author: Literal["analyst", "deterministic", "model"] = "analyst"


class Review(BaseModel):
    status: Literal["unreviewed", "reviewed", "inconclusive", "false_positive"]
    note: str = Field(default="", max_length=4000)


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    finding_ids: list[str] = Field(default_factory=list, max_length=12)
    provider: Literal["deterministic", "local", "hosted"] = "deterministic"
    consent_digest: str | None = None


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    citations: list[str] = Field(min_length=1, max_length=12)


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[Claim] = Field(max_length=12)
    hypotheses: list[Claim] = Field(max_length=8)
    actions: list[Claim] = Field(max_length=8)
