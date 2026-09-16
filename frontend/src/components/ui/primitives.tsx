/**
 * The design system, in the Hostel OS idiom: white cards with generous
 * radii and soft shadows, gradient brand furniture, very heavy display
 * numerals, and small uppercase eyebrow labels above everything.
 *
 * Risk colours stay semantic. The brand gradient is decoration and appears
 * only on brand furniture — never on a number whose colour means something.
 */
import type { CSSProperties, ReactNode } from "react";

import { cn, riskStyles } from "@/lib/format";
import type { RiskLevel } from "@/types/api";

export function Card({
  children,
  className,
  padded = true,
  accent = false,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  /** Draws the brand gradient hairline across the top edge. */
  accent?: boolean;
}) {
  return (
    <section
      className={cn(
        "lift relative overflow-hidden rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-sm)]",
        padded && "p-6",
        className,
      )}
    >
      {accent ? (
        <span
          className="pointer-events-none absolute inset-x-0 top-0 h-[3px]"
          style={{ background: "var(--accent-grad)" }}
          aria-hidden
        />
      ) : null}
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
        <h2 className="text-[14px] font-extrabold tracking-tight text-[var(--text)]">{title}</h2>
        {description ? (
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-[var(--text-subtle)]">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </header>
  );
}

/** The small uppercase label the hostel puts above every heading. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="text-[10.5px] font-extrabold uppercase tracking-[0.2em] text-[var(--accent)]">
      {children}
    </p>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
        <h1 className="mt-1.5 text-[30px] font-black leading-[1.1] tracking-tight text-[var(--text)]">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-[var(--text-muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {children}
    </header>
  );
}

/** The solid-indigo call to action, with the hostel's press-down feel. */
export function PrimaryButton({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button
      {...props}
      className={cn(
        "inline-flex items-center gap-2 rounded-[var(--radius-control)] px-4 py-2.5 text-[13px] font-bold text-white shadow-[var(--shadow-accent)] transition-all duration-200 hover:-translate-y-0.5 active:scale-95",
        className,
      )}
      style={{ background: "var(--accent-grad)", ...props.style }}
    >
      {children}
    </button>
  );
}

export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  const style = riskStyles[level];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10.5px] font-extrabold uppercase tracking-wider",
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
    neutral: "bg-[var(--surface-2)] text-[var(--text-muted)] border-[var(--border-strong)]",
    accent: "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--border-accent)]",
    good: "bg-[var(--low-soft)] text-[var(--low)] border-[var(--low-border)]",
    bad: "bg-[var(--high-soft)] text-[var(--high)] border-[var(--high-border)]",
    warn: "bg-[var(--medium-soft)] text-[var(--medium)] border-[var(--medium-border)]",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-bold",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * A headline number. The hostel's metric cards pair a gradient icon tile with
 * a very heavy numeral; the tile carries the brand, the numeral carries the
 * meaning, and only the numeral takes a risk colour.
 */
export function Metric({
  label,
  value,
  hint,
  tone,
  icon,
  style,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: RiskLevel;
  icon?: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div
      className="lift rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[var(--shadow-sm)]"
      style={style}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="text-[10.5px] font-extrabold uppercase tracking-[0.18em] text-[var(--text-subtle)]">
          {label}
        </div>
        {icon ? (
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[14px] text-white shadow-[var(--shadow-accent)]"
            style={{ background: "var(--accent-grad)" }}
            aria-hidden
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div
        className={cn(
          "tnum mt-3 text-[32px] font-black leading-none tracking-tight",
          tone ? riskStyles[tone].text : "text-[var(--text)]",
        )}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-2.5 text-[11.5px] leading-snug text-[var(--text-subtle)]">{hint}</div>
      ) : null}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div>
      <div className="text-[10.5px] font-extrabold uppercase tracking-[0.18em] text-[var(--text-subtle)]">
        {label}
      </div>
      <div className="tnum mt-1.5 text-[18px] font-black tracking-tight text-[var(--text)]">
        {value}
      </div>
      {hint ? <div className="mt-0.5 text-[11px] text-[var(--text-subtle)]">{hint}</div> : null}
    </div>
  );
}

/** A meter with the hostel's inner-shadow track and long easing. */
export function Meter({
  value,
  gradient,
  className,
}: {
  value: number;
  gradient: string;
  className?: string;
}) {
  return (
    <div className={cn("meter h-2", className)}>
      <span style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: gradient }} />
    </div>
  );
}

export function Empty({
  title,
  body,
  icon,
  action,
}: {
  title: string;
  body?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-card)] border border-dashed border-[var(--border-strong)] bg-[var(--surface)] px-6 py-16 text-center">
      {icon ? (
        <span
          className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--border-accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
          aria-hidden
        >
          {icon}
        </span>
      ) : null}
      <p className="text-[14px] font-extrabold tracking-tight">{title}</p>
      {body ? (
        <p className="mt-1.5 max-w-sm text-[12.5px] leading-relaxed text-[var(--text-subtle)]">
          {body}
        </p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/**
 * What a screen shows when the pipeline has not produced something yet.
 *
 * The backend answers "not produced, run this", and the UI repeats it rather
 * than rendering a zero that would read as a measurement.
 */
export function NotMeasured({ reason, how }: { reason: string; how?: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-dashed border-[var(--border-strong)] bg-[var(--surface)] p-7">
      <p className="text-[14px] font-extrabold tracking-tight">Not measured yet</p>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-[var(--text-subtle)]">{reason}</p>
      {how ? (
        <code className="mt-4 block w-fit rounded-[var(--radius-control)] border border-[var(--border-accent)] bg-[var(--accent-soft)] px-3 py-2 font-mono text-[11.5px] text-[var(--accent)]">
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
    <div className="rounded-[var(--radius-card)] border border-[var(--high-border)] bg-[var(--high-soft)] p-6">
      <p className="text-[13.5px] font-extrabold text-[var(--high)]">This panel could not load</p>
      <p className="mt-2 font-mono text-[11.5px] leading-relaxed text-[var(--text-muted)]">
        {message}
      </p>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-2xl", className)} />;
}

export function Divider({ className }: { className?: string }) {
  return <hr className={cn("border-t border-[var(--border)]", className)} />;
}

/** A definition-list row — used wherever the UI states an assumption. */
export function Field({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-[var(--border)] py-2.5 last:border-0">
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
      <dd className="tnum text-[12.5px] font-bold">{value}</dd>
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
        "sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-3 text-[10.5px] font-extrabold uppercase tracking-[0.14em] text-[var(--text-subtle)]",
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
        "border-b border-[var(--border)] px-4 py-3 align-middle",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className,
      )}
    >
      {children}
    </td>
  );
}
