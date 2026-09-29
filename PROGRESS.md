# StegAnalysis V2 development record

## Constraints
- The rebuild and initial QA were local on `workbench/local-rebuild`. Publication was later authorized specifically to `AlBrmagawi/StegAnalysis-V2-AI-Assisted`; the original repository remains untouched.
- Original creators: Mohamed Abdelgalil (AlBrmagawi) and Spooky. Preserve attribution.
- Original binaries and sample PDFs are not executed or parsed. Use generated fixtures.
- No LICENSE found at original commit `1eaabb0`. No relicensing inferred.

## Audit
Empty workspace cloned from upstream master at `1eaabb0` (three commits). No AGENTS.md, package metadata, tests, or reusable service. Read script.py, documentation and git history. Confirmed import-time pip/sudo installation, missing run_stegwav, None text handling, duplicate processing, broad exceptions, global output, unbounded subprocesses, fragile pixel handling, incorrect extracted extensions, and unsupported whitespace detection claim. Generated documentation has been rewritten and rebuilt from current source.

## Decisions
- Python 3.12; FastAPI, SQLite migrations, isolated job subprocess with bounded single worker, persistent events streamed over SSE. Shared engine for CLI and API.
- pypdf (BSD) rather than adding an AGPL PDF engine; Pillow, numpy/scipy for native image/audio visual inspection.
- Original bytes immutable by application contract, SHA-256 identity, per-case paths and linked artifacts/runs/findings. Profiles record actual completion counts.
- React/TypeScript/Vite with native accessible controls, restrained teal/slate interface and light theme.
- No model/key required. Deterministic assistant explicitly labeled; optional local/hosted providers with minimal selection and consent.
- Experimental ML ships reproducible source-group split pipeline, JSON weights (no pickle), clear scope and no universal detection claim.
- Official FastAPI container, Vite requirements, pypdf image extraction, Pillow security, and sklearn leakage documentation checked. Exact resolved versions go in lockfiles.

## Stages
- [x] Audit and local branch
- [x] Engine, persistence, jobs, API/CLI, fixtures, reports
- [x] Complete investigation UI
- [x] Grounded assistant and ML extension
- [x] Tests, browser verification, documentation and screenshots

## Verification / continuation
- Python 3.12.14 managed by workspace-local uv; Node 24.18, Docker 29.6.
- Current Python results after QA: 98 passed and one symlink-permission skip on Windows; all 99 passed in restricted Linux. Statement coverage 89.04%, branch coverage 75.77%. Ruff and mypy pass (16 modules). TypeScript, ESLint and Vite production build pass.
- All 51 Playwright checks pass: 17 journeys each in Chromium, Firefox and WebKit, including upload/recovery/review/assistant/export, genuine API restart persistence, responsive accessibility, keyboard controls, failure states, hosted consent and concurrent-client edit preservation.
- Fixed contrast findings from axe. Checked layouts at 1536/1440 and 390 pixels. Screenshots in docs/screenshots.
- Synthetic ML experiment completed (60 sources, 300 examples). Test AUC 0.6204, FPR 0.875. Inadequate for operation; no default model weights shipped. Natural-source evaluation and live model provisioning remain optional/user-supplied.
- Compatibility CLI and structured CLI exports tested for all four input categories. Readiness tests use isolated servers and leave normal port 8000 unused. Optional external tools absent, reported as such.
- Docker built from clean dependency installs; UID 10001 and no outbound route verified; real 18-task demo completed. Fixed CLI STEG_DATA_DIR defaults for read-only image. Docker Desktop internal-network port publication required a dedicated loopback gateway without an evidence mount.
- MkDocs strict build passes. Container gateway serves the real app; final Docker demo completed 18/18 runs and 23 findings without duplicate execution. Desktop/narrow screenshots refreshed from that running container.
- Implementation and verification complete. Optional external tools and live model providers remain unprovisioned; no default experimental ML weights are enabled. See docs/verification.md for the exact tested scope.
- Original binaries/PDFs unchanged; no git push, merge, history rewrite or public deployment.

## Extended readiness audit (requested after initial delivery)
- Expanded Python contracts from 50 to 83 collected tests, covering all-format CLI exports, streamed upload limits, SSE reconnect, provider failures, real worker deadlines/exits, optional adapter contracts and trained ML integration.
- Browser suite expanded to 15 journeys across Chromium, Firefox and WebKit. It starts its own isolated server/data, includes 320/768/1536 px and both themes, and leaves normal port 8000 unused.
- Fixed unnamed dialogs, initial/contained/restored keyboard focus, arrow-key tabs, narrow assistant scroll access, malformed provider envelopes, and in-root symlink rejection for ML manifests.
- Linux verification image runs non-root, offline, read-only; all 83 tests pass, including the Windows-skipped symlink test. Final Windows coverage run: 82 passed, one skipped, zero failures.
- Frozen installs, Ruff/mypy/TypeScript/ESLint/build, Python/npm dependency audits, package creation and repository-content review passed. Secret scan candidates were dataset SHA-256 identities, not credentials.
- Final three-browser regression: 45 passed. Production Docker HTTP smoke: five generated files, 18 runs, 23 findings, 38 SSE events and valid reports. Workflow checked by actionlint; GitHub-hosted CI remains unrun until a future authorized push. No push performed.

## Quality control and assurance follow-up
- Added 16 Python regression cases and two browser journeys (six browser executions). Reproduced nine Python failures and two Chromium failures before corrections, plus a source-archive content defect.
- Fixed stale editor writes replacing unrelated fields, unchecked damaged duplicate evidence, concurrent original-record duplication, inconsistent export snapshots, late interruptions replacing terminal jobs, unnecessary legacy files in source packages, and occupied-port CLI startup mutating existing jobs.
- Added atomic original-file limits, flush/publication fault injection, retry checks, distinct derived-provenance controls, and successful CLI server startup/cleanup coverage.
- Final regressions: Windows 98 passed/one symlink-permission skip; restricted Linux 99 passed; all three browsers 51 passed. Ruff, mypy, frontend lint/types/build and frozen lock validation passed.
- Rebuilt and inspected the wheel/source archive. A fresh isolated wheel installation completed real analysis and HTML/JSON reporting. Original executables and PDFs remain unchanged in the checkout and are excluded from the source package.
- The rebuilt production container passed the HTTP smoke test: 18 runs, 23 findings, 38 SSE events and valid JSON/246,032-byte HTML reports in 65.72 seconds. Removed only the disposable QA containers/networks/evidence volume afterward; existing analyst evidence remains intact.
- Exact findings, coverage and remaining limitations are recorded in docs/verification.md. Work remains local; no commit, push, merge or public deployment.

## V2 repository publication
- Publication target: `https://github.com/AlBrmagawi/StegAnalysis-V2-AI-Assisted`, branch `main`. Earlier no-push statements above describe the completed local QA phases.
- Publish the supported source, regression tests, real screenshots, documentation and locked build configuration. Keep legacy executables/PDFs, generated site files, local evidence, environments and test outputs outside the published tree and initial history.
- Add a visual README, live CI link, contribution/security guidance, changelog and issue/PR templates. Preserve both creators' attribution and the unresolved licensing notice.
- GitHub-hosted checks are tracked by the repository workflow; their status is separate from the completed local QA evidence.
