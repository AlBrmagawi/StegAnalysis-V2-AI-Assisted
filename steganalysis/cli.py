from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path

from .db import Store
from .engine import create_job
from .jobs import run_sync
from .models import Budget
from .reports import html_report, report_data
from .storage import ingest
from .tools import doctor


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="steganalysis", description="Local steganalysis with explicit evidence provenance"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Analyze evidence in a bounded worker")
    analyze.add_argument("-f", "--file", type=Path, required=True)
    analyze.add_argument("--profile", choices=["quick", "standard", "deep"], default="standard")
    analyze.add_argument(
        "-o", "--output", type=Path, default=Path(os.getenv("STEG_DATA_DIR", ".data")) / "cli"
    )
    analyze.add_argument("--json", action="store_true", help="Write structured report to stdout")
    analyze.add_argument("--entropy-window", type=int, default=4096)
    analyze.add_argument("--entropy-stride", type=int, default=4096)
    analyze.add_argument("--timeout", type=int, default=180)
    commands.add_parser("doctor", help="Inspect native and optional tool capabilities")
    fixtures = commands.add_parser("fixtures", help="Generate only benign reproducible fixtures")
    fixtures.add_argument("--output", type=Path, default=Path("demo-fixtures"))
    demo = commands.add_parser("demo", help="Create a labeled demonstration case through the real engine")
    demo.add_argument("--data-dir", type=Path, default=Path(os.getenv("STEG_DATA_DIR", ".data")))
    serve = commands.add_parser("serve", help="Serve API and built frontend on loopback")
    serve.add_argument("--port", type=int, default=8000)
    ml = commands.add_parser("ml", help="Experimental ML pipeline; see steganalysis.ml --help")
    ml.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == "serve":
        import uvicorn

        if not 0 <= args.port <= 65535:
            serve.error("--port must be between 0 and 65535")
        # Own the listening port before startup can recover jobs in the data directory.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            if sys.platform == "win32":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", args.port))
                listener.listen(2048)
            except OSError as exc:
                serve.error(
                    f"Cannot listen on 127.0.0.1:{args.port}: {exc}. "
                    "Use the running instance or choose another --port with a separate STEG_DATA_DIR."
                )
            server = uvicorn.Server(
                uvicorn.Config("steganalysis.api:app_factory", factory=True, host="127.0.0.1", port=args.port)
            )
            server.run(sockets=[listener])
            if not server.started:
                raise SystemExit(1)
    elif args.command == "doctor":
        print(json.dumps(doctor(), indent=2))
    elif args.command == "fixtures":
        from .fixtures import make_fixtures

        print(json.dumps(make_fixtures(args.output), indent=2))
    elif args.command == "ml":
        from .ml import main as ml_main

        ml_main(args.args)
    elif args.command == "demo":
        from .fixtures import make_fixtures

        fixture_dir = args.data_dir / "generated-fixtures"
        make_fixtures(fixture_dir)
        store = Store(args.data_dir)
        case = store.create_case(
            "DEMO · The quiet signal",
            "Benign generated fixtures with known payloads and clean controls. Results come from the real pipeline.",
        )
        files = [
            "demo-lsb-landscape.png",
            "clean-landscape.png",
            "demo-attachment.pdf",
            "demo-unicode.txt",
            "demo-sample-lsb.wav",
        ]
        ids = [ingest(store, case["id"], (fixture_dir / name).read_bytes(), name)["id"] for name in files]
        result = run_sync(store, create_job(store, case["id"], ids)["id"])
        print(json.dumps({"case_id": case["id"], "job": result}, indent=2))
        if result["status"] != "completed":
            raise SystemExit(1)
    else:
        if args.file.is_symlink() or not args.file.is_file():
            parser.error("Input must be an ordinary file, not a symlink")
        if args.file.stat().st_size > Budget().max_file_bytes:
            parser.error("Input exceeds 32 MiB")
        store = Store(args.output)
        case = store.create_case(args.file.name)
        artifact = ingest(store, case["id"], args.file.read_bytes(), args.file.name)
        budget = Budget(
            entropy_window=args.entropy_window, entropy_stride=args.entropy_stride, job_seconds=args.timeout
        )
        job = create_job(store, case["id"], [artifact["id"]], args.profile, budget)
        result = run_sync(store, job["id"])
        report = report_data(store, case["id"])
        case_output = args.output / case["id"]
        (case_output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (case_output / "report.html").write_text(html_report(store, case["id"]), encoding="utf-8")
        print(
            json.dumps(report, indent=2)
            if args.json
            else f"{result['status']}: {result['completed']}/{result['total']} tasks. Reports: {case_output.resolve()}"
        )
        if result["status"] != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
