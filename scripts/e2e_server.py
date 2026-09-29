"""Start an isolated, fixture-backed API for Playwright; never use analyst data."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import uvicorn

from steganalysis.cli import main


def serve() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()
    # Optional services must not receive test evidence through inherited credentials.
    for key in list(os.environ):
        if key.startswith(("STEG_HOSTED_", "STEG_LOCAL_", "STEG_ML_")):
            os.environ.pop(key)
    with tempfile.TemporaryDirectory(prefix="steganalysis-e2e-") as directory:
        os.environ["STEG_DATA_DIR"] = directory
        main(["fixtures", "--output", str(Path("demo-fixtures"))])
        main(["demo", "--data-dir", directory])
        uvicorn.run("steganalysis.api:app_factory", factory=True, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    serve()
