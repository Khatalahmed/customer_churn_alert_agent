import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-card)] border border-dashed border-[var(--border-strong)] px-6 py-20 text-center">
      <p className="text-[14px] font-medium">Nothing to show here</p>
      <p className="mt-1.5 max-w-sm text-[12.5px] leading-relaxed text-[var(--text-subtle)]">
        This customer was not active at the current analysis time, so the model did not score them
        — there is no risk, evidence or recommendation to display.
      </p>
      <Link
        href="/worklist"
        className="mt-5 rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[12.5px] font-medium transition-colors hover:border-[var(--border-strong)]"
      >
        Back to the worklist
      </Link>
    </div>
  );
}
