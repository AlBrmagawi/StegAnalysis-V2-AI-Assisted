import { useState } from "react";
import {
  ArrowRight,
  FilePenLine,
  LockKeyhole,
  MessageSquare,
  Send,
  Sparkles,
} from "lucide-react";
import type { Health, Message, Provider, Snapshot } from "./types";
import { api, errorText } from "./api";
import { Badge, Empty, Modal } from "./ui";

type Props = {
  snapshot: Snapshot;
  health: Health | null;
  findingIds: string[];
  onCite: (id: string) => void;
  refresh: () => Promise<void>;
  run: (action: () => Promise<void>) => Promise<void>;
  onReport: () => void;
  onNotice: (text: string) => void;
};

export default function Assistant({
  snapshot,
  health,
  findingIds,
  onCite,
  refresh,
  run,
  onReport,
  onNotice,
}: Props) {
  const [provider, setProvider] = useState<Provider>("deterministic"),
    [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [consent, setConsent] = useState<{
    digest: string;
    payload: unknown;
    bytes: number;
    destination: unknown;
    request: { question: string; finding_ids: string[]; provider: Provider };
  } | null>(null);
  const ask = async (approved?: typeof consent) => {
    setBusy(true);
    setError("");
    const body = approved?.request || {
      question,
      finding_ids: findingIds,
      provider,
    };
    try {
      if (provider === "hosted" && !approved) {
        const preview = await api<{
          digest: string;
          payload: unknown;
          bytes: number;
          destination: unknown;
        }>(`/cases/${snapshot.case.id}/assistant/preview`, {
          method: "POST",
          body: JSON.stringify(body),
        });
        setConsent({ ...preview, request: body });
        return;
      }
      await api(`/cases/${snapshot.case.id}/assistant`, {
        method: "POST",
        body: JSON.stringify({ ...body, consent_digest: approved?.digest }),
      });
      setConsent(null);
      setQuestion("");
      await refresh();
    } catch (e) {
      setError(errorText(e));
      setConsent(null);
    } finally {
      setBusy(false);
    }
  };
  const draft = async (message: Message) => {
    const text = [
      `Investigation narrative — ${message.provider === "deterministic" ? "deterministic evidence guide" : "model-authored draft"}. Analyst review required.`,
      ...(["facts", "hypotheses", "actions"] as const).flatMap((section) => [
        section.toUpperCase(),
        ...message.content[section].map(
          (c) => `${c.text} [${c.citations.join(", ")}]`,
        ),
      ]),
    ].join("\n\n");
    await api(`/cases/${snapshot.case.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        report_draft: text,
        report_author:
          message.provider === "deterministic" ? "deterministic" : "model",
      }),
    });
    await refresh();
    onNotice("Draft added to the report editor for analyst review.");
    onReport();
  };
  return (
    <div className="assistant-pane">
      <div className="assistant-config">
        <div className="assistant-label">
          <MessageSquare size={17} />
          <strong>Evidence guide</strong>
          <Badge>
            {provider === "deterministic" ? "NO MODEL" : provider.toUpperCase()}
          </Badge>
        </div>
        <label className="field">
          Provider
          <select
            aria-label="Assistant provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
          >
            {(["deterministic", "local", "hosted"] as const).map((p) => (
              <option
                key={p}
                value={p}
                disabled={
                  p !== "deterministic" && !health?.providers[p].available
                }
              >
                {p === "deterministic"
                  ? "Deterministic · no language model"
                  : p === "local"
                    ? "Local model"
                    : "Hosted model"}
                {p !== "deterministic" && !health?.providers[p].available
                  ? " · unavailable"
                  : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="assistant-scope">
          <LockKeyhole size={13} />
          <span>
            {findingIds.length} selected finding
            {findingIds.length === 1 ? "" : "s"} · current case only
          </span>
        </div>
        <p className="caption">
          {provider === "deterministic"
            ? "A rule-based guide renders measured findings and their limitations. It is not a live AI model."
            : "Answers must cite selected findings. Validate the interpretation before including it in your conclusions."}
        </p>
      </div>
      <div
        className="conversation"
        role="region"
        aria-label="Assistant conversation"
        aria-live="polite"
        tabIndex={0}
      >
        {!snapshot.messages.length && (
          <Empty
            icon={<Sparkles size={25} />}
            title="Ask the evidence a question"
          >
            <p>
              Select findings, then explore what supports them—and what else
              could explain them.
            </p>
          </Empty>
        )}
        {snapshot.messages.map((message) => (
          <article className="message" key={message.id}>
            <div className="question-bubble">{message.question}</div>
            <div className="message-source">
              {message.provider === "deterministic"
                ? "DETERMINISTIC GUIDE"
                : `${message.provider.toUpperCase()} MODEL`}
            </div>
            {(["facts", "hypotheses", "actions"] as const).map(
              (section) =>
                message.content[section].length > 0 && (
                  <div className="answer-section" key={section}>
                    <h4>
                      {section === "facts"
                        ? "Measured evidence"
                        : section === "hypotheses"
                          ? "Interpretation & alternatives"
                          : "Recommended next steps"}
                    </h4>
                    {message.content[section].map((claim, i) => (
                      <div key={i}>
                        <p>{claim.text}</p>
                        <div className="citations">
                          {claim.citations.map((id, j) => (
                            <button
                              key={id}
                              onClick={() => onCite(id)}
                              title={
                                snapshot.findings.find((f) => f.id === id)
                                  ?.title
                              }
                            >
                              [{j + 1}]{" "}
                              {snapshot.findings
                                .find((f) => f.id === id)
                                ?.title.slice(0, 34) || id}
                              <ArrowRight size={11} />
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ),
            )}
            <p className="caption">{message.content.notice}</p>
            <button
              className="button small"
              onClick={() => void run(() => draft(message))}
            >
              <FilePenLine size={13} />
              Use as report draft
            </button>
          </article>
        ))}
      </div>
      <div className="assistant-compose">
        <div className="prompt-suggestions">
          {[
            "Why was this flagged?",
            "Could this be normal compression?",
            "Which check should I run next?",
            "Compare the selected evidence.",
          ].map((q) => (
            <button key={q} onClick={() => setQuestion(q)}>
              {q}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void ask();
          }}
        >
          <label className="field">
            <span className="visually-hidden">Ask about selected evidence</span>
            <textarea
              aria-label="Ask about selected evidence"
              rows={3}
              maxLength={2000}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What supports this finding?"
            />
          </label>
          {error && (
            <p className="inline-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="button primary full-width"
            disabled={!question.trim() || busy}
            type="submit"
          >
            <Send size={14} />
            {busy
              ? "Checking evidence…"
              : provider === "hosted"
                ? "Preview hosted request"
                : "Ask evidence guide"}
          </button>
        </form>
      </div>
      {consent && (
        <Modal
          title="Review hosted transmission"
          onClose={() => setConsent(null)}
        >
          <p className="muted">
            Only the following selected findings and your question will leave
            this machine. Original files and raw extracted text are excluded.
          </p>
          <p className="caption">
            {consent.bytes.toLocaleString()} bytes · Destination:{" "}
            {JSON.stringify(consent.destination)}
          </p>
          <pre className="consent-payload">
            {JSON.stringify(consent.payload, null, 2)}
          </pre>
          <div className="modal-actions">
            <button className="button" onClick={() => setConsent(null)}>
              Keep local
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => void ask(consent)}
            >
              <Send size={14} />
              Approve & send this payload
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
