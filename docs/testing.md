# Testing and release checks

Tests use generated benign evidence. The legacy binaries and original sample PDFs are never executed or parsed. The suite validates the supported local research workflow; it cannot prove the absence of all defects or establish universal steganography detection accuracy.

## Native checks

```sh
uv sync --frozen --group ml
uv run --frozen --group ml pytest --cov --cov-report=term-missing --cov-report=xml -q
uv run --frozen --group ml ruff check steganalysis tests scripts script.py
uv run --frozen --group ml mypy steganalysis
cd frontend
npm ci
npm run lint
npm run build
npx playwright install chromium firefox webkit
npm run test:e2e
cd ..
uv run --frozen --group ml mkdocs build --strict
```

In this Windows checkout, replace `uv` with `.tools/uv/uv.exe` and use `npm.cmd` / `npx.cmd` if PowerShell blocks script shims. Python is also directly available at `.venv/Scripts/python.exe`.

Playwright builds no assets itself: run the production build first. It launches `scripts/e2e_server.py` on port 18765, creates temporary evidence storage, generates fixtures, and analyzes a real demo before the browser starts. Existing analyst cases and the normal server on port 8000 are not used. Optional model settings are removed from the test server environment. A separate persistence test chooses a free port, stops its entire owned server process tree, verifies the endpoint is unavailable, then restarts against the same data and verifies notes and exports.

Use `npm run test:e2e -- --project=chromium` for one browser, or `--grep "upload"` to select a journey. HTML reports are in `frontend/playwright-report/`; failures preserve screenshots and traces under `frontend/test-results/`. `STEG_E2E_BASE_URL` can target a disposable externally started instance containing the generated demo; that mode writes test cases to the selected instance.

## Coverage matrix

| Area | Automated checks |
|---|---|
| Formats | PNG/JPEG/BMP signatures and pixel modes; PCM widths; float WAV rejection; parsed PDF metadata/text/images/attachments/revisions; malformed/encrypted inputs; exact Unicode locations |
| Evidence integrity | Hash identity; revalidation of duplicate uploads; missing/tampered originals; concurrent deduplication and case capacity; atomic object publication and failed-write recovery; distinct extraction edges; case boundaries, traversal and symlinks; extraction budgets; CRC failure |
| Statistical interpretation | Known LSB frames, clean controls, high entropy, chi-square assumptions, explicit JPEG decoded-pixel scope |
| Jobs | Atomic claim, persistent progress and SSE reconnect, queue cap, cancellation and child termination, deadlines, worker exit failure, restart, retained originals, terminal-result preservation and idempotent interruption |
| API and reports | Upload limits including streamed bodies, host/origin checks, inert downloads, notes/reviews, partial updates, escaped HTML, JSON provenance and hashes, consistent snapshots during concurrent writes |
| CLI | JSON and file exports for all four supported input categories, compatibility entry point, invalid input, structured doctor output, occupied-port failure without case mutations, successful HTTP startup and socket cleanup |
| UI controls | Search/sort/filter, named dialogs, focus containment/restoration, keyboard tabs, resizing, synchronized pan/zoom, transformations, upload/remove/drop/validation/retry, all analysis profiles, reruns, finding review |
| UI journeys | Real upload-to-recovery-to-report; PDF attachments; text locations; WAV playback/waveform/spectrogram; assistant citations and draft; JSON and HTML downloads; genuine server restart; stale-editor isolation across clients; failed-save retry without losing the draft |
| Responsive accessibility | Chromium, Firefox, WebKit; 320/768/1536 px; dark/light; reduced motion; axe WCAG A/AA checks on primary screens and dialogs |
| Assistant | Exact hosted consent, minimal case-scoped evidence, citation/schema validation, prompt-injection boundaries, HTTP stubs for local/hosted success and timeout/quota/invalid/oversized responses; browser consent and failure states |
| Optional tools | Explicit missing states; bounded subprocess execution/failure/timeout/cancellation; adapter contracts and captured versions/output using controlled stubs |
| Experimental ML | Source/derivative split separation, training-only scaling, integrity checks, permission requirement, real training and inference integration, invalid model coefficients, traversal rejection |

The provider stubs are identified test responses, not evidence of live-model quality. External tool contracts do not substitute for testing an installed executable/version. Automated accessibility scans do not replace manual screen-reader evaluation. Windows may skip actual symlink creation when developer mode/elevation is unavailable; the Linux run exercises it.

## Linux container checks

```sh
docker build --target verification -t steganalysis-verification .
docker run --rm --init --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=256m --cap-drop ALL --security-opt no-new-privileges --memory 2g --cpus 2 --pids-limit 96 steganalysis-verification
```

The verification image installs locked development dependencies at build time. Tests run as UID 10001, offline, with a read-only root and temporary test storage. The default Docker target remains the smaller production image; it does not include pytest or ML training dependencies.

To check multipart upload, real analysis, nonblocking HTTP, SSE, hashes and HTML/JSON export through a running disposable gateway, run `uv run python scripts/smoke.py --url http://127.0.0.1:8001` after starting Compose with `STEG_PORT=8001`. This intentionally creates a labeled SMOKE case with five generated files in that instance. It leaves existing evidence intact.

The [GitHub Actions workflow](https://github.com/AlBrmagawi/StegAnalysis-V2-AI-Assisted/actions/workflows/checks.yml) runs native checks on Windows and Ubuntu, all three browser engines, documentation, package builds, and a separate restricted Linux container job. It retains coverage and browser failure artifacts. Inspect the run for the specific commit you use; local QA results do not substitute for hosted CI results.

## Repository readiness

Before sharing, check `git diff --check`, inspect the diff, verify that evidence, environments, credentials, models and test outputs remain ignored, and inspect dependency/secret scan findings. Generated `site/` is built locally from documentation source and excluded from Git. Retain creator credits and the unresolved original-license notice. The current measured results and exact unverified features are recorded in [verification](verification.md).
