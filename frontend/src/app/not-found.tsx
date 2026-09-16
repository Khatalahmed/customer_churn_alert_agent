import Link from "next/link";
import { Shield } from "lucide-react";

export default function NotFound() {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-[var(--radius-card)] px-6 py-24 text-center"
      style={{ border: "1px dashed var(--border-strong)", background: "var(--surface)" }}
    >
      {/* Icon */}
      <div
        className="mb-5 flex h-14 w-14 items-center justify-center rounded-full"
        style={{
          background: "rgba(99,102,241,0.08)",
          border: "1px solid var(--border-accent)",
          boxShadow: "0 0 24px rgba(99,102,241,0.15)",
        }}
      >
        <Shield className="h-7 w-7 text-[var(--accent)]" strokeWidth={1.5} aria-hidden />
      </div>

      <p className="text-[16px] font-semibold text-[var(--text)]">Nothing to show here</p>
      <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-[var(--text-subtle)]">
        This customer was not active at the current analysis time, so the model did not score them
        — there is no risk, evidence or recommendation to display.
      </p>
      <Link
        href="/worklist"
        className="mt-6 rounded-[var(--radius-control)] px-4 py-2 text-[13px] font-semibold text-white transition-all hover:opacity-90 hover:shadow-[0_0_16px_rgba(99,102,241,0.35)]"
        style={{ background: "var(--accent-grad)" }}
      >
        Back to the worklist
      </Link>
    </div>
  );
}
