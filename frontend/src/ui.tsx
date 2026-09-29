import { useEffect, useId, useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import {
  X,
  FileText,
  Image,
  AudioLines,
  File,
  ChevronRight,
} from "lucide-react";

export function FileIcon({ kind, size = 17 }: { kind: string; size?: number }) {
  const Icon =
    kind === "image"
      ? Image
      : kind === "audio"
        ? AudioLines
        : ["text", "pdf"].includes(kind)
          ? FileText
          : File;
  return <Icon size={size} aria-hidden="true" />;
}
export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Empty({
  icon,
  title,
  children,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-icon">{icon}</div>}
      <h3>{title}</h3>
      <div className="muted">{children}</div>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby={titleId}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], [tabindex]",
          ),
        ).filter(
          (element) =>
            element.tabIndex >= 0 && element.getClientRects().length > 0,
        );
        const first = controls[0],
          last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-heading">
        <h2 id={titleId}>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function navigateTabs(event: KeyboardEvent<HTMLElement>) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const tabs = Array.from(
    event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'),
  );
  const current = tabs.indexOf(event.target as HTMLButtonElement);
  if (current < 0) return;
  event.preventDefault();
  const next =
    event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
          tabs.length;
  tabs[next]?.focus();
  tabs[next]?.click();
}
export function Breadcrumb({
  children,
  onCases,
}: {
  children?: ReactNode;
  onCases: () => void;
}) {
  return (
    <div className="breadcrumbs">
      <button onClick={onCases}>Cases</button>
      {children && (
        <>
          <ChevronRight size={13} />
          <span>{children}</span>
        </>
      )}
    </div>
  );
}
export function Chart({
  values,
  max,
  label,
  color = "var(--accent)",
}: {
  values: number[];
  max?: number;
  label: string;
  color?: string;
}) {
  if (!values.length)
    return <p className="muted">No measurements available.</p>;
  const peak = max || Math.max(...values, 1);
  const path = values
    .map(
      (n, i) =>
        `${i ? "L" : "M"} ${(i * 600) / Math.max(1, values.length - 1)} ${110 - (n / peak) * 100}`,
    )
    .join(" ");
  return (
    <svg
      className="chart"
      viewBox="0 0 600 120"
      role="img"
      aria-label={label}
      preserveAspectRatio="none"
    >
      <path
        d="M0 10H600 M0 60H600 M0 110H600"
        stroke="var(--border)"
        fill="none"
      />
      <path d={`${path} L600 115 L0 115 Z`} fill={color} opacity=".10" />
      <path
        d={path}
        stroke={color}
        strokeWidth="1.5"
        fill="none"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
