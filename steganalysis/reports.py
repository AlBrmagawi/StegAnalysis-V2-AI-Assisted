from __future__ import annotations

import base64
import html
import json

from . import __version__
from .db import Store
from .models import now
from .storage import artifact_path


def report_data(store: Store, case_id: str) -> dict:
    snapshot = store.snapshot(case_id)
    for artifact in snapshot["artifacts"]:
        artifact.pop("path", None)
    for job in snapshot["jobs"]:
        job.pop("worker_pid", None)
        job.pop("worker_created", None)
    return {
        "schema_version": 1,
        "application": "StegAnalysis",
        "version": __version__,
        "exported_at": now(),
        "creators": ["Mohamed Abdelgalil (AlBrmagawi)", "Spooky"],
        "limitations": "Indicators are not proof of steganography. Review failed/skipped runs. Experimental ML is method- and dataset-specific. Model-authored prose requires analyst review.",
        **snapshot,
    }


def html_report(store: Store, case_id: str) -> str:
    data = report_data(store, case_id)
    e = lambda value: html.escape(str(value))  # noqa: E731
    case = data["case"]
    parts = [
        f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>StegAnalysis · {e(case["name"])}</title><style>
body{{font:15px/1.65 system-ui,sans-serif;color:#172d33;background:#f4f7f6;margin:0}}main{{max-width:1080px;margin:auto;padding:50px 30px}}header{{border-bottom:3px solid #187f71;padding-bottom:24px}}h1{{font-size:32px}}h2{{margin-top:40px}}h3{{margin:0 0 8px}}small,.muted{{color:#52676c}}article{{padding:22px;border:1px solid #cbd8d6;background:white;margin:16px 0;border-radius:8px}}code,pre{{font:12px/1.6 ui-monospace,monospace;overflow-wrap:anywhere;white-space:pre-wrap}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #cbd8d6;overflow-wrap:anywhere}}a{{color:#126f63}}.tag{{font-size:12px;font-weight:650;color:#126f63}}img{{max-width:100%;max-height:300px}}@media print{{body{{background:white}}article{{break-inside:avoid}}main{{padding:0}}}}
</style><main><header><div class="tag">STEGANALYSIS / INVESTIGATION REPORT</div><h1>{e(case["name"])}</h1><p>{e(case["description"])}</p><small>Exported {e(data["exported_at"])} · v{__version__}</small></header>
<p>{e(data["limitations"])}</p><h2>Analyst notes</h2><pre>{e(case.get("notes") or "No notes recorded.")}</pre>
<h2>Investigation narrative</h2><small>Authorship: {e(case.get("report_author", "analyst"))}; editable draft, requires analyst review.</small><pre>{e(case.get("report_draft") or "No narrative recorded.")}</pre><h2>Evidence & provenance</h2>"""
    ]
    for a in data["artifacts"]:
        parent = (
            f'<a href="#{e(a["parent_id"])}">{e(a["parent_id"])}</a>' if a["parent_id"] else "Original upload"
        )
        parts.append(
            f'<article id="{e(a["id"])}"><h3>{e(a["name"])}</h3><span class="tag">{e(a["role"])} · {e(a["mime"])} · {a["size"]:,} bytes</span><p><code>SHA-256 {e(a["sha256"])}</code></p><p>Parent: {parent} · Run: {e(a["run_id"])}</p><pre>{e(json.dumps(a["location"], indent=2))}</pre></article>'
        )
    parts.append("<h2>Findings</h2>")
    for f in data["findings"]:
        links = " · ".join(f'<a href="#{e(id)}">{e(id)}</a>' for id in f["supporting"])
        parts.append(
            f'<article id="{e(f["id"])}"><span class="tag">{e(f["category"])} · {e(f["review"]["status"])}</span><h3>{e(f["title"])}</h3><p>{e(f["interpretation"])}</p><p><b>Alternative explanation:</b> {e(f["contradictory"] or "See limitations.")}</p><p><b>Limitations:</b> {e(f["limitations"])}</p><p>{links}</p><pre>{e(json.dumps(f["location"], indent=2))}</pre><small>{e(f["analyzer"])} v{e(f["analyzer_version"])} · {e(f["id"])}</small><p>Review note: {e(f["review"]["note"])}</p></article>'
        )
    parts.append("<h2>Execution manifests</h2>")
    for job in data["jobs"]:
        parts.append(
            f"<article><h3>{e(job['profile'])} · {e(job['status'])}</h3><pre>{e(json.dumps(job, indent=2))}</pre></article>"
        )
    parts.append("<h2>Analysis runs — including failures and skips</h2>")
    for run in data["runs"]:
        parts.append(
            f'<article id="{e(run["id"])}"><h3>{e(run["analyzer"])} · {e(run["status"])}</h3><p>{e(run.get("error") or "")}</p><pre>{e(json.dumps(run, indent=2))}</pre></article>'
        )
    parts.append("<h2>Assistant history</h2>")
    for message in data["messages"]:
        parts.append(
            f"<article><h3>{e(message['question'])}</h3><small>{e(message['provider'])} · {e(message['created_at'])}</small><pre>{e(json.dumps(message['content'], indent=2, ensure_ascii=False))}</pre></article>"
        )
    parts.append("<h2>Visual exhibits</h2>")
    total = 0
    for a in store.list("artifacts", case_id):
        if a["role"] == "preview" and a["mime"] == "image/png" and total + a["size"] < 4 * 1024 * 1024:
            total += a["size"]
            parts.append(
                f'<figure><img alt="{e(a["name"])}" src="data:image/png;base64,{base64.b64encode(artifact_path(store, a).read_bytes()).decode()}"><figcaption>{e(a["name"])} · {e(a["id"])}</figcaption></figure>'
            )
    parts.append(
        "<footer><hr>StegAnalysis · Original creators: Mohamed Abdelgalil (AlBrmagawi) and Spooky. Evidence processing is local by default. No universal detection claim.</footer></main></html>"
    )
    return "\n".join(parts)
