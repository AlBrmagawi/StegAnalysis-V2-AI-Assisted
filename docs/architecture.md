# Architecture

StegAnalysis is one application with a shared Python engine, one API process, one supervised job subprocess at a time, and a React client. There are no remote services required for core use.

```text
React UI / CLI
      │
FastAPI / shared ingestion
      │
SQLite + per-case content-addressed originals and artifacts
      │
Persistent job queue → supervisor → isolated process → typed analyzer registry
      │                                  │
SSE persisted events              runs / findings / artifact edges
      │                                  │
Investigation, scoped assistant, analyst review, HTML / JSON export
```

## Data and provenance

`Store` applies numbered transactional migrations and uses SQLite WAL. Case, artifact, job, run, finding and message records have case indexes. Format-specific parameters and locations are JSON within those records. This supports byte ranges, PDF page/object numbers, image channels/planes and audio frame/time ranges without inventing offsets.

Each original is SHA-256 hashed and written once under `<data>/<case>/objects/<sha256>`. Uploading identical bytes to the same case returns the existing original. Derived records preserve distinct parent/run edges even if content hashes repeat. Files with identical content share stored bytes within the case. Worker workspaces live under `<data>/<case>/jobs/<job>`.

Ingestion holds a SQLite write transaction while checking identity, the API's original-file limit and object publication. Existing bytes are rehashed even for duplicate uploads. A new object is flushed to a temporary file and published by a non-overwriting hard link; the data filesystem must support hard links. Case snapshots use a single read transaction so concurrent analysis cannot produce dangling references in an export. Interruption finalizes active jobs/runs in one transaction and preserves already terminal results.

Findings have a run-specific stable ID and a content/analyzer/location fingerprint for comparison across reruns. Reruns retain prior findings, reviews, parameters, versions and actual tool output. A new run does not silently adopt a previous analyst review. Supporting references are artifact IDs; contradictory evidence is recorded as an alternative explanation, never as a fabricated measurement.

## Execution

The API returns HTTP 202 after writing a job. A single background supervisor selects queued records and launches `python -m steganalysis.worker`. Parsing does not run in request handlers. The CLI uses the same supervisor and worker. Task counts increase when supported extracted artifacts are discovered; the UI reports completed/discovered tasks, never invented percentages.

The analyzer registry declares supported signatures, versions, dependencies, profile eligibility, and the Pydantic budget schema. Each invocation has a running record followed by completed, failed, skipped, unsupported, timed-out, or cancelled status. Independent analyzers continue after a recorded failure when safe. A job with an analyzer failure ends failed and retains partial artifacts. Missing optional tools are skipped, not interpreted as negative evidence.

Cancellation kills the worker process tree, including external child processes. On restart, previously running jobs become failed with a restart explanation; queued jobs resume. Worker PID/create-time checks prevent killing an unrelated process whose PID was reused. Explicit retry creates a new job. Run the API with one Uvicorn worker; multiple supervisors against one data directory are unsupported.

## Limits

Defaults: 32 MiB input, 12 million decoded pixels, 100 PDF pages, 2 million channel/sample values, 160 derived artifacts and 96 MiB derived bytes per job, extraction depth 2, 45 seconds per analyzer, 180 seconds per job, 64 KiB each for captured external stdout/stderr. Rolling entropy has configurable 256–65,536-byte windows and strides, capped at 4,096 points. ASCII string capture is capped at 300 entries of 240 displayed characters. Text inspection covers at most 1 million characters and 200 invisible/whitespace locations per category.

The supervisor monitors process-tree RSS at 1.5 GiB and bounds diagnostic logs. Linux workers additionally apply CPU/file-size/open-file/core limits. Per-case aggregate disk quota is not implemented; repeated intentional analyses can consume storage. See [security](security.md) for boundaries.

## Implementation map

| Module | Responsibility |
|---|---|
| `models.py` | Typed configuration, request validation, IDs, timestamps |
| `db.py`, `storage.py` | Migrations, case scope, immutable objects, path containment |
| `engine.py` | Registry, provenance context, extraction queue, result states |
| `analyzers.py`, `pdf.py` | Native analysis and version-pinned parsed PDF revision hooks |
| `tools.py` | Optional tool health, bounded subprocess capture and tree cancellation |
| `jobs.py`, `worker.py` | Persistent queue supervision and parser process limits |
| `api.py`, `cli.py` | Same-origin HTTP/SSE and compatibility CLI |
| `assistant.py` | Minimal context, consent digest, provider boundary, citations |
| `ml.py` | Source-separated experiment, safe JSON model weights, inference |
| `reports.py`, `fixtures.py` | Reproducible reports and generated benign controls |

Dependency decisions followed current official documentation: [FastAPI container guidance](https://fastapi.tiangolo.com/deployment/docker/), [Vite requirements](https://vite.dev/guide/), [pypdf image extraction](https://pypdf.readthedocs.io/en/stable/user/extract-images.html), [Pillow security](https://pillow.readthedocs.io/en/stable/handbook/security.html). Exact installed versions are in the lockfiles and every job’s version record.


## Container network gateway

Docker Compose includes one non-root Nginx transport gateway in front of the application. It publishes only the loopback port and preserves Host/Origin and SSE streaming. It has no evidence-volume mount. The workbench remains on an internal network with no outbound route. This avoids Docker Desktop internal-network port-publication limitations without granting parsers internet access. The gateway itself has a normal bridge interface; its sole configured upstream is the workbench. Native use needs no gateway.
