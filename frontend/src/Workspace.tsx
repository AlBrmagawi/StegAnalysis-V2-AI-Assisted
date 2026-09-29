import { useEffect, useRef, useState } from "react";
import type { CSSProperties, PointerEvent } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Braces,
  Check,
  ChevronDown,
  ChevronRight,
  FileSearch,
  GitBranch,
  Image as ImageIcon,
  Layers,
  ListFilter,
  Maximize2,
  MessageSquare,
  Minus,
  Plus,
  Search,
  SlidersHorizontal,
  StickyNote,
} from "lucide-react";
import type { Artifact, Finding, Health, Snapshot } from "./types";
import { api, bytes, contentUrl, date } from "./api";
import { Badge, Chart, Empty, FileIcon, navigateTabs } from "./ui";
import Assistant from "./Assistant";

type Props = {
  snapshot: Snapshot;
  health: Health | null;
  refresh: () => Promise<void>;
  run: (action: () => Promise<void>) => Promise<void>;
  onUpload: () => void;
  onAnalyze: () => void;
  onReport: () => void;
  onNotice: (text: string) => void;
};

export default function Workspace({
  snapshot,
  health,
  refresh,
  run,
  onUpload,
  onAnalyze,
  onReport,
  onNotice,
}: Props) {
  const [selectedId, setSelectedId] = useState(snapshot.artifacts[0]?.id || "");
  const [findingId, setFindingId] = useState("");
  const [selectedFindings, setSelectedFindings] = useState<string[]>([]);
  const [inspector, setInspector] = useState("findings");
  const [query, setQuery] = useState(""),
    [findingQuery, setFindingQuery] = useState(""),
    [category, setCategory] = useState("all"),
    [findingSort, setFindingSort] = useState("recovered");
  const [tab, setTab] = useState("preview");
  const [leftWidth, setLeftWidth] = useState(
    Number(localStorage.getItem("steg-tree-width")) || 240,
  );
  const [rightWidth, setRightWidth] = useState(
    Number(localStorage.getItem("steg-inspector-width")) || 340,
  );
  const workspace = useRef<HTMLDivElement>(null);
  const artifact =
    snapshot.artifacts.find((a) => a.id === selectedId) ||
    snapshot.artifacts[0];
  const originals = snapshot.artifacts.filter((a) => a.role === "original");
  const matching = snapshot.findings
    .filter(
      (f) =>
        (category === "all" || category === f.category) &&
        `${f.title} ${f.interpretation} ${f.analyzer}`
          .toLowerCase()
          .includes(findingQuery.toLowerCase()),
    )
    .sort((a, b) =>
      findingSort === "title"
        ? a.title.localeCompare(b.title)
        : findingSort === "review"
          ? a.review.status.localeCompare(b.review.status)
          : (a.category === "recovered" ? -1 : 1) -
            (b.category === "recovered" ? -1 : 1),
    );
  const jump = (id: string) => {
    setSelectedId(id);
    setTab("preview");
  };
  const cite = (id: string) => {
    setFindingId(id);
    setInspector("findings");
    setFindingQuery("");
    setCategory("all");
    const f = snapshot.findings.find((f) => f.id === id);
    if (f) jump(f.supporting[0] || f.artifact_id);
  };
  const resize = (e: PointerEvent<HTMLDivElement>, side: "left" | "right") => {
    e.currentTarget.setPointerCapture(e.pointerId);
    const origin = e.clientX,
      initial = side === "left" ? leftWidth : rightWidth;
    const move = (event: globalThis.PointerEvent) => {
      const value = Math.round(
        Math.min(
          side === "left" ? 400 : 540,
          Math.max(
            side === "left" ? 190 : 290,
            initial + (event.clientX - origin) * (side === "left" ? 1 : -1),
          ),
        ),
      );
      if (side === "left") {
        setLeftWidth(value);
        localStorage.setItem("steg-tree-width", String(value));
      } else {
        setRightWidth(value);
        localStorage.setItem("steg-inspector-width", String(value));
      }
    };
    const end = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end, { once: true });
  };
  const toggleFinding = (id: string) =>
    setSelectedFindings((selected) =>
      selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id].slice(-12),
    );
  const scope = selectedFindings.length
    ? selectedFindings
    : findingId
      ? [findingId]
      : snapshot.findings
          .filter((f) => f.artifact_id === artifact?.id)
          .slice(0, 6)
          .map((f) => f.id);
  return (
    <div
      ref={workspace}
      className="workspace"
      style={
        {
          "--tree-width": `${leftWidth}px`,
          "--inspector-width": `${rightWidth}px`,
        } as CSSProperties
      }
    >
      <aside className="evidence-pane" aria-label="Evidence tree">
        <div className="pane-heading">
          <span>EVIDENCE</span>
          <Badge>{originals.length}</Badge>
          <button
            className="icon-button"
            aria-label="Add evidence to case"
            onClick={onUpload}
          >
            <Plus size={16} />
          </button>
        </div>
        <label className="search-field tree-search">
          <Search size={14} />
          <input
            aria-label="Filter artifacts"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find an artifact…"
          />
        </label>
        <div className="tree-scroll">
          {!originals.length ? (
            <Empty icon={<FileSearch size={28} />} title="No evidence yet">
              <p>Add a file to begin.</p>
              <button className="button small" onClick={onUpload}>
                Add evidence
              </button>
            </Empty>
          ) : (
            originals.map((original, index) => (
              <div className="tree-group" key={original.id}>
                <div className="tree-group-label">
                  SOURCE {String(index + 1).padStart(2, "0")}
                </div>
                <ArtifactBranch
                  artifact={original}
                  artifacts={snapshot.artifacts}
                  selected={artifact?.id}
                  onSelect={jump}
                  query={query}
                />
              </div>
            ))
          )}
        </div>
        <div className="evidence-bottom">
          <ShieldMini />
          <div>
            Evidence integrity<small>SHA-256 at ingestion</small>
          </div>
        </div>
      </aside>
      <div
        className="resize-handle"
        role="separator"
        aria-label="Resize evidence tree"
        aria-orientation="vertical"
        aria-valuenow={leftWidth}
        aria-valuemin={190}
        aria-valuemax={400}
        tabIndex={0}
        onPointerDown={(e) => resize(e, "left")}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight")
            setLeftWidth(Math.min(400, leftWidth + 20));
          if (e.key === "ArrowLeft")
            setLeftWidth(Math.max(190, leftWidth - 20));
        }}
      />
      <section className="viewer-pane" aria-label="Artifact viewer">
        <div className="viewer-heading">
          <div className="viewer-filename">
            <FileIcon kind={artifact?.kind || ""} />
            <span>{artifact?.name || "Investigation workspace"}</span>
          </div>
          {artifact && (
            <a
              className="icon-button"
              aria-label="Download selected artifact"
              title="Download original artifact bytes"
              href={contentUrl(snapshot.case.id, artifact.id, true)}
            >
              <ArrowDownToLine size={16} />
            </a>
          )}
        </div>
        <div
          className="tabbar viewer-tabs"
          role="tablist"
          aria-label="Artifact views"
          onKeyDown={navigateTabs}
        >
          {[
            ["preview", "Preview", ImageIcon],
            ["measurements", "Measurements", SlidersHorizontal],
            ["provenance", "Provenance", GitBranch],
            ["runs", "Run history", Layers],
          ].map(([id, label, Icon]) => {
            const I = Icon as typeof ImageIcon;
            return (
              <button
                key={String(id)}
                role="tab"
                aria-selected={tab === id}
                tabIndex={tab === id ? 0 : -1}
                onClick={() => setTab(String(id))}
              >
                <I size={14} />
                {String(label)}
              </button>
            );
          })}
        </div>
        {!artifact ? (
          <Empty
            icon={<Layers size={38} />}
            title="Every investigation starts with evidence"
          >
            <p>
              Add a PDF, image, WAV or text file.
              <br />
              Analysis will create traceable findings and artifacts.
            </p>
            <button className="button primary" onClick={onUpload}>
              <Plus size={16} />
              Add evidence
            </button>
          </Empty>
        ) : (
          <div
            className={`viewer-content ${tab === "preview" ? "preview-content" : ""}`}
          >
            {tab === "preview" && (
              <Preview
                key={artifact.id}
                artifact={artifact}
                snapshot={snapshot}
                onJump={jump}
                onAnalyze={onAnalyze}
              />
            )}
            {tab === "measurements" && (
              <Measurements artifact={artifact} snapshot={snapshot} />
            )}
            {tab === "provenance" && (
              <Provenance
                artifact={artifact}
                snapshot={snapshot}
                onJump={jump}
              />
            )}
            {tab === "runs" && (
              <div className="runs-view">
                <div className="eyebrow">PERSISTENT EXECUTION HISTORY</div>
                <h2>What actually ran</h2>
                <p className="muted">
                  All case runs are retained, including skipped and failed
                  analyzers.
                </p>
                {!snapshot.runs.length && (
                  <Empty title="No analysis runs yet">
                    <button className="button primary" onClick={onAnalyze}>
                      Configure analysis
                    </button>
                  </Empty>
                )}
                {snapshot.jobs
                  .slice()
                  .reverse()
                  .map((job) => (
                    <section className="run-group" key={job.id}>
                      <div className="section-toolbar">
                        <strong>{job.profile} profile</strong>
                        <Badge tone={job.status}>{job.status}</Badge>
                      </div>
                      <p className="caption">
                        {date(job.created_at)} · {job.completed}/{job.total}{" "}
                        tasks · <code>{job.id.slice(-10)}</code>
                      </p>
                      {snapshot.runs
                        .filter(
                          (r) =>
                            r.id &&
                            snapshot.artifacts.some(
                              (a) => a.id === r.artifact_id,
                            ) &&
                            (r as typeof r & { job_id: string }).job_id ===
                              job.id,
                        )
                        .map((r) => (
                          <details className="run-row" key={r.id}>
                            <summary>
                              <span>{r.analyzer}</span>
                              <Badge tone={r.status}>{r.status}</Badge>
                              <span className="caption">
                                {r.duration_seconds?.toFixed(2) ?? "—"}s
                              </span>
                            </summary>
                            <p>
                              {
                                snapshot.artifacts.find(
                                  (a) => a.id === r.artifact_id,
                                )?.name
                              }
                            </p>
                            {r.error && (
                              <p className="inline-error">{r.error}</p>
                            )}
                            <pre>
                              {JSON.stringify(
                                { parameters: r.parameters, result: r.result },
                                null,
                                2,
                              )}
                            </pre>
                          </details>
                        ))}
                    </section>
                  ))}
              </div>
            )}
          </div>
        )}
        {artifact && (
          <div className="artifact-footer">
            <span>
              {artifact.mime} · {bytes(artifact.size)}
            </span>
            <code title={artifact.sha256}>
              SHA-256 {artifact.sha256.slice(0, 16)}…
            </code>
          </div>
        )}
      </section>
      <div
        className="resize-handle"
        role="separator"
        aria-label="Resize inspector"
        aria-orientation="vertical"
        aria-valuenow={rightWidth}
        aria-valuemin={290}
        aria-valuemax={540}
        tabIndex={0}
        onPointerDown={(e) => resize(e, "right")}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft")
            setRightWidth(Math.min(540, rightWidth + 20));
          if (e.key === "ArrowRight")
            setRightWidth(Math.max(290, rightWidth - 20));
        }}
      />
      <aside className="inspector-pane" aria-label="Findings and assistant">
        <div
          className="tabbar inspector-tabs"
          role="tablist"
          aria-label="Inspector"
          onKeyDown={navigateTabs}
        >
          {[
            ["findings", "Findings", ListFilter],
            ["assistant", "Assistant", MessageSquare],
            ["notes", "Notes", StickyNote],
          ].map(([id, label, Icon]) => {
            const I = Icon as typeof ImageIcon;
            return (
              <button
                key={String(id)}
                role="tab"
                aria-selected={inspector === id}
                tabIndex={inspector === id ? 0 : -1}
                onClick={() => setInspector(String(id))}
              >
                <I size={14} />
                {String(label)}
                {id === "findings" && (
                  <span className="tab-count">{snapshot.findings.length}</span>
                )}
              </button>
            );
          })}
        </div>
        {inspector === "findings" && (
          <>
            <div className="finding-tools">
              <label className="search-field">
                <Search size={14} />
                <input
                  aria-label="Search findings"
                  value={findingQuery}
                  onChange={(e) => setFindingQuery(e.target.value)}
                  placeholder="Search findings…"
                />
              </label>
              <div className="finding-filter">
                <select
                  aria-label="Filter finding category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="all">All observations</option>
                  <option value="heuristic">Heuristic indicators</option>
                  <option value="recovered">Recovered content</option>
                  <option value="observation">Observations</option>
                  <option value="experimental">Experimental ML</option>
                </select>
                <select
                  aria-label="Sort findings"
                  value={findingSort}
                  onChange={(e) => setFindingSort(e.target.value)}
                >
                  <option value="recovered">Recovered first</option>
                  <option value="title">Title</option>
                  <option value="review">Review status</option>
                </select>
              </div>
            </div>
            <div className="findings-scroll">
              {!matching.length ? (
                <Empty
                  icon={<FileSearch size={26} />}
                  title={
                    snapshot.findings.length
                      ? "No matching findings"
                      : "Findings will appear here"
                  }
                >
                  <p>
                    {snapshot.findings.length
                      ? "Adjust your filters to inspect other observations."
                      : "Run analysis to inspect measurements, indicators, and recovered content."}
                  </p>
                </Empty>
              ) : (
                matching.map((f) => (
                  <FindingCard
                    key={f.id}
                    finding={f}
                    expanded={findingId === f.id}
                    selected={selectedFindings.includes(f.id)}
                    onToggle={() =>
                      setFindingId(findingId === f.id ? "" : f.id)
                    }
                    onSelect={() => toggleFinding(f.id)}
                    onJump={jump}
                    snapshot={snapshot}
                    onReview={(review) =>
                      run(async () => {
                        await api(
                          `/cases/${snapshot.case.id}/findings/${f.id}`,
                          { method: "PATCH", body: JSON.stringify(review) },
                        );
                        await refresh();
                        onNotice("Finding review saved.");
                      })
                    }
                  />
                ))
              )}
            </div>
            <div className="inspector-footer">
              <p>
                {selectedFindings.length
                  ? `${selectedFindings.length} findings selected for the assistant`
                  : "Select findings to ask an evidence-specific question."}
              </p>
              <button
                className="button full-width"
                onClick={() => setInspector("assistant")}
              >
                <MessageSquare size={15} />
                Ask about the evidence
                <ArrowRight size={14} />
              </button>
            </div>
          </>
        )}
        {inspector === "assistant" && (
          <Assistant
            snapshot={snapshot}
            health={health}
            findingIds={scope}
            onCite={cite}
            refresh={refresh}
            run={run}
            onReport={onReport}
            onNotice={onNotice}
          />
        )}
        {inspector === "notes" && (
          <Notes
            snapshot={snapshot}
            refresh={refresh}
            run={run}
            onNotice={onNotice}
          />
        )}
      </aside>
    </div>
  );
}

function ShieldMini() {
  return <Check size={16} className="accent" />;
}

function ArtifactBranch({
  artifact,
  artifacts,
  selected,
  onSelect,
  query,
}: {
  artifact: Artifact;
  artifacts: Artifact[];
  selected?: string;
  onSelect: (id: string) => void;
  query: string;
}) {
  const children = artifacts.filter((a) => a.parent_id === artifact.id);
  const extracted = children.filter((a) => a.role === "extracted"),
    derived = children.filter((a) => a.role !== "extracted");
  const visible =
    !query ||
    artifact.name.toLowerCase().includes(query.toLowerCase()) ||
    children.some((a) => a.name.toLowerCase().includes(query.toLowerCase()));
  if (!visible) return null;
  return (
    <div className="artifact-branch">
      <button
        className={`tree-file ${selected === artifact.id ? "selected" : ""}`}
        onClick={() => onSelect(artifact.id)}
        title={artifact.name}
      >
        <FileIcon kind={artifact.kind} />
        <span>
          {artifact.name}
          <small>
            {artifact.role === "original"
              ? `${bytes(artifact.size)} · original`
              : artifact.role}
          </small>
        </span>
      </button>
      {extracted.map((a) => (
        <div className="tree-nested" key={a.id}>
          <ArtifactBranch
            artifact={a}
            artifacts={artifacts}
            selected={selected}
            onSelect={onSelect}
            query={query}
          />
        </div>
      ))}
      {derived.length > 0 && (
        <details className="derived-tree" open={query ? true : undefined}>
          <summary>
            <ChevronRight size={12} />
            {derived.length} derived artifacts
          </summary>
          {derived
            .filter(
              (a) =>
                !query || a.name.toLowerCase().includes(query.toLowerCase()),
            )
            .map((a) => (
              <button
                key={a.id}
                className={`tree-file derived ${selected === a.id ? "selected" : ""}`}
                onClick={() => onSelect(a.id)}
                title={a.name}
              >
                <FileIcon kind={a.kind} size={13} />
                <span>{a.name}</span>
              </button>
            ))}
        </details>
      )}
    </div>
  );
}

function Preview({
  artifact,
  snapshot,
  onJump,
  onAnalyze,
}: {
  artifact: Artifact;
  snapshot: Snapshot;
  onJump: (id: string) => void;
  onAnalyze: () => void;
}) {
  const [preview, setPreview] = useState<{
    text?: string;
    hex?: string;
    truncated?: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  const isImage = artifact.kind === "image",
    isAudio = artifact.kind === "audio";
  const source =
    isImage && !["original", "extracted"].includes(artifact.role)
      ? snapshot.artifacts.find(
          (a) => a.id === artifact.parent_id && a.kind === "image",
        ) || artifact
      : artifact;
  useEffect(() => {
    if (isImage || isAudio) return;
    let live = true;
    api<{ text?: string; hex?: string; truncated?: boolean }>(
      `/cases/${snapshot.case.id}/artifacts/${artifact.id}/preview`,
    )
      .then((data) => {
        if (live) setPreview(data);
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [artifact.id, snapshot.case.id, isImage, isAudio]);
  if (isImage) {
    const safePreview = snapshot.artifacts.some(
      (a) => a.parent_id === source.id && a.role === "preview",
    );
    if (["original", "extracted"].includes(source.role) && !safePreview)
      return (
        <Empty
          icon={<ImageIcon size={28} />}
          title="Image preview awaits bounded decoding"
        >
          <p>
            Run analysis to validate dimensions and generate a safe, lossless
            preview. Original bytes remain available as a download.
          </p>
          <button className="button" onClick={onAnalyze}>
            Configure analysis
          </button>
        </Empty>
      );
    return (
      <ImagePreview artifact={artifact} source={source} snapshot={snapshot} />
    );
  }
  if (isAudio) {
    const run = snapshot.runs
      .filter(
        (r) =>
          r.artifact_id === artifact.id &&
          r.analyzer === "audio" &&
          r.status === "completed",
      )
      .at(-1);
    const spectrum = snapshot.artifacts.find(
      (a) => a.id === run?.result.spectrogram_id,
    );
    return (
      <div className="audio-preview">
        <div className="eyebrow">PCM AUDIO INSPECTION</div>
        <h2>{artifact.name}</h2>
        <audio
          controls
          preload="metadata"
          src={contentUrl(snapshot.case.id, artifact.id)}
        >
          Your browser does not support WAV playback.
        </audio>
        {run?.result.waveform && (
          <>
            <h3>Waveform envelope</h3>
            <Chart
              values={run.result.waveform.map((p) =>
                Math.max(Math.abs(p.min), p.max),
              )}
              max={1}
              label="PCM waveform absolute peak amplitude"
            />
            <div className="chart-axis">
              <span>0 s</span>
              <span>
                {Number(run.result.frames_inspected) /
                  Number(run.result.sample_rate)}{" "}
                s inspected
              </span>
            </div>
          </>
        )}
        {spectrum && (
          <>
            <h3>Spectrogram</h3>
            <div className="spectrum-frame">
              <img
                alt="Measured WAV spectrogram, low frequencies at bottom"
                src={contentUrl(snapshot.case.id, spectrum.id)}
              />
              <div className="chart-axis">
                <span>
                  0 Hz →{" "}
                  {Number(spectrum.metadata.frequency_max).toLocaleString()} Hz
                  (vertical)
                </span>
                <span>Time →</span>
              </div>
            </div>
            <button className="text-button" onClick={() => onJump(spectrum.id)}>
              Open supporting spectrogram
              <ArrowRight size={14} />
            </button>
          </>
        )}
        {!run && (
          <Empty title="Sample analysis not available yet">
            <button className="button" onClick={onAnalyze}>
              Configure analysis
            </button>
          </Empty>
        )}
      </div>
    );
  }
  const children = snapshot.artifacts.filter(
    (a) => a.parent_id === artifact.id && a.role === "extracted",
  );
  return (
    <div className="document-preview">
      <div className="eyebrow">
        {artifact.kind === "pdf"
          ? "PDF EVIDENCE"
          : artifact.kind === "text"
            ? "TEXT EVIDENCE"
            : "BOUNDED BYTE PREVIEW"}
      </div>
      <h2>{artifact.name}</h2>
      {artifact.kind === "pdf" && (
        <>
          <p className="muted">
            Inspect parser-extracted pages and attachments below. The original
            PDF is available as a download.
          </p>
          {children.length ? (
            <div className="document-children">
              {children.map((a) => (
                <button key={a.id} onClick={() => onJump(a.id)}>
                  <FileIcon kind={a.kind} />
                  <span>
                    {a.name}
                    <small>
                      {Object.entries(a.location)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(" · ")}
                    </small>
                  </span>
                  <ArrowRight size={16} />
                </button>
              ))}
            </div>
          ) : (
            <Empty title="No extracted artifacts yet">
              <button className="button" onClick={onAnalyze}>
                Run analysis
              </button>
            </Empty>
          )}
        </>
      )}
      {artifact.kind !== "pdf" && (
        <>
          <div className="preview-note">
            <Braces size={14} />
            {preview?.text !== undefined
              ? "Rendered as inert text. Invisible characters may not be visible; inspect location findings."
              : "First 4 KiB in hexadecimal; offsets start at zero."}
          </div>
          {error ? (
            <p className="inline-error">{error}</p>
          ) : preview ? (
            <pre className="text-preview">
              {preview.text ??
                preview.hex
                  ?.match(/.{1,48}/g)
                  ?.map(
                    (line, i) =>
                      `${(i * 16).toString(16).padStart(8, "0")}  ${line}`,
                  )
                  .join("\n")}
            </pre>
          ) : (
            <p className="muted">Loading preview…</p>
          )}
          {preview?.truncated && (
            <p className="caption">
              Preview truncated. Download the artifact to inspect all bytes.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function ImagePreview({
  artifact,
  source,
  snapshot,
}: {
  artifact: Artifact;
  source: Artifact;
  snapshot: Snapshot;
}) {
  const views = snapshot.artifacts.filter(
    (a) => a.parent_id === source.id && a.kind === "image",
  );
  const latestRun = snapshot.runs
    .filter((r) => r.artifact_id === source.id && r.analyzer === "image")
    .at(-1);
  const latestViews = views.filter((a) => a.run_id === latestRun?.id);
  const original = latestViews.find((a) => a.role === "preview") || source;
  const [chosen, setChosen] = useState(
    artifact.id !== source.id
      ? artifact.id
      : latestViews.find(
          (a) =>
            a.metadata.view === "bit-plane" &&
            a.metadata.channel === "R" &&
            a.metadata.plane === 0,
        )?.id || original.id,
  );
  const [zoom, setZoom] = useState(1),
    [pan, setPan] = useState({ x: 0, y: 0 }),
    [compare, setCompare] = useState(true);
  const selected = views.find((a) => a.id === chosen) || artifact;
  const [channel, setChannel] = useState(
      String(selected.metadata.channel || "R"),
    ),
    [plane, setPlane] = useState(Number(selected.metadata.plane || 0));
  const [mode, setMode] = useState(
    String(selected.metadata.view || "original"),
  );
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(
    null,
  );
  const choose = (view: string, ch = channel, bit = plane) => {
    setMode(view);
    setChannel(ch);
    setPlane(bit);
    const target = latestViews.find(
      (a) =>
        a.metadata.view === view &&
        (view === "bit-plane"
          ? a.metadata.channel === ch && a.metadata.plane === bit
          : view === "channel"
            ? a.metadata.channel === ch
            : true),
    );
    if (target) setChosen(target.id);
    else if (view === "original") setChosen(original.id);
  };
  const panStart = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
  };
  const available = latestViews.length > 0;
  return (
    <div className="image-inspection">
      <div className="image-controls">
        <div>
          <label>
            View
            <select
              aria-label="Derived image view"
              value={mode}
              onChange={(e) => choose(e.target.value)}
            >
              {[
                "original",
                "channel",
                "bit-plane",
                "grayscale",
                "negative",
                "residual",
              ]
                .filter(
                  (v) =>
                    v === "original" ||
                    latestViews.some((a) => a.metadata.view === v),
                )
                .map((v) => (
                  <option key={v} value={v}>
                    {v === "bit-plane"
                      ? "Bit plane"
                      : v[0].toUpperCase() + v.slice(1)}
                  </option>
                ))}
            </select>
          </label>
          {["bit-plane", "channel"].includes(mode) && (
            <label>
              Channel
              <select
                aria-label="Image channel"
                value={channel}
                onChange={(e) => choose(mode, e.target.value)}
              >
                {["R", "G", "B", "A"]
                  .filter((c) =>
                    latestViews.some((a) => a.metadata.channel === c),
                  )
                  .map((c) => (
                    <option key={c}>{c}</option>
                  ))}
              </select>
            </label>
          )}
          {mode === "bit-plane" && (
            <label>
              Plane
              <select
                aria-label="Image bit plane"
                value={plane}
                onChange={(e) => choose(mode, channel, Number(e.target.value))}
              >
                {[0, 1, 2, 3, 4, 5, 6, 7]
                  .filter((p) =>
                    latestViews.some(
                      (a) =>
                        a.metadata.view === "bit-plane" &&
                        a.metadata.channel === channel &&
                        a.metadata.plane === p,
                    ),
                  )
                  .map((p) => (
                    <option key={p} value={p}>
                      {p}
                      {p === 0 ? " · LSB" : p === 7 ? " · MSB" : ""}
                    </option>
                  ))}
              </select>
            </label>
          )}
        </div>
        <button
          className={`button small ${compare ? "selected" : ""}`}
          aria-pressed={compare}
          onClick={() => setCompare(!compare)}
        >
          <Layers size={14} />
          Compare
        </button>
      </div>
      <div
        className={`image-stage ${compare ? "comparison" : ""}`}
        onPointerDown={panStart}
        onPointerMove={(e) => {
          if (drag.current)
            setPan({
              x: drag.current.px + e.clientX - drag.current.x,
              y: drag.current.py + e.clientY - drag.current.y,
            });
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
      >
        {compare && (
          <div className="image-cell">
            <div className="image-cell-label">
              <span>01 / ORIGINAL</span>
              <span>decoded pixels</span>
            </div>
            <div className="image-frame">
              <img
                draggable={false}
                alt={`Original decoded image: ${source.name}`}
                src={contentUrl(snapshot.case.id, original.id)}
                style={{
                  transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`,
                }}
              />
            </div>
            <div className="image-cell-caption">{source.name}</div>
          </div>
        )}
        <div className="image-cell">
          <div className="image-cell-label">
            <span>
              {compare ? "02 / " : ""}
              {mode.toUpperCase()}
            </span>
            {Boolean(selected.metadata.channel) && (
              <span>
                {String(selected.metadata.channel)}
                {selected.metadata.plane !== undefined
                  ? ` · bit ${selected.metadata.plane}`
                  : ""}
              </span>
            )}
          </div>
          <div className="image-frame">
            <img
              draggable={false}
              alt={`Selected derived view: ${selected.name}`}
              src={contentUrl(snapshot.case.id, selected.id)}
              style={{
                transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`,
                imageRendering: mode === "bit-plane" ? "pixelated" : "auto",
              }}
            />
          </div>
          <div className="image-cell-caption">{selected.name}</div>
        </div>
      </div>
      <div className="image-zoom">
        <span>
          <span className="status-dot" />
          Synchronized zoom & pan
        </span>
        <div>
          <button
            className="icon-button"
            aria-label="Zoom out"
            onClick={() => setZoom(Math.max(0.25, zoom - 0.25))}
          >
            <Minus size={14} />
          </button>
          <output>{Math.round(zoom * 100)}%</output>
          <button
            className="icon-button"
            aria-label="Zoom in"
            onClick={() => setZoom(Math.min(6, zoom + 0.25))}
          >
            <Plus size={14} />
          </button>
          <button
            className="icon-button"
            aria-label="Reset image view"
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
      <div className="image-info">
        <div className="eyebrow">READ THE MEASUREMENT IN CONTEXT</div>
        <p>
          {mode === "bit-plane"
            ? "Each pixel shows a single bit of the decoded channel. Structure, noise, or apparent randomness alone does not establish an embedded payload."
            : mode === "residual"
              ? "Absolute grayscale difference from a 3 × 3 median filter, amplified 8×. Edges and sensor noise also create residual structure."
              : "Views are generated losslessly from decoded pixels. JPEG coefficient-domain analysis is not performed."}
        </p>
        {!available && (
          <p className="caption">
            Run Standard or Deep analysis to generate channels and bit planes.
          </p>
        )}
        <div className="image-properties">
          <span>
            <b>
              {String(latestRun?.result.width || "—")} ×{" "}
              {String(latestRun?.result.height || "—")}
            </b>
            dimensions
          </span>
          <span>
            <b>{String(latestRun?.result.source_mode || "—")}</b>source mode
          </span>
          <span>
            <b>
              {String(latestRun?.result.format || source.mime.split("/")[1])}
            </b>
            format
          </span>
          <span>
            <b>Lossless PNG</b>derived format
          </span>
        </div>
      </div>
    </div>
  );
}

function Measurements({
  artifact,
  snapshot,
}: {
  artifact: Artifact;
  snapshot: Snapshot;
}) {
  const source = ["original", "extracted"].includes(artifact.role)
    ? artifact
    : snapshot.artifacts.find((a) => a.id === artifact.parent_id) || artifact;
  const runs = snapshot.runs.filter(
    (r) => r.artifact_id === source.id && r.status === "completed",
  );
  const byteRun = runs.filter((r) => r.analyzer === "bytes").at(-1),
    imageRun = runs.filter((r) => r.analyzer === "image").at(-1);
  return (
    <div className="measurements">
      <div className="eyebrow">MEASURED, NOT INFERRED</div>
      <h2>Evidence measurements</h2>
      <p className="caption">Source: {source.name}</p>
      {byteRun && (
        <section className="measurement-block">
          <div className="section-toolbar">
            <h3>Rolling byte entropy</h3>
            <code>{Number(byteRun.result.entropy).toFixed(3)} bits/byte</code>
          </div>
          <Chart
            values={byteRun.result.windows?.map((w) => w.entropy) || []}
            max={8}
            label="Shannon entropy from zero to eight bits per byte"
          />
          <div className="chart-axis">
            <span>0 bytes</span>
            <span>{source.size.toLocaleString()} bytes</span>
          </div>
          <p className="caption">
            Window {String(byteRun.result.window)} B · Stride{" "}
            {String(byteRun.result.stride)} B · Compression and encryption
            commonly produce high entropy.
          </p>
        </section>
      )}
      {imageRun?.result.histograms && (
        <section className="measurement-block">
          <h3>Channel histograms</h3>
          {Object.entries(imageRun.result.histograms).map(
            ([channel, counts]) => (
              <div className="channel-chart" key={channel}>
                <span>{channel}</span>
                <Chart
                  values={counts}
                  label={`${channel} channel histogram, values 0 to 255`}
                  color={
                    channel === "R"
                      ? "#c3988e"
                      : channel === "G"
                        ? "var(--accent)"
                        : channel === "B"
                          ? "#8aafcb"
                          : "var(--muted)"
                  }
                />
              </div>
            ),
          )}
          <div className="chart-axis">
            <span>0</span>
            <span>255 · decoded pixel value</span>
          </div>
        </section>
      )}
      {!runs.length && (
        <Empty title="No measurements yet">
          <p>Run analysis to inspect this source.</p>
        </Empty>
      )}
      <section className="measurement-block">
        <h3>Identity & metadata</h3>
        <dl className="metadata-list">
          <dt>SHA-256</dt>
          <dd>
            <code>{source.sha256}</code>
          </dd>
          <dt>Signature MIME</dt>
          <dd>{source.mime}</dd>
          <dt>Size</dt>
          <dd>{bytes(source.size)}</dd>
          <dt>Role</dt>
          <dd>{source.role}</dd>
          <dt>Location</dt>
          <dd>
            <pre>{JSON.stringify(source.location, null, 2)}</pre>
          </dd>
        </dl>
        {imageRun && (
          <details>
            <summary>Pixel statistics and metadata</summary>
            <pre>
              {JSON.stringify(
                { ...imageRun.result, histograms: undefined },
                null,
                2,
              )}
            </pre>
          </details>
        )}
      </section>
    </div>
  );
}

function Provenance({
  artifact,
  snapshot,
  onJump,
}: {
  artifact: Artifact;
  snapshot: Snapshot;
  onJump: (id: string) => void;
}) {
  const ancestry: Artifact[] = [];
  let parent: Artifact | undefined = artifact;
  const seen = new Set<string>();
  while (parent && !seen.has(parent.id)) {
    ancestry.unshift(parent);
    seen.add(parent.id);
    parent = snapshot.artifacts.find((a) => a.id === parent?.parent_id);
  }
  const children = snapshot.artifacts.filter(
    (a) => a.parent_id === artifact.id,
  );
  const run = snapshot.runs.find((r) => r.id === artifact.run_id);
  return (
    <div className="provenance-view">
      <div className="eyebrow">CHAIN OF DERIVATION</div>
      <h2>Nothing without a source.</h2>
      <p className="muted">
        Navigate the actual artifact relationships recorded during analysis.
      </p>
      <div className="provenance-chain">
        {ancestry.map((a, i) => (
          <div key={a.id}>
            {i > 0 && (
              <div className="chain-edge">
                <span />
                {snapshot.runs.find((r) => r.id === a.run_id)?.analyzer} ·
                v2.0.0
                <ChevronDown size={14} />
              </div>
            )}
            <button
              className={`provenance-node ${a.id === artifact.id ? "selected" : ""}`}
              onClick={() => onJump(a.id)}
            >
              <FileIcon kind={a.kind} size={21} />
              <div>
                <Badge>{a.role}</Badge>
                <strong>{a.name}</strong>
                <code>{a.sha256.slice(0, 24)}…</code>
              </div>
              <ArrowRight size={16} />
            </button>
          </div>
        ))}
      </div>
      {run && (
        <div className="provenance-run">
          <Badge tone={run.status}>{run.status}</Badge>
          <strong>
            {run.analyzer} v{run.version}
          </strong>
          <p className="caption">
            Run {run.id} · {run.started_at}
          </p>
          <details>
            <summary>Recorded parameters & location</summary>
            <pre>
              {JSON.stringify(
                { parameters: run.parameters, location: artifact.location },
                null,
                2,
              )}
            </pre>
          </details>
        </div>
      )}
      <h3>{children.length} direct descendants</h3>
      <div className="provenance-children">
        {children.map((a) => (
          <button
            className="provenance-child"
            key={a.id}
            onClick={() => onJump(a.id)}
          >
            <FileIcon kind={a.kind} />
            <span>
              {a.name}
              <small>{a.role}</small>
            </span>
            <ArrowRight size={14} />
          </button>
        ))}
      </div>
      {!children.length && (
        <p className="muted">This artifact has no recorded descendants.</p>
      )}
    </div>
  );
}

function FindingCard({
  finding: f,
  expanded,
  selected,
  onToggle,
  onSelect,
  onJump,
  snapshot,
  onReview,
}: {
  finding: Finding;
  expanded: boolean;
  selected: boolean;
  onToggle: () => void;
  onSelect: () => void;
  onJump: (id: string) => void;
  snapshot: Snapshot;
  onReview: (review: Finding["review"]) => Promise<void>;
}) {
  const [note, setNote] = useState(f.review.note),
    [status, setStatus] = useState(f.review.status);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (expanded)
      ref.current?.scrollIntoView({
        block: "nearest",
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
  }, [expanded]);
  return (
    <article ref={ref} className={`finding-card ${expanded ? "expanded" : ""}`}>
      <div className="finding-kicker">
        <Badge tone={f.category}>
          {f.category === "heuristic" ? "indicator" : f.category}
        </Badge>
        <span>{f.analyzer}</span>
        <label className="select-finding" title="Include in assistant context">
          <input
            aria-label={`Select finding: ${f.title}`}
            type="checkbox"
            checked={selected}
            onChange={onSelect}
          />
        </label>
      </div>
      <button
        className="finding-title"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <h3>{f.title}</h3>
        {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
      </button>
      <p>{f.interpretation}</p>
      <div className="finding-source">
        <FileIcon
          kind={
            snapshot.artifacts.find((a) => a.id === f.artifact_id)?.kind || ""
          }
          size={12}
        />
        <span>
          {snapshot.artifacts.find((a) => a.id === f.artifact_id)?.name}
        </span>
        {f.review.status !== "unreviewed" && (
          <Badge>{f.review.status.replace("_", " ")}</Badge>
        )}
      </div>
      {expanded && (
        <div className="finding-detail">
          <div className="detail-label">SUPPORTING EVIDENCE</div>
          {f.supporting.map((id) => (
            <button
              className="citation-link"
              key={id}
              onClick={() => onJump(id)}
            >
              <FileIcon
                kind={snapshot.artifacts.find((a) => a.id === id)?.kind || ""}
                size={13}
              />
              <span>
                {snapshot.artifacts.find((a) => a.id === id)?.name || id}
              </span>
              <ArrowRight size={13} />
            </button>
          ))}
          <div className="detail-label">LOCATION</div>
          <pre>{JSON.stringify(f.location, null, 2)}</pre>
          {f.contradictory && (
            <>
              <div className="detail-label">ALTERNATIVE EXPLANATION</div>
              <p>{f.contradictory}</p>
            </>
          )}
          <div className="detail-label">LIMITATIONS</div>
          <p>{f.limitations}</p>
          <label className="field">
            Analyst review
            <select
              value={status}
              onChange={(e) =>
                setStatus(e.target.value as Finding["review"]["status"])
              }
            >
              <option value="unreviewed">Unreviewed</option>
              <option value="reviewed">Reviewed</option>
              <option value="inconclusive">Inconclusive</option>
              <option value="false_positive">False positive</option>
            </select>
          </label>
          <label className="field">
            Review note
            <textarea
              rows={3}
              maxLength={4000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Record your reasoning…"
            />
          </label>
          <button
            className="button small full-width"
            onClick={() => void onReview({ status, note })}
          >
            <Check size={14} />
            Save review
          </button>
          <code className="finding-id">{f.id}</code>
        </div>
      )}
    </article>
  );
}

function Notes({
  snapshot,
  refresh,
  run,
  onNotice,
}: Pick<Props, "snapshot" | "refresh" | "run" | "onNotice">) {
  const [notes, setNotes] = useState(snapshot.case.notes);
  return (
    <div className="notes-pane">
      <div className="eyebrow">ANALYST NOTEBOOK</div>
      <h3>Keep your reasoning with the case.</h3>
      <p className="muted">
        Separate measured facts from your conclusions. Notes persist locally and
        are included in reports.
      </p>
      <label className="field">
        Case notes
        <textarea
          rows={18}
          maxLength={20000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Observations, alternative explanations, next steps…"
        />
      </label>
      <button
        className="button primary full-width"
        onClick={() =>
          void run(async () => {
            await api(`/cases/${snapshot.case.id}`, {
              method: "PATCH",
              body: JSON.stringify({
                notes,
              }),
            });
            await refresh();
            onNotice("Case notes saved.");
          })
        }
      >
        <Check size={15} />
        Save notes
      </button>
      <p className="caption">
        {notes.length.toLocaleString()} / 20,000 characters ·{" "}
        {notes === snapshot.case.notes ? "Saved" : "Unsaved changes"}
      </p>
    </div>
  );
}
