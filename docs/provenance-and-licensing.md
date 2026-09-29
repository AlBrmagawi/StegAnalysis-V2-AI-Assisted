# Audit, provenance and licensing

Original project: [AlBrmagawi/steganalysis](https://github.com/AlBrmagawi/steganalysis). Original creators: **Mohamed Abdelgalil (AlBrmagawi)** and **Spooky**. Inspected baseline: master `1eaabb0efd96cf9f2849da2090bdacaefb64abbe`, with prior commits `d6ad3f1` and `6ca5391`. The rebuild and local QA were developed on `workbench/local-rebuild`.

V2 publication target: [AlBrmagawi/StegAnalysis-V2-AI-Assisted](https://github.com/AlBrmagawi/StegAnalysis-V2-AI-Assisted). V2 starts with a clean source tree and retains creator credits and this provenance record. The original repository is not a publication target and its history is unchanged.

## Licensing status

The baseline had no LICENSE/COPYING file and no project license declaration. Public repository visibility does not establish permission to relicense it. Existing attribution is retained in README, package metadata, compatibility entry point, UI and reports. No new blanket project license has been invented. Resolve project licensing with the creators before redistribution or relicensing. Dependency licenses do not resolve the project’s own licensing.

## Unverified legacy binaries

These files remain untouched in the original development checkout. They are excluded from the published V2 tree, Docker build and source packages, and are never executed by the application or tests:

| File | Size | SHA-256 |
|---|---:|---|
| `ensteg` | 17,720 B | `63ef17e213ed928462f976394e47b42f776421e680eff62373e134912998dc94` |
| `stegwav` | 17,408 B | `0b5977d53a6946c64a187a93481c419c5ec63857f7555756f714189a9cda104e` |

No source/build recipe or redistribution license was established for these committed executables. The original `tryme.pdf` and `test.pdf.bak` were not opened or analyzed; fixtures are generated from scratch. WAV behavior is replaced with reproducible stdlib PCM decoding plus NumPy/SciPy, not an assumed clone of the legacy binary’s algorithm.

## Reproducible dependency replacements

- PDF extraction: pypdf, BSD-3-Clause; image processing: Pillow, HPND; numerical processing: NumPy/SciPy, BSD family. Exact artifacts are locked by version and hash.
- Optional [Binwalk upstream](https://github.com/ReFirmLabs/binwalk): build/install from trusted upstream or your package manager; this workbench uses a non-extracting signature invocation.
- Optional [zsteg upstream](https://github.com/zed-0xff/zsteg): install the published Ruby gem or reproduce from upstream source; invocation and version are recorded.
- Optional [Steghide documentation/source](https://steghide.sourceforge.net/documentation.php): install a trusted package/build explicitly. Only non-interactive carrier information is integrated.
- GUI-only Stegsolve is replaced by native lossless web inspection. Foremost carving is explicitly unavailable; no dangerous unbounded “extract everything” fallback is offered.

These third-party projects retain their own licenses and notices. The workbench does not vendor optional tool executables or claim a redistribution license for them. Tool results can vary by installed version; record `doctor` output with an examination.

## Legacy defect disposition

| Audited issue | Rebuild behavior |
|---|---|
| pip/sudo apt on import | Explicit locked installation only; imports do not install software |
| Undefined `run_stegwav` | Tested integer PCM analyzer and sample-level inspection |
| `extract_text()` returning None | Empty-text observation, no None concatenation |
| Duplicate processing | Per-job SHA-256 visited set and upload deduplication |
| Broad swallowed exceptions | Persisted typed run outcomes and actionable errors |
| Global output directory | Per-case objects and per-job workspaces |
| Unbounded subprocesses | Wall deadlines, output caps and process-tree cancellation |
| Fragile pixel modes | Deliberate normalization and unsupported-depth state |
| All extracted images named PNG | Extension chosen from actual returned signature |
| Whitespace asserted as proof | Qualified indicator, exact location, benign explanations |
| Regex parsing PDF objects | Parser extraction and parsed revision hooks |

The original source remains available in the upstream project's Git history. V2 does not import the legacy executable/sample-file history into its new repository.
