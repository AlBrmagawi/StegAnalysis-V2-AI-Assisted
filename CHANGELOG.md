# Changelog

## 2.0.0 — V2 workbench

### Investigation workflow

- React/TypeScript investigation workspace with dark/light themes, responsive layouts, keyboard controls, image transformations and artifact provenance.
- Shared FastAPI/CLI engine for PDF, PNG/JPEG/BMP, integer PCM WAV and UTF-8 text analysis.
- SHA-256 evidence identity, persistent SQLite cases, bounded subprocess jobs, progress events, cancellation and retry.
- Finding review, case notes and escaped, self-contained HTML/JSON exports.

### Assistance and interpretation

- Deterministic evidence guide available without a model; optional local/hosted providers with selected evidence, validated citations and explicit hosted-payload consent.
- Reproducible experimental ML pipeline with source-group splits and documented synthetic evaluation. No production detector or default weights are claimed.
- Explicit unsupported formats, missing dependencies, failed runs and method limitations.

### Quality assurance fixes

- Preserve unrelated changes when saving notes, report narratives or assistant drafts from stale clients.
- Revalidate duplicate evidence and publish complete objects without overwriting existing bytes.
- Deduplicate concurrent uploads and enforce original-file limits atomically.
- Export all case tables from a consistent database snapshot.
- Preserve terminal job results during late cancellation or shutdown.
- Exclude legacy binaries and sample PDFs from source packages and the published V2 tree.
- Reserve the CLI listening port before startup can recover interrupted jobs.
- Guard Windows-only process/socket constants so native type checks pass on both Windows and Linux.
- Keep keyboard focus inside dialogs on macOS WebKit, including forward/reverse navigation and dynamically enabled buttons.
- Run hosted browser checks across Ubuntu (all engines), Windows (Chromium/Firefox), and macOS (WebKit), retaining every journey and playback assertion; document the unverified Windows Server WebKit media combination.

### Verification

The local release-readiness pass recorded 98 passing Python tests on Windows with one permission-related skip, all 99 on restricted Linux, and 51 browser checks across Chromium, Firefox and WebKit. The production container completed real upload, analysis, progress and export checks. See [verification](docs/verification.md) for coverage and remaining limits, and [GitHub Actions](https://github.com/AlBrmagawi/StegAnalysis-V2-AI-Assisted/actions/workflows/checks.yml) for hosted runs.
