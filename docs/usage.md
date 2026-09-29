# Investigation workflow and API

1. Create a case with a meaningful name and purpose.
2. Add files using drag/drop or the keyboard-accessible file chooser. Files are validated for size and hashed; identical originals deduplicate within the case.
3. Select Quick, Standard or Deep and the evidence scope. Watch actual stage names and completed/discovered counts. Cancel or retry without losing originals.
4. Navigate the evidence tree. Images offer synchronized original/derived views, channel and bit-plane selection, zoom/pan, histograms and byte entropy. WAV offers audio, waveform and spectrogram; PDFs offer parsed text, images, structure and attachments. Text/JSON previews are inert.
5. Search/filter/sort findings. Open a finding to jump to its supporting artifact and inspect its location, source hash, analyzer and limitations. Record reviewed/inconclusive/false-positive decisions with reasoning.
6. Use the provenance tab to traverse parent/run/child relationships. Run history includes every failure, skip and unsupported check.
7. Select findings for the assistant. The default guide is deterministic, not AI. Optional hosted calls require preview and exact-payload consent.
8. Save analyst notes and edit the report narrative. Export self-contained HTML or structured JSON. Use the browser's Print ? Save as PDF for a PDF copy.

## CLI

```sh
steganalysis doctor
steganalysis fixtures --output demo-fixtures
steganalysis analyze -f demo-fixtures/demo-attachment.pdf --profile standard --output .data/cli
steganalysis analyze -f demo-fixtures/demo-unicode.txt --profile quick --json
steganalysis analyze -f demo-fixtures/demo-lsb-landscape.png --profile deep --entropy-window 1024 --entropy-stride 512 --timeout 300
python script.py -f demo-fixtures/demo-sample-lsb.wav
```

Activate the environment or prefix commands with `uv run`. Each CLI analysis creates a new case with HTML and JSON reports in its output directory. Stdout with `--json` is structured; nonzero exit means a failed/timed-out/cancelled job, not a positive steganography verdict.

## HTTP API

Interactive schema: http://127.0.0.1:8000/docs. API clients use a custom mutation header. These examples assume POSIX shell quoting; use `curl.exe` with equivalent JSON quoting or Python/httpx on PowerShell.

```sh
curl -X POST http://127.0.0.1:8000/api/cases   -H 'Content-Type: application/json' -H 'X-Steganalysis: local'   -d '{"name":"Document review","description":"Validate a generated fixture"}'
```

Use the returned case ID:

```sh
curl -X POST http://127.0.0.1:8000/api/cases/CASE_ID/evidence   -H 'X-Steganalysis: local' -F 'file=@demo-fixtures/demo-unicode.txt'
curl -X POST http://127.0.0.1:8000/api/cases/CASE_ID/jobs   -H 'Content-Type: application/json' -H 'X-Steganalysis: local'   -d '{"artifact_ids":["ARTIFACT_ID"],"profile":"standard"}'
curl -N http://127.0.0.1:8000/api/cases/CASE_ID/jobs/JOB_ID/events
curl -o report.json http://127.0.0.1:8000/api/cases/CASE_ID/report.json
```

`GET /api/cases/CASE_ID` returns the case snapshot with artifacts, jobs, runs, findings and conversations. `POST .../jobs/JOB_ID/cancel` requests cancellation. `PATCH .../findings/FINDING_ID` records a review. `POST .../assistant/preview` returns the precise selected evidence projection and consent digest; `POST .../assistant` validates it for hosted calls. IDs are scoped to the case, including artifact content access.

## Benign fixture protocol

`steganalysis fixtures` generates a PDF with a known standard attachment, normal blank/incremental controls, a deliberately appended tail, a shaped image and known LSB demo variant, clean JPEG noise and grayscale controls, UTF-8 invisible/whitespace indicators, and clean/LSB-pattern integer PCM WAVs. A manifest records hashes and seed. No committed binary or historical sample PDF is used. The exact demo framing is documented in [analysis methods](analyzers.md).
