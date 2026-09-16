import { Card, CardHeader, NotMeasured } from "@/components/ui/primitives";
import { cn } from "@/lib/format";
import { isAvailable, type Explanation } from "@/types/api";

/**
 * What the model reacted to, kept visibly separate from what the agent found.
 *
 * SHAP explains the model's arithmetic — which features moved this score, and
 * in which direction. It does not explain the customer. The caption says so,
 * because a bar chart labelled "why they are leaving" is a causal claim this
 * project has no basis for making.
 */
export function ModelSignal({ explanation }: { explanation: Explanation }) {
  if (!isAvailable(explanation)) {
    return (
      <Card>
        <CardHeader title="Why the model is concerned" />
        <NotMeasured reason={explanation.reason} how={explanation.how} />
      </Card>
    );
  }

  const widest = Math.max(...explanation.factors.map((f) => Math.abs(f.contribution)), 0.0001);

  return (
    <Card>
      <CardHeader
        title="Why the model is concerned"
        description="Model signal — the features that moved this customer's score, from SHAP on the booster."
      />
      <ul className="space-y-3">
        {explanation.factors.map((factor) => {
          const share = Math.abs(factor.contribution) / widest;
          const raises = factor.contribution > 0;
          return (
            <li key={factor.feature}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[12.5px]">{factor.label}</span>
                <span className="tnum text-[11.5px] text-[var(--text-subtle)]">
                  {factor.value === null ? "no data" : factor.value}
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      raises ? "bg-[var(--high)]" : "bg-[var(--low)]",
                    )}
                    style={{ width: `${Math.max(share * 100, 4)}%` }}
                  />
                </div>
                <span
                  className={cn(
                    "tnum w-[84px] shrink-0 text-right text-[11px]",
                    raises ? "text-[var(--high)]" : "text-[var(--low)]",
                  )}
                >
                  {raises ? "raises" : "lowers"} {Math.abs(factor.contribution).toFixed(2)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 border-t border-[var(--border)] pt-3 text-[11px] leading-relaxed text-[var(--text-subtle)]">
        These are contributions to the model&rsquo;s <em>ranking</em>, not causes of the
        customer&rsquo;s behaviour, and not the calibrated probability — the shipped model is a
        calibrated ensemble on top of the booster SHAP can read. Treat them as a description of the
        model, and the evidence panel as a description of the customer.
      </p>
    </Card>
  );
}
