/**
 * The design system: every surface, label and state in the product is one of
 * these. Built by hand rather than pulled from a component library because
 * the set is small, the tokens are already defined, and an eight-component
 * dependency would be larger than the thing it replaces.
 */
import type { ReactNode } from "react";

import { cn, riskStyles } from "@/lib/format";
import type { RiskLevel } from "@/types/api";

export function Card({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)]",
        padded && "p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-[13px] font-semibold tracking-tight">{title}</h2>
        {description ? (
          <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-subtle)]">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </header>
  );
}

export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[19px] font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-[var(--text-muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {children}
    </header>
  );
}

export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  const style = riskStyles[level];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[var(--radius-control)] border px-2 py-0.5 text-[11px] font-medium",
        style.chip,
        className,
      )}
    >
      {/* a shape as well as a colour: risk must survive a greyscale print */}
      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} aria-hidden />
      {level}
    </span>
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "good" | "bad" | "warn";
  className?: string;
}) {
  const tones = {
    neutral: "bg-[var(--surface-2)] text-[var(--text-muted)] border-[var(--border)]",
    accent: "bg-[var(--accent-soft)] text-[var(--accent)] border-transparent",
    good: "bg-[var(--low-soft)] text-[var(--low)] border-[var(--low-border)]",
    bad: "bg-[var(--high-soft)] text-[var(--high)] border-[var(--high-border)]",
    warn: "bg-[var(--medium-soft)] text-[var(--medium)] border-[var(--medium-border)]",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: RiskLevel;
}) {
  return (
    <div className="rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--text-subtle)]">
        {label}
      </div>
      <div
        className={cn(
          "tnum mt-2 text-[26px] font-semibold leading-none tracking-tight",
          tone && riskStyles[tone].text,
        )}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-2 text-[11.5px] leading-snug text-[var(--text-subtle)]">{hint}</div>
      ) : null}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">{label}</div>
      <div className="tnum mt-1 text-[15px] font-semibold">{value}</div>
      {hint ? <div className="mt-0.5 text-[11px] text-[var(--text-subtle)]">{hint}</div> : null}
    </div>
  );
}

export function Empty({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-card)] border border-dashed border-[var(--border-strong)] px-6 py-14 text-center">
      <p className="text-[13px] font-medium">{title}</p>
      {body ? (
        <p className="mt-1.5 max-w-sm text-[12px] leading-relaxed text-[var(--text-subtle)]">
          {body}
        </p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/**
 * What a screen shows when the pipeline has not produced something yet.
 *
 * This component is the spec's data-integrity rule made visible: the backend
 * answers "not produced, run this", and the UI repeats it rather than
 * rendering a zero that would read as a measurement.
 */
export function NotMeasured({ reason, how }: { reason: string; how?: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-dashed border-[var(--border-strong)] bg-[var(--surface)] p-6">
      <p className="text-[13px] font-medium">Not measured yet</p>
      <p className="mt-1 text-[12px] leading-relaxed text-[var(--text-subtle)]">{reason}</p>
      {how ? (
        <code className="mt-3 block w-fit rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1.5 font-mono text-[11.5px] text-[var(--text-muted)]">
          {how}
        </code>
      ) : null}
      <p className="mt-3 text-[11px] text-[var(--text-subtle)]">
        Nothing is shown here until that runs — a placeholder number would be indistinguishable
        from a result.
      </p>
    </div>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-[var(--high-border)] bg-[var(--high-soft)] p-5">
      <p className="text-[13px] font-medium text-[var(--high)]">This panel could not load</p>
      <p className="mt-1.5 font-mono text-[11.5px] leading-relaxed text-[var(--text-muted)]">
        {message}
      </p>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} />;
}

export function Divider({ className }: { className?: string }) {
  return <hr className={cn("border-t border-[var(--border)]", className)} />;
}

/** A definition list row — used wherever the UI states an assumption. */
export function Field({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-6 py-2">
      <dt className="text-[12px] text-[var(--text-muted)]">
        {label}
        {/* the space is inside the markup, so the label still reads correctly
            when it is flattened — by a screen reader, or by copy-and-paste */}
        {note ? (
          <>
            {" "}
            <span className="text-[11px] text-[var(--text-subtle)]">({note})</span>
          </>
        ) : null}
      </dt>
      <dd className="tnum text-[12.5px] font-medium">{value}</dd>
    </div>
  );
}

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full border-collapse text-[12.5px]", className)}>{children}</table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
  className,
}: {
  /** Optional: a column of row actions has a header cell with no label. */
  children?: ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={cn(
        "sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--surface)] px-3 py-2.5 text-[11px] font-medium uppercase tracking-wide text-[var(--text-subtle)]",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align = "left",
  className,
}: {
  children: ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}) {
  return (
    <td
      className={cn(
        "border-b border-[var(--border)] px-3 py-2.5 align-middle",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className,
      )}
    >
      {children}
    </td>
  );
}
