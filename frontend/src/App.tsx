import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  FileCheck2,
  FlaskConical,
  Folder,
  FolderPlus,
  Layers,
  LoaderCircle,
  LockKeyhole,
  Moon,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sun,
  UploadCloud,
  X,
} from "lucide-react";
import type { Case, Health, Job, Progress, Snapshot } from "./types";
import { api, bytes, date, errorText } from "./api";
import { Badge, Breadcrumb, Empty, Modal } from "./ui";
import Workspace from "./Workspace";
import Reports from "./Reports";

type View = "cases" | "investigate" | "reports" | "settings";

export default function App() {
  const [view, setView] = useState<View>("cases");
  const [cases, setCases] = useState<Case[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const [events, setEvents] = useState<Progress[]>([]);
  const [theme, setTheme] = useState(
    localStorage.getItem("steg-theme") || "dark",
  );
  const currentId = useRef<string | null>(null);
  const activeJob = snapshot?.jobs.find((j) =>
    ["queued", "running"].includes(j.status),
  );
  const refreshCases = useCallback(
    async () => setCases(await api<Case[]>("/cases")),
    [],
  );
  const refresh = useCallback(async () => {
    const id = currentId.current;
    if (!id) return;
    const next = await api<Snapshot>(`/cases/${id}`);
    if (currentId.current === id) setSnapshot(next);
  }, []);
  const run = useCallback(async (action: () => Promise<void>) => {
    setError("");
    try {
      await action();
    } catch (e) {
      setError(errorText(e));
    }
  }, []);
  useEffect(() => {
    void run(async () => {
      try {
        await Promise.all([
          refreshCases(),
          api<Health>("/health").then(setHealth),
        ]);
      } finally {
        setLoading(false);
      }
    });
  }, [refreshCases, run]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("steg-theme", theme);
  }, [theme]);
  useEffect(() => {
    if (!activeJob || !caseId) return;
    setEvents([]);
    const stream = new EventSource(
      `/api/cases/${caseId}/jobs/${activeJob.id}/events`,
    );
    stream.addEventListener("progress", (event) =>
      setEvents((previous) => [
        ...previous.slice(-199),
        JSON.parse((event as MessageEvent).data) as Progress,
      ]),
    );
    stream.addEventListener("done", () => {
      stream.close();
      void run(async () => {
        await refresh();
        await refreshCases();
      });
    });
    const timer = window.setInterval(() => void run(refresh), 2000);
    return () => {
      stream.close();
      clearInterval(timer);
    };
  }, [activeJob?.id, caseId, refresh, refreshCases, run]); // eslint-disable-line react-hooks/exhaustive-deps
  const openCase = async (id: string) => {
    currentId.current = id;
    setCaseId(id);
    setSnapshot(null);
    setView("investigate");
    setEvents([]);
    await refresh();
  };
  const showCases = () => {
    setView("cases");
    void run(refreshCases);
  };
  const filtered = cases
    .filter((c) =>
      `${c.name} ${c.description}`.toLowerCase().includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name)
        : b.created_at.localeCompare(a.created_at),
    );
  const jobAction = async (job: Job, cancel: boolean) => {
    await api(`/cases/${caseId}/jobs${cancel ? `/${job.id}/cancel` : ""}`, {
      method: "POST",
      body: JSON.stringify(
        cancel
          ? {}
          : {
              artifact_ids: job.artifact_ids,
              profile: job.profile,
              budget: job.budget,
            },
      ),
    });
    await refresh();
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <nav className="rail" aria-label="Main navigation">
        <button
          className="brand-mark"
          aria-label="StegAnalysis home"
          onClick={showCases}
        >
          <Layers size={24} />
        </button>
        <div className="rail-links">
          <button
            className={`rail-item ${view === "cases" ? "active" : ""}`}
            onClick={showCases}
            aria-label="Cases"
            title="Cases"
          >
            <Folder size={21} />
            <span>Cases</span>
          </button>
          <button
            className={`rail-item ${view === "investigate" ? "active" : ""}`}
            disabled={!caseId}
            onClick={() => setView("investigate")}
            aria-label="Investigate"
            title="Investigation workspace"
          >
            <Activity size={21} />
            <span>Inspect</span>
          </button>
          <button
            className={`rail-item ${view === "reports" ? "active" : ""}`}
            disabled={!caseId}
            onClick={() => setView("reports")}
            aria-label="Reports"
            title="Reporting"
          >
            <FileCheck2 size={21} />
            <span>Report</span>
          </button>
        </div>
        <div className="rail-bottom">
          <button
            className={`rail-item ${view === "settings" ? "active" : ""}`}
            onClick={() => setView("settings")}
            aria-label="Settings and tool health"
            title="Settings & tool health"
          >
            <Settings2 size={21} />
          </button>
          <button
            className="rail-item"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title="Toggle theme"
          >
            {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <span className="local-avatar" title="Local analyst">
            LA
          </span>
        </div>
      </nav>
      <div className="app-body">
        <header className="topbar">
          <div className="wordmark">
            Steg<span>Analysis</span>
            <span className="edition">WORKBENCH</span>
          </div>
          <div className="topbar-right">
            <span className="local-indicator">
              <span className="status-dot" />
              Local workspace
            </span>
            <span className="version">v{health?.version || "2.0.0"}</span>
          </div>
        </header>
        <div className="contextbar">
          <Breadcrumb onCases={showCases}>
            {view !== "cases"
              ? view === "settings"
                ? "Settings & capabilities"
                : snapshot?.case.name || "Loading case…"
              : undefined}
          </Breadcrumb>
          <div className="context-actions">
            {snapshot && view !== "cases" && view !== "settings" && (
              <>
                <button
                  className="button small"
                  onClick={() => setUploadOpen(true)}
                >
                  <Plus size={14} />
                  Add evidence
                </button>
                <button
                  className="button primary small"
                  onClick={() => setConfigOpen(true)}
                  disabled={
                    !snapshot.artifacts.some((a) => a.role === "original") ||
                    !!activeJob
                  }
                >
                  <Activity size={14} />
                  Run analysis
                </button>
              </>
            )}
          </div>
        </div>
        {error && (
          <div className="banner error" role="alert">
            <CircleHelp size={17} />
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        {notice && (
          <div className="banner success" role="status">
            <Check size={16} />
            <span>{notice}</span>
            <button
              aria-label="Dismiss notification"
              onClick={() => setNotice("")}
            >
              <X size={16} />
            </button>
          </div>
        )}
        <main
          id="main"
          className={`main-view ${view === "investigate" ? "investigation-main" : ""}`}
        >
          {view === "cases" && (
            <div className="page cases-page">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    EVIDENCE FIRST. CONCLUSIONS SECOND.
                  </div>
                  <h1>Your investigations</h1>
                  <p className="muted">
                    Follow the signal. Keep the evidence in view.
                  </p>
                </div>
                <button
                  className="button primary"
                  onClick={() => setCreateOpen(true)}
                >
                  <Plus size={17} />
                  New case
                </button>
              </div>
              <div className="workspace-intro">
                <div className="intro-symbol">
                  <ShieldCheck size={28} />
                </div>
                <div>
                  <h3>A clear chain from source to finding.</h3>
                  <p>
                    Inspect PDFs, images, audio and text in one local workspace.
                    Every transformation stays connected to its source.
                  </p>
                </div>
                <span className="intro-label">
                  <LockKeyhole size={14} />
                  LOCAL BY DEFAULT
                </span>
              </div>
              <div className="section-toolbar">
                <div className="section-title">
                  CASE LIBRARY{" "}
                  <span>{cases.length.toString().padStart(2, "0")}</span>
                </div>
                <div className="toolbar">
                  <label className="search-field">
                    <Search size={16} />
                    <input
                      aria-label="Search cases"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search investigations…"
                    />
                  </label>
                  <select
                    aria-label="Sort cases"
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                  >
                    <option value="newest">Newest first</option>
                    <option value="name">Name A–Z</option>
                  </select>
                </div>
              </div>
              {loading ? (
                <Empty
                  icon={<LoaderCircle className="spin" />}
                  title="Opening local workspace…"
                />
              ) : !filtered.length ? (
                <Empty
                  icon={<FolderPlus size={34} />}
                  title={
                    cases.length ? "No matching cases" : "Start with a question"
                  }
                >
                  <p>
                    {cases.length
                      ? "Try a different case name or description."
                      : "Create a case, add evidence, and follow the artifacts to a defensible conclusion."}
                  </p>
                  {!cases.length && (
                    <button
                      className="button primary"
                      onClick={() => setCreateOpen(true)}
                    >
                      Create your first case
                      <ArrowRight size={15} />
                    </button>
                  )}
                </Empty>
              ) : (
                <div className="case-table">
                  <div className="case-table-head">
                    <span>INVESTIGATION</span>
                    <span>EVIDENCE</span>
                    <span>FINDINGS</span>
                    <span>CREATED</span>
                    <span />
                  </div>
                  {filtered.map((c, index) => (
                    <button
                      className="case-row"
                      key={c.id}
                      onClick={() => void run(() => openCase(c.id))}
                    >
                      <div className="case-title-cell">
                        <span className="case-folder">
                          <Folder size={22} />
                        </span>
                        <div>
                          <div className="case-index">
                            CASE {String(cases.length - index).padStart(3, "0")}
                            {c.name.startsWith("DEMO") && (
                              <span className="demo-label">DEMONSTRATION</span>
                            )}
                          </div>
                          <h3>{c.name}</h3>
                          <p>{c.description || "No description added."}</p>
                        </div>
                      </div>
                      <span className="case-metric">
                        {c.evidence_count}
                        <small>files</small>
                      </span>
                      <span className="case-metric">
                        {c.finding_count}
                        <small>observations</small>
                      </span>
                      <span className="muted case-date">
                        {date(c.created_at)}
                      </span>
                      <ChevronRight size={18} />
                    </button>
                  ))}
                </div>
              )}
              <div className="case-footer">
                <span>
                  <ShieldCheck size={14} />
                  Original evidence is retained. Findings remain open to review.
                </span>
                <button
                  className="text-button"
                  onClick={() => setView("settings")}
                >
                  View analyzer capabilities
                  <ArrowRight size={14} />
                </button>
              </div>
              <div className="credits">
                StegAnalysis · Created by Mohamed Abdelgalil (AlBrmagawi) &
                Spooky
              </div>
            </div>
          )}
          {view === "investigate" &&
            (!snapshot ? (
              <Empty
                icon={<LoaderCircle className="spin" />}
                title="Loading evidence…"
              />
            ) : (
              <>
                {activeJob && (
                  <div className="job-strip" role="status">
                    <LoaderCircle size={17} className="spin" />
                    <div>
                      <strong>
                        {events.at(-1)?.stage ||
                          (activeJob.status === "queued"
                            ? "Waiting for worker"
                            : "Analyzing evidence")}
                      </strong>
                      <span>
                        {activeJob.completed} of {activeJob.total || "pending"}{" "}
                        discovered tasks complete · {activeJob.profile} profile
                      </span>
                    </div>
                    <button
                      className="button small"
                      disabled={activeJob.cancel_requested}
                      onClick={() => void run(() => jobAction(activeJob, true))}
                    >
                      {activeJob.cancel_requested
                        ? "Cancelling…"
                        : "Cancel analysis"}
                    </button>
                  </div>
                )}
                {!activeJob &&
                  snapshot.jobs.at(-1) &&
                  ["failed", "cancelled", "timed_out"].includes(
                    snapshot.jobs.at(-1)!.status,
                  ) && (
                    <div className="banner warning">
                      <span>
                        Last run {snapshot.jobs.at(-1)!.status}.{" "}
                        {snapshot.jobs.at(-1)!.error} Partial evidence remains
                        available.
                      </span>
                      <button
                        className="button small"
                        onClick={() =>
                          void run(() =>
                            jobAction(snapshot.jobs.at(-1)!, false),
                          )
                        }
                      >
                        Retry analysis
                      </button>
                    </div>
                  )}
                <Workspace
                  key={snapshot.case.id}
                  snapshot={snapshot}
                  health={health}
                  refresh={refresh}
                  run={run}
                  onUpload={() => setUploadOpen(true)}
                  onAnalyze={() => setConfigOpen(true)}
                  onReport={() => setView("reports")}
                  onNotice={setNotice}
                />
              </>
            ))}
          {view === "reports" && snapshot && (
            <Reports
              key={snapshot.case.id}
              snapshot={snapshot}
              refresh={refresh}
              run={run}
              onNotice={setNotice}
            />
          )}
          {view === "settings" && (
            <div className="page settings-page">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">KNOW YOUR INSTRUMENTS</div>
                  <h1>Settings & capabilities</h1>
                  <p className="muted">
                    Measured tool availability, explicit limits, and local-first
                    defaults.
                  </p>
                </div>
                <button
                  className="button"
                  onClick={() =>
                    void run(async () =>
                      setHealth(await api<Health>("/health")),
                    )
                  }
                >
                  Refresh health
                </button>
              </div>
              <div className="settings-grid">
                <section className="surface">
                  <h2>
                    <ShieldCheck size={18} />
                    Native analysis
                  </h2>
                  {health?.analyzers
                    .filter((a) => !a.deep_only)
                    .map((a) => (
                      <div className="health-row" key={a.id}>
                        <div>
                          <strong>{a.name}</strong>
                          <small>{a.kinds.join(" / ")}</small>
                        </div>
                        <Badge tone="completed">Available</Badge>
                      </div>
                    ))}
                </section>
                <section className="surface">
                  <h2>
                    <Settings2 size={18} />
                    Optional tools
                  </h2>
                  {Object.entries(health?.doctor.tools || {}).map(
                    ([name, tool]) => (
                      <div className="health-row" key={name}>
                        <div>
                          <strong>{name}</strong>
                          <small>{tool.purpose}</small>
                        </div>
                        <Badge tone={tool.available ? "completed" : "skipped"}>
                          {tool.available ? "Available" : "Not installed"}
                        </Badge>
                      </div>
                    ),
                  )}
                  <p className="caption">
                    Install optional tools explicitly on a trusted PATH. Legacy
                    binaries are excluded. Foremost carving is unavailable;
                    Stegsolve views are implemented natively.
                  </p>
                </section>
                <section className="surface">
                  <h2>
                    <LockKeyhole size={18} />
                    Assistant & privacy
                  </h2>
                  {(["deterministic", "local", "hosted"] as const).map((p) => (
                    <div className="health-row" key={p}>
                      <div>
                        <strong>{health?.providers[p].label}</strong>
                        <small>
                          {health?.providers[p].model ||
                            (p === "deterministic"
                              ? "No model, account or API key required"
                              : "Configure server environment; see documentation")}
                        </small>
                      </div>
                      <Badge>
                        {health?.providers[p].available
                          ? "Configured"
                          : "Unavailable"}
                      </Badge>
                    </div>
                  ))}
                  <p className="caption">
                    Configuration is not a connectivity check. Hosted requests
                    require a preview and consent for each exact selected
                    payload. No original files are transmitted.
                  </p>
                </section>
                <section className="surface">
                  <h2>
                    <FlaskConical size={18} />
                    Experimental ML
                  </h2>
                  <Badge tone={health?.ml.available ? "completed" : "skipped"}>
                    {health?.ml.available
                      ? "Local model configured"
                      : "Model not available"}
                  </Badge>
                  <p className="muted">
                    A reproducible feature and logistic-regression pipeline is
                    included. Train and evaluate on source-separated data before
                    enabling inference.
                  </p>
                  <code className="command">steganalysis ml --help</code>
                  <p className="caption">
                    No universal detection claim. Synthetic data cannot
                    establish performance on natural images.
                  </p>
                </section>
              </div>
              <section className="surface runtime">
                <h2>Runtime & boundaries</h2>
                <div className="runtime-grid">
                  {Object.entries(health?.doctor.versions || {}).map(
                    ([name, version]) => (
                      <div key={name}>
                        <span className="muted">{name}</span>
                        <code>{version}</code>
                      </div>
                    ),
                  )}
                </div>
                <p className="caption">
                  32 MiB per upload · One worker · Eight pending jobs ·
                  Deadlines and memory limits · Single-user loopback service.
                  Native workers are not an operating-system security sandbox.
                  See the security documentation for isolation limits.
                </p>
              </section>
            </div>
          )}
        </main>
        <footer className="statusbar">
          <span>
            <span className="status-dot" />
            {activeJob ? "Analysis running" : "Workspace ready"}
          </span>
          <span>
            {snapshot && view !== "cases"
              ? `${snapshot.artifacts.length} artifacts · ${snapshot.findings.length} findings`
              : "SHA-256 evidence identity"}
            <span className="status-separator">/</span>Local storage
          </span>
        </footer>
      </div>
      {createOpen && (
        <CreateCase
          onClose={() => setCreateOpen(false)}
          onCreate={async (name, description) => {
            const c = await api<Case>("/cases", {
              method: "POST",
              body: JSON.stringify({ name, description }),
            });
            await refreshCases();
            await openCase(c.id);
            setCreateOpen(false);
            setUploadOpen(true);
          }}
        />
      )}
      {uploadOpen && caseId && (
        <Upload
          caseId={caseId}
          onClose={() => setUploadOpen(false)}
          onDone={async (count) => {
            await refresh();
            await refreshCases();
            setNotice(
              `${count} file${count === 1 ? "" : "s"} ingested and hashed.`,
            );
            setUploadOpen(false);
            setConfigOpen(true);
          }}
        />
      )}
      {configOpen && snapshot && (
        <Configure
          snapshot={snapshot}
          onClose={() => setConfigOpen(false)}
          onStart={async (ids, profile, window) => {
            await api(`/cases/${caseId}/jobs`, {
              method: "POST",
              body: JSON.stringify({
                artifact_ids: ids,
                profile,
                budget: { entropy_window: window, entropy_stride: window },
              }),
            });
            setConfigOpen(false);
            setView("investigate");
            await refresh();
          }}
        />
      )}
    </div>
  );
}

function CreateCase({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string, description: string) => Promise<void>;
}) {
  const [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <Modal title="New investigation" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await onCreate(name, description);
          } catch (e) {
            setError(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <p className="muted">
          Give the evidence a place to belong. You can add files next.
        </p>
        <label className="field">
          Case name
          <input
            data-autofocus
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Document integrity review"
          />
        </label>
        <label className="field">
          Description <span className="muted">optional</span>
          <textarea
            maxLength={4000}
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What are you investigating?"
          />
        </label>
        {error && (
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="button" onClick={onClose}>
            Cancel
          </button>
          <button className="button primary" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create case"}
            <ArrowRight size={15} />
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Upload({
  caseId,
  onClose,
  onDone,
}: {
  caseId: string;
  onClose: () => void;
  onDone: (n: number) => Promise<void>;
}) {
  const [files, setFiles] = useState<File[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const add = (incoming: File[]) => {
    if (incoming.some((f) => !f.size || f.size > 32 * 1024 * 1024)) {
      setError("Each file must contain data and be no larger than 32 MiB.");
      return;
    }
    if (incoming.length + files.length > 16) {
      setError("Add up to 16 files at a time.");
      return;
    }
    setError("");
    setFiles((previous) => [...previous, ...incoming]);
  };
  const upload = async () => {
    setBusy(true);
    setError("");
    let count = 0;
    try {
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        await api(`/cases/${caseId}/evidence`, { method: "POST", body: form });
        count++;
      }
      await onDone(count);
    } catch (e) {
      setFiles((previous) => previous.slice(count));
      setError(
        `${errorText(e)} ${count ? `${count} earlier files were saved; retry will only upload remaining files.` : ""}`,
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Add evidence"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <p className="muted">
        Original bytes stay intact. SHA-256 hashes are computed at ingestion.
      </p>
      <button
        disabled={busy}
        type="button"
        className={`dropzone ${drag ? "dragging" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          add(Array.from(e.dataTransfer.files));
        }}
      >
        <UploadCloud size={30} />
        <strong>Drop evidence here, or browse files</strong>
        <span>PDF · PNG, JPEG, BMP · WAV · UTF-8 text</span>
        <small>
          32 MiB per file · Other formats receive byte inspection only
        </small>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        className="visually-hidden"
        aria-label="Evidence files"
        onChange={(e) => {
          add(Array.from(e.target.files || []));
          e.target.value = "";
        }}
      />
      <div className="upload-list">
        {files.map((f, i) => (
          <div key={`${f.name}-${i}`}>
            <span>{f.name}</span>
            <small>{bytes(f.size)}</small>
            <button
              className="icon-button"
              aria-label={`Remove ${f.name}`}
              disabled={busy}
              onClick={() => setFiles(files.filter((_, index) => index !== i))}
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      <div className="modal-actions">
        <span className="caption">
          <LockKeyhole size={13} />
          Files stay on this machine
        </span>
        <button
          className="button primary"
          disabled={!files.length || busy}
          onClick={() => void upload()}
        >
          {busy
            ? "Ingesting evidence…"
            : `Add ${files.length || ""} file${files.length === 1 ? "" : "s"}`}
          <ArrowRight size={15} />
        </button>
      </div>
    </Modal>
  );
}

function Configure({
  snapshot,
  onClose,
  onStart,
}: {
  snapshot: Snapshot;
  onClose: () => void;
  onStart: (ids: string[], profile: string, window: number) => Promise<void>;
}) {
  const originals = snapshot.artifacts.filter((a) => a.role === "original");
  const [selected, setSelected] = useState(
      originals.slice(0, 16).map((a) => a.id),
    ),
    [profile, setProfile] = useState("standard"),
    [window, setWindow] = useState(4096),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Modal title="Configure analysis" onClose={onClose}>
      <p className="muted">
        Choose a scope. Every run preserves its settings and history.
      </p>
      <div className="profiles">
        {[
          [
            "quick",
            "Quick",
            "Identity, format metadata, bounded statistical checks.",
          ],
          [
            "standard",
            "Standard",
            "Native analysis, channels, selected bit planes and extraction.",
          ],
          [
            "deep",
            "Deep",
            "All eight image bit planes and optional external tool adapters.",
          ],
        ].map(([id, label, description]) => (
          <label
            className={`profile ${profile === id ? "selected" : ""}`}
            key={id}
          >
            <input
              type="radio"
              name="profile"
              value={id}
              checked={profile === id}
              onChange={() => setProfile(id)}
            />
            <div>
              <strong>
                {label}
                {id === "standard" && <small>RECOMMENDED</small>}
              </strong>
              <p>{description}</p>
            </div>
          </label>
        ))}
      </div>
      <fieldset className="evidence-checklist">
        <legend>Evidence to analyze · up to 16</legend>
        {originals.map((a) => (
          <label key={a.id}>
            <input
              type="checkbox"
              checked={selected.includes(a.id)}
              onChange={(e) =>
                setSelected(
                  e.target.checked
                    ? [...selected, a.id].slice(0, 16)
                    : selected.filter((id) => id !== a.id),
                )
              }
            />
            <span>{a.name}</span>
            <small>{bytes(a.size)}</small>
          </label>
        ))}
      </fieldset>
      <label className="field">
        Entropy window / stride
        <select
          value={window}
          onChange={(e) => setWindow(Number(e.target.value))}
        >
          <option value={1024}>1,024 bytes</option>
          <option value={4096}>4,096 bytes</option>
          <option value={16384}>16,384 bytes</option>
        </select>
      </label>
      <p className="caption">
        45 seconds per analyzer · 180 seconds per job · Recursive depth 2 ·
        Missing optional tools are explicitly skipped.
      </p>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      <div className="modal-actions">
        <button className="button" onClick={onClose}>
          Cancel
        </button>
        <button
          className="button primary"
          disabled={!selected.length || busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onStart(selected, profile, window);
            } catch (e) {
              setError(errorText(e));
              setBusy(false);
            }
          }}
        >
          <Activity size={15} />
          {busy ? "Queuing…" : "Start analysis"}
        </button>
      </div>
    </Modal>
  );
}
