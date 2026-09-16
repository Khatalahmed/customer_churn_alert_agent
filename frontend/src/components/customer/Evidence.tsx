import { BadgeCheck, MessageSquareWarning, Star, TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/primitives";
import { cn } from "@/lib/format";
import type { CustomerView } from "@/types/api";

/**
 * The facts behind the verdict, each marked verified.
 *
 * "Verified" here is not decoration: every number shown was re-queried from
 * the database by `verifier.real_facts` on this request, independently of
 * whatever the agent wrote. That is what the tick means, and it is why the
 * caption says which check produced it.
 */
export function EvidencePanel({ customer }: { customer: CustomerView }) {
  const { evidence } = customer;
  const loginsUp = evidence.logins_last_14d >= evidence.logins_prev_14_28d;

  const items = [
    {
      icon: MessageSquareWarning,
      title:
        evidence.unresolved_serious_tickets > 0
          ? `${evidence.unresolved_serious_tickets} unresolved ${evidence.unresolved_serious_tickets === 1 ? "complaint" : "complaints"}`
          : "No unresolved serious complaints",
      body:
        evidence.unresolved_serious_tickets > 0
          ? "About delivery, payment, refund, quality or a wrong order — the categories that signal a real problem."
          : `${evidence.total_tickets} ticket${evidence.total_tickets === 1 ? "" : "s"} in total, none of them an open serious complaint.`,
      tone: evidence.unresolved_serious_tickets > 0 ? "bad" : "neutral",
    },
    {
      icon: Star,
      title:
        evidence.worst_review_rating === 0
          ? "No reviews written"
          : `Worst review: ${evidence.worst_review_rating} star${evidence.worst_review_rating === 1 ? "" : "s"}`,
      body:
        evidence.worst_review_rating === 0
          ? "Silence is not dissatisfaction — the rubric does not treat a missing review as evidence."
          : evidence.worst_review_rating <= 2
            ? "A rating of 2 or below counts as dissatisfaction on its own."
            : "Above the dissatisfaction threshold, so it does not qualify.",
      tone: evidence.worst_review_rating >= 1 && evidence.worst_review_rating <= 2 ? "bad" : "neutral",
    },
    {
      icon: loginsUp ? TrendingUp : TrendingDown,
      title: `Logins ${loginsUp ? "steady or rising" : "falling"}: ${evidence.logins_prev_14_28d} → ${evidence.logins_last_14d}`,
      body: "Last 14 days against the 14 before — the same windows the model's features use.",
      tone: customer.disengagement ? "bad" : "good",
    },
    {
      icon: BadgeCheck,
      title: `${evidence.total_orders} orders, ${evidence.total_tickets} tickets on record`,
      body: "Exposure counts: they tell the model how much to trust every rate above.",
      tone: "neutral",
    },
  ] as const;

  return (
    <Card>
      <CardHeader
        title="Evidence supporting the assessment"
        description="Every figure re-queried from the database on this request, independently of anything the agent wrote."
      />
      <ul className="space-y-2.5">
        {items.map((item) => (
          <li
            key={item.title}
            className="flex gap-3 rounded-[var(--radius-control)] border border-[var(--border)] p-3"
          >
            <item.icon
              className={cn(
                "mt-0.5 h-4 w-4 shrink-0",
                item.tone === "bad"
                  ? "text-[var(--high)]"
                  : item.tone === "good"
                    ? "text-[var(--low)]"
                    : "text-[var(--text-subtle)]",
              )}
              aria-hidden
            />
            <div className="min-w-0">
              <p className="text-[12.5px] font-medium">{item.title}</p>
              <p className="mt-0.5 text-[11.5px] leading-relaxed text-[var(--text-subtle)]">
                {item.body}
              </p>
            </div>
            <span
              className="ml-auto shrink-0 self-start text-[11px] text-[var(--low)]"
              title="Re-queried from the database by the evidence verifier"
            >
              ✓ Verified
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-4 rounded-[var(--radius-control)] bg-[var(--surface-2)] p-3">
        <p className="text-[11.5px] leading-relaxed text-[var(--text-muted)]">
          <strong className="font-medium">How the level was decided.</strong> Dissatisfaction
          {customer.dissatisfaction ? " fired" : " did not fire"}; disengagement
          {customer.disengagement ? " fired" : " did not fire"}. Both means HIGH, one means MEDIUM,
          neither means LOW. A high model probability alone never raises the level — the evidence
          has to back it.
        </p>
      </div>
    </Card>
  );
}
