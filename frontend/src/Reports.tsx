import { useState } from "react";
import {
  ArrowDownToLine,
  Check,
  FileCheck2,
  FileJson,
  FileText,
  Printer,
} from "lucide-react";
import type { Snapshot } from "./types";
import { api } from "./api";
import { Badge } from "./ui";

export default function Reports({
  snapshot,
  refresh,
  run,
  onNotice,
}: {
  snapshot: Snapshot;
  refresh: () => Promise<void>;
  run: (action: () => Promise<void>) => Promise<void>;
  onNotice: (text: string) => void;
}) {
  const [draft, setDraft] = useState(snapshot.case.report_draft);
  const [author, setAuthor] = useState(snapshot.case.report_author);
  const originals = snapshot.artifacts.filter((a) => a.role === "original");
  const reviewed = snapshot.findings.filter(
    (f) => f.review.status !== "unreviewed",
  ).length;
  const save = async () => {
    await api(`/cases/${snapshot.case.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        report_draft: draft,
        report_author: author,
      }),
    });
    await refresh();
    onNotice("Investigation narrative saved.");
  };
  return (
    <div className="page reports-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">MAKE THE REASONING REPRODUCIBLE</div>
          <h1>Investigation report</h1>
          <p className="muted">
            A record of the evidence, methods, and conclusions you can stand
            behind.
          </p>
        </div>
        <Badge>{snapshot.case.name}</Badge>
      </div>
      <div className="report-layout">
        <div>
          <section className="surface report-readiness">
            <h2>
              <FileCheck2 size={20} />
              Case record
            </h2>
            <div className="report-counts">
              <div>
                <strong>{originals.length}</strong>
                <span>original files</span>
              </div>
              <div>
                <strong>{snapshot.runs.length}</strong>
                <span>analyzer runs</span>
              </div>
              <div>
                <strong>{snapshot.findings.length}</strong>
                <span>findings</span>
              </div>
              <div>
                <strong>{reviewed}</strong>
                <span>reviewed</span>
              </div>
            </div>
            <p className="caption">
              Exports include all run history and findings, including failures,
              skips, review notes and explicit limitations.
            </p>
          </section>
          <section className="surface narrative-editor">
            <div className="section-toolbar">
              <h2>Investigation narrative</h2>
              <Badge>
                {author === "model"
                  ? "MODEL-AUTHORED DRAFT"
                  : author === "deterministic"
                    ? "DETERMINISTIC DRAFT"
                    : "ANALYST-AUTHORED"}
              </Badge>
            </div>
            <p className="muted">
              State what was measured, consider alternative explanations, and
              distinguish your conclusion from a heuristic.
            </p>
            <label className="field">
              Editable report draft
              <textarea
                aria-label="Report narrative"
                rows={16}
                maxLength={40000}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={
                  "Purpose of examination…\n\nEvidence and methods…\n\nObservations and alternatives…\n\nAnalyst conclusions and limitations…"
                }
              />
            </label>
            <label className="field">
              Authorship
              <select
                value={author}
                onChange={(e) => setAuthor(e.target.value as typeof author)}
              >
                <option value="analyst">Analyst-authored</option>
                <option value="deterministic">
                  Deterministic guide draft, analyst edited
                </option>
                <option value="model">
                  Model-authored draft, analyst edited
                </option>
              </select>
            </label>
            <div className="section-toolbar">
              <span className="caption">
                {draft === snapshot.case.report_draft &&
                author === snapshot.case.report_author
                  ? "All changes saved"
                  : "Unsaved changes — save before export"}
              </span>
              <button className="button primary" onClick={() => void run(save)}>
                <Check size={15} />
                Save narrative
              </button>
            </div>
          </section>
        </div>
        <aside>
          <section className="surface export-panel">
            <h2>Export case report</h2>
            <p className="muted">
              Self-contained, escaped content. No remote fonts, trackers, or
              active evidence.
            </p>
            <a
              className="export-option"
              href={`/api/cases/${snapshot.case.id}/report.html`}
              download
            >
              <FileText size={22} />
              <div>
                <strong>HTML report</strong>
                <span>Readable, self-contained report</span>
              </div>
              <ArrowDownToLine size={16} />
            </a>
            <a
              className="export-option"
              href={`/api/cases/${snapshot.case.id}/report.json`}
              download
            >
              <FileJson size={22} />
              <div>
                <strong>Structured JSON</strong>
                <span>Full evidence & provenance records</span>
              </div>
              <ArrowDownToLine size={16} />
            </a>
            <div className="print-note">
              <Printer size={17} />
              <p>
                For PDF, open the downloaded HTML report and use your browser’s
                Print → Save as PDF. Server-side PDF export is not enabled.
              </p>
            </div>
          </section>
          <section className="surface">
            <h3>Included in every export</h3>
            <ul className="report-inclusions">
              {[
                "Original and derived SHA-256 hashes",
                "Analyzer versions and parameters",
                "Finding locations and evidence references",
                "Provenance links and run history",
                "Analyst notes and review decisions",
                "Labeled assistant conversations",
                "Failures, skips, timestamps and limitations",
              ].map((item) => (
                <li key={item}>
                  <Check size={14} />
                  {item}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
