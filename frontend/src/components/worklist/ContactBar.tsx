"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, PhoneOutgoing, X } from "lucide-react";

/**
 * Records that the team acted on the selected customers.
 *
 * This is the only write in the product, and it is deliberately small: it
 * says who was contacted, not what was said. That single fact is what the
 * next scan reads to stop re-flagging them, and what the uplift measurement
 * joins against later.
 */
export function ContactBar({
  selected,
  onClear,
  names,
}: {
  selected: number[];
  onClear: () => void;
  names: Record<number, string>;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<number | null>(null);

  if (selected.length === 0 && done === null) return null;

  async function record() {
    setSaving(true);
    setError(null);
    try {
      const response = await fetch("/api/contacted", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ user_ids: selected }),
      });
      const body = await response.json();
      if (!response.ok) {
        setError(body.error ?? "Could not record the outreach");
        return;
      }
      setDone(body.marked ?? selected.length);
      onClear();
      // The worklist drops anyone contacted in the last 30 days, so it has to
      // be refetched rather than patched in the browser.
      startTransition(() => router.refresh());
    } catch {
      setError("Could not reach the service");
    } finally {
      setSaving(false);
    }
  }

  if (done !== null) {
    return (
      <div
        className="mb-3 flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border border-[var(--low-border)] bg-[var(--low-soft)] px-5 py-3.5"
        role="status"
      >
        <CheckCircle2 className="h-4 w-4 text-[var(--low)]" aria-hidden />
        <p className="text-[12.5px] font-semibold text-[var(--low)]">
          {done} customer{done === 1 ? "" : "s"} recorded as contacted
        </p>
        <p className="text-[11.5px] text-[var(--text-muted)]">
          They will be skipped by scans for 30 days, and their outcome joins the uplift
          measurement once the 14-day window closes.
          {pending ? " Refreshing the worklist…" : ""}
        </p>
        <button
          type="button"
          onClick={() => setDone(null)}
          className="ml-auto rounded-lg p-1 text-[var(--text-subtle)] hover:bg-[var(--surface-2)]"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    );
  }

  const preview = selected
    .slice(0, 3)
    .map((id) => names[id])
    .filter(Boolean)
    .join(", ");

  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[var(--radius-card)] border border-[var(--border-accent)] bg-[var(--accent-soft)] px-5 py-3.5">
      <p className="text-[12.5px] font-bold text-[var(--accent)]">
        {selected.length} selected
      </p>
      <p className="max-w-md truncate text-[11.5px] text-[var(--text-muted)]">
        {preview}
        {selected.length > 3 ? ` and ${selected.length - 3} more` : ""}
      </p>

      {error ? (
        <p className="text-[11.5px] font-semibold text-[var(--high)]" role="alert">
          {error}
        </p>
      ) : null}

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onClear}
          className="rounded-[var(--radius-control)] border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-[12px] font-semibold text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
        >
          Clear
        </button>
        <button
          type="button"
          onClick={record}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-[var(--radius-control)] px-4 py-2 text-[12.5px] font-bold text-white shadow-[var(--shadow-accent)] transition-all duration-200 hover:-translate-y-0.5 active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
          style={{ background: "var(--accent-grad)" }}
        >
          {saving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <PhoneOutgoing className="h-3.5 w-3.5" aria-hidden />
          )}
          {saving ? "Recording…" : "Mark as contacted"}
        </button>
      </div>
    </div>
  );
}
