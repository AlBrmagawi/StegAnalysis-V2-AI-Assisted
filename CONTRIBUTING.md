# Contributing

StegAnalysis V2 is a local forensic workbench. Useful contributions make examinations more reproducible, improve supported-format handling, or help analysts distinguish measurements from interpretations.

Read the [architecture](docs/architecture.md), [analysis methods](docs/analyzers.md), and [security boundaries](docs/security.md) before changing those contracts. The project's [licensing status](docs/provenance-and-licensing.md#licensing-status) is still unresolved; no contributor license agreement or new license is implied.

## Development setup

Use Python 3.12 and Node 24 for the tested configuration. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv sync --frozen --group ml
cd frontend
npm ci
npm run build
cd ..
uv run steganalysis fixtures
uv run steganalysis demo
uv run steganalysis serve
```

For frontend development, run `npm run dev` from `frontend/` in a second terminal and open http://127.0.0.1:5173. Use `npm.cmd` / `npx.cmd` on Windows when PowerShell blocks script shims. Run only one API instance per data directory.

## Before opening a pull request

1. Explain the user-visible problem and the resulting behavior.
2. Use generated benign fixtures. Include a regression test for a behavioral defect; never commit real case data, extracted evidence, credentials or model weights.
3. Preserve original hashes, case boundaries and artifact/run provenance. Failed or skipped analysis must remain explicit.
4. Keep observations, heuristics, recovered content, model output and analyst conclusions distinct. Describe the method and its limits when adding a detector.
5. Run checks relevant to the change and report their actual results. Update documentation when behavior changes.

## Checks

```sh
uv run --frozen --group ml ruff check steganalysis tests scripts script.py
uv run --frozen --group ml mypy steganalysis
uv run --frozen --group ml pytest -q
cd frontend
npm run lint
npm run build
npx playwright install chromium firefox webkit
npm run test:e2e
cd ..
uv run mkdocs build --strict
```

Playwright starts an isolated server and temporary evidence store. It does not use your analyst cases. Linux container checks, coverage commands and the full feature matrix are in [testing](docs/testing.md).

Edit documentation in `docs/`, not generated `site/`. Keep both lockfiles current for intentional dependency updates; regenerate `requirements.lock` using the command in [installation](docs/installation.md#dependencies-and-updates). Preserve the original creator credits.

## Reporting problems

Use a [bug report](https://github.com/AlBrmagawi/StegAnalysis-V2-AI-Assisted/issues/new?template=bug-report.yml) with the app version, OS, launch method, steps and relevant sanitized logs. For security issues, use the private route described in [SECURITY.md](SECURITY.md).
