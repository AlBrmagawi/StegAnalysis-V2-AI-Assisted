"""Exercise a disposable running instance through its public HTTP API."""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from steganalysis.fixtures import make_fixtures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Loopback URL of a disposable instance")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Use a loopback instance")
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="steganalysis-smoke-") as directory:
        fixture_dir = Path(directory)
        make_fixtures(fixture_dir)
        with httpx.Client(base_url=args.url, headers={"X-Steganalysis": "local"}, timeout=240) as client:

            def checked(response):
                response.raise_for_status()
                return response.json()

            assert checked(client.get("/api/health"))["version"] == "2.0.0"
            assert (
                client.get("/api/cases", headers={"Origin": "https://unrelated.invalid"}).status_code == 403
            )
            case = checked(
                client.post("/api/cases", json={"name": "SMOKE · generated multi-format verification"})
            )
            base = f"/api/cases/{case['id']}"
            artifacts = []
            for name in (
                "demo-lsb-landscape.png",
                "clean-landscape.png",
                "demo-attachment.pdf",
                "demo-unicode.txt",
                "demo-sample-lsb.wav",
            ):
                data = (fixture_dir / name).read_bytes()
                artifact = checked(client.post(base + "/evidence", files={"file": (name, data)}))
                assert artifact["sha256"] == hashlib.sha256(data).hexdigest()
                artifacts.append(artifact["id"])
            job = checked(
                client.post(base + "/jobs", json={"artifact_ids": artifacts, "profile": "standard"})
            )
            events, responsive = [], False
            with client.stream("GET", base + f"/jobs/{job['id']}/events") as stream:
                stream.raise_for_status()
                for line in stream.iter_lines():
                    if line.startswith("event:"):
                        events.append(line)
                        if not responsive:
                            assert client.get("/api/cases", timeout=5).status_code == 200
                            responsive = True
            assert "event: done" in events and "event: progress" in events
            checked(
                client.patch(
                    base, json={"notes": "Verified through HTTP: hashes, all formats, progress and exports."}
                )
            )
            report = checked(client.get(base + "/report.json"))
            assert report["jobs"][0]["status"] == "completed", report["jobs"][0]
            assert report["case"]["notes"].startswith("Verified through HTTP")
            assert len({(r["artifact_id"], r["analyzer"]) for r in report["runs"]}) == len(report["runs"])
            assert sum(f["category"] == "recovered" for f in report["findings"]) == 2
            assert any(a["name"] == "known-attachment.txt" for a in report["artifacts"])
            assert any(f["title"] == "Invisible Unicode characters" for f in report["findings"])
            html = client.get(base + "/report.html")
            html.raise_for_status()
            assert "SHA-256" in html.text and "<script" not in html.text
            print(
                json.dumps(
                    {
                        "case": case["id"],
                        "status": "passed",
                        "runs": len(report["runs"]),
                        "findings": len(report["findings"]),
                        "events": len(events),
                        "html_bytes": len(html.content),
                        "seconds": round(time.monotonic() - start, 2),
                    }
                )
            )


if __name__ == "__main__":
    main()
