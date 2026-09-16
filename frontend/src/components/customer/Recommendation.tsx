import { ArrowDownRight, CircleSlash, ShieldCheck, TriangleAlert } from "lucide-react";

import { Badge, Card, Field } from "@/components/ui/primitives";
import { humanise, money, moneySigned, percent } from "@/lib/format";
import type { CustomerView } from "@/types/api";

/**
 * The recommendation, with its economics visible rather than implied.
 *
 * The spec's rule for this component is "do not hide economic assumptions",
 * and the hardest case is the downgrade: when the fix the complaint calls for
 * does not pay, the card has to say what was dropped, what replaced it, and
 * what would have justified the original.
 */
export function Recommendation({ customer }: { customer: CustomerView }) {
  const currency = customer.currency;
  const [low, high] = customer.value_range;

  return (
    <Card accent>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10.5px] font-extrabold uppercase tracking-[0.2em] text-[var(--accent)]">
            Recommended action
          </p>
          <h2 className="mt-2 text-[22px] font-black tracking-tight">
            {customer.intervention_label}
          </h2>
        </div>
        {customer.worth_doing ? (
          <Badge tone={customer.robust ? "good" : "warn"}>
            {customer.robust ? (
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
            ) : (
              <TriangleAlert className="h-3.5 w-3.5" aria-hidden />
            )}
            {customer.robust ? "Economically justified" : "Marginal"}
          </Badge>
        ) : (
          <Badge tone="neutral">
            <CircleSlash className="h-3.5 w-3.5" aria-hidden />
            Not worth doing
          </Badge>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
            Expected value
          </p>
          <p className="tnum mt-1 text-[20px] font-semibold">
            {moneySigned(customer.expected_value, currency)}
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
            Intervention cost
          </p>
          <p className="tnum mt-1 text-[20px] font-semibold">{money(customer.cost, currency)}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
            Margin at risk
          </p>
          <p className="tnum mt-1 text-[20px] font-semibold">
            {money(customer.margin_at_risk, currency)}
          </p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
            Break-even P(churn)
          </p>
          <p className="tnum mt-1 text-[20px] font-semibold">
            {percent(customer.break_even_probability)}
          </p>
        </div>
      </div>

      <p className="mt-3 text-[11.5px] leading-relaxed text-[var(--text-subtle)]">
        This action pays for itself above {percent(customer.break_even_probability)} churn risk or{" "}
        {money(customer.break_even_margin, currency)} of margin at risk; this customer is at{" "}
        {percent(customer.churn_probability)} and {money(customer.margin_at_risk, currency)}.
        Halving or increasing the assumed uplift by half moves the expected value between{" "}
        <span className="tnum">{moneySigned(low, currency)}</span> and{" "}
        <span className="tnum">{moneySigned(high, currency)}</span>.
      </p>

      {customer.downgraded_from ? (
        <div className="mt-4 rounded-[var(--radius-control)] border border-[var(--medium-border)] bg-[var(--medium-soft)] p-3.5">
          <p className="flex items-center gap-1.5 text-[12px] font-medium text-[var(--medium)]">
            <ArrowDownRight className="h-3.5 w-3.5" aria-hidden />
            Downgraded from {humanise(customer.downgraded_from)}
          </p>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-[var(--text-muted)]">
            The fix this complaint actually calls for does not pay for itself on this customer, so
            the plan recommends the cheapest action that does.
          </p>
          {customer.matched_fix_break_even_margin ? (
            <dl className="mt-2 border-t border-[var(--medium-border)] pt-1">
              <Field
                label={`${humanise(customer.matched_fix ?? "")} would need`}
                value={money(customer.matched_fix_break_even_margin, currency)}
                note="of margin at risk"
              />
              <Field
                label="…or a churn probability of"
                value={percent(customer.matched_fix_break_even_probability ?? 0)}
              />
            </dl>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
