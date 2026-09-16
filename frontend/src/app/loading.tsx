import { Skeleton } from "@/components/ui/primitives";

/**
 * Shown while a server component fetches. The shape matches what arrives, so
 * the page does not jump when real content replaces it.
 */
export default function Loading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading</span>
      <Skeleton className="h-6 w-56" />
      <Skeleton className="mt-2 h-4 w-[420px] max-w-full" />
      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-[104px] rounded-[var(--radius-card)]" />
        ))}
      </div>
      <Skeleton className="mt-3 h-[260px] rounded-[var(--radius-card)]" />
      <Skeleton className="mt-3 h-[320px] rounded-[var(--radius-card)]" />
    </div>
  );
}
