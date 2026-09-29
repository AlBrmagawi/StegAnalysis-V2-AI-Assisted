# Installation

## Native

Use Python 3.12 (tested), Node 24 LTS, npm, and uv. Python 3.13/3.14 are permitted by the package but were not independently exercised. Install dependencies explicitly; no runtime/import path installs packages or invokes sudo.

```sh
git clone https://github.com/AlBrmagawi/StegAnalysis-V2-AI-Assisted.git
cd StegAnalysis-V2-AI-Assisted
uv sync --frozen
cd frontend
npm ci
npm run build
cd ..
uv run steganalysis fixtures
uv run steganalysis demo
uv run steganalysis serve
```

Open http://127.0.0.1:8000. `demo` is optional and creates a labeled investigation by processing newly generated benign fixtures. It does not parse the repository's original sample PDFs or execute its binaries. Data is stored in `.data/` by default; set `STEG_DATA_DIR` to change it.

Install uv before using these commands. On Windows, Python is available at `.venv/Scripts/python.exe` after synchronization; you can use `& .\.venv\Scripts\steganalysis.exe serve` after installation. Use `npm.cmd` and `npx.cmd` if PowerShell blocks the `.ps1` shims. No execution-policy change is needed.

For editable native development, keep the API running and launch `npm run dev` from `frontend/`. Open http://127.0.0.1:5173. The Vite proxy keeps API requests same-origin. Opening Vite on `localhost` and mixing it with raw `127.0.0.1` API URLs is unnecessary; use relative `/api` routes.

## Containers

```sh
docker compose up --build -d
docker compose exec workbench steganalysis demo
```

Stop any existing native server on port 8000 first. The image runs UID 10001 with a named volume, read-only root, limited resources and no outbound connectivity. Only `127.0.0.1:8000` is published. For a second local instance set `STEG_PORT=8001` before Compose startup. Never publish the service on a public interface.

```sh
docker compose logs --tail 50 workbench
docker compose exec workbench steganalysis doctor
docker compose down
```

The last command preserves evidence. `down -v` deletes the named volume and is not a routine shutdown command.

## Dependencies and updates

`uv.lock` locks Python development/ML dependencies; `requirements.lock` is the hash-locked runtime export used by Docker. `frontend/package-lock.json` locks JavaScript dependencies. Docker base images are pinned by digest. Regenerate the runtime export after an intentional dependency update:

```sh
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock
```

Optional tools must be explicitly installed on trusted PATH. Settings/doctor reports absence clearly. No installation is necessary for native channels, bit planes, PCM, entropy, PDF extraction or text checks. See [adapter behavior](analyzers.md) and [dependency provenance](provenance-and-licensing.md).

## Troubleshooting

- **Blank API landing page:** build the frontend, then restart the service so it mounts `dist/assets`.
- **Port already in use:** stop the other local server or use `steganalysis serve --port 8001` / `STEG_PORT` for Compose.
- **HTTP 403:** use the same-origin app/proxy, loopback host, and `X-Steganalysis: local` for API mutations. Do not disable origin controls.
- **Job failed/timed out:** inspect Run history. Partial outputs are retained; retry creates a new run. Reduce scope or adjust documented budgets within maximums.
- **Worker interrupted on restart:** previous running jobs are marked failed; use Retry. Queued jobs resume.
- **Missing tools/model:** native analysis and the deterministic guide still work. Do not interpret skips as absence of hidden content.
- **Container provider unavailable:** its default network intentionally has no outbound connectivity. Native providers require explicit configuration; see [assistant](assistant.md).
- **Space use:** cases retain all run history. No aggregate disk quota is enforced. Back up and manage data offline while the service is stopped; originals are not deleted through the UI.

Build documentation with `uv run mkdocs build --strict`. `site/` is generated; change `docs/` and rebuild rather than editing generated HTML.


## Container network gateway

Docker Compose includes one non-root Nginx transport gateway in front of the application. It publishes only the loopback port and preserves Host/Origin and SSE streaming. It has no evidence-volume mount. The workbench remains on an internal network with no outbound route. This avoids Docker Desktop internal-network port-publication limitations without granting parsers internet access. The gateway itself has a normal bridge interface; its sole configured upstream is the workbench. Native use needs no gateway.
