import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { RiskDistribution } from "@/components/dashboard/RiskDistribution";
import { WorklistTable } from "@/components/worklist/WorklistTable";
import {
  Card,
  CardHeader,
  ErrorPanel,
  Metric,
  PageHeader,
} from "@/components/ui/primitives";
import { api, attempt, isError } from "@/lib/api";
import { compact, money, moment, percent } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [overview, worklist] = await Promise.all([
    attempt(api.overview()),
    attempt(api.worklist()),
  ]);

  if (isError(overview)) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorPanel message={overview.error} />
      </>
    );
  }

  const shortlistCutoff = isError(worklist)
    ? 1
    : Math.min(...worklist.customers.map((c) => c.churn_probability));

  return (
    <>
      <PageHeader
        title="Overview"
        description={`What needs attention as of ${moment(overview.analysis_time)}. Every figure is computed from data before that moment only.`}
      >
        <Link
          href="/worklist"
          className="flex items-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[12.5px] font-medium transition-colors hover:border-[var(--border-strong)]"
        >
          Open worklist
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Metric
          label="Customers scored"
          value={compact(overview.scored_customers)}
          hint="every customer active at the analysis time"
        />
        <Metric
          label="High risk"
          value={overview.risk_mix.HIGH}
          tone="HIGH"
          hint="unresolved complaint and falling logins"
        />
        <Metric
          label="Medium risk"
          value={overview.risk_mix.MEDIUM}
          tone="MEDIUM"
          hint="one of the two signals"
        />
        <Metric
          label="Margin at risk"
          value={money(overview.margin_at_risk, overview.currency)}
          hint="on the shortlist, discounted"
        />
        <Metric
          label="Expected value"
          value={money(overview.expected_value_total, overview.currency)}
          hint={`${overview.worth_doing} of ${overview.shortlist_size} actions pay for themselves`}
        />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[1.35fr_1fr]">
        <Card>
          <CardHeader
            title="Where the risk sits"
            description={`All ${compact(overview.scored_customers)} scored customers by churn probability. The shortlist is the red tail — the model's job is to find it, not to raise everyone's score.`}
          />
          <RiskDistribution bins={overview.probability_distribution} cutoff={shortlistCutoff} />
        </Card>

        <Card>
          <CardHeader
            title="Risk levels"
            description={overview.risk_mix_scope}
          />
          <dl className="space-y-3">
            {(["HIGH", "MEDIUM", "LOW"] as const).map((level) => {
              const count = overview.risk_mix[level];
              const share = overview.shortlist_size ? count / overview.shortlist_size : 0;
              return (
                <div key={level}>
                  <div className="flex items-baseline justify-between">
                    <dt className="text-[12px] text-[var(--text-muted)]">{level}</dt>
                    <dd className="tnum text-[12.5px] font-medium">
                      {count}
                      <span className="ml-1.5 text-[11px] text-[var(--text-subtle)]">
                        {percent(share, 0)}
                      </span>
                    </dd>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.max(share * 100, count ? 3 : 0)}%`,
                        background: `var(--${level.toLowerCase()})`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </dl>
          <p className="mt-4 border-t border-[var(--border)] pt-3 text-[11.5px] leading-relaxed text-[var(--text-subtle)]">
            The model picks <em>who</em> to look at. The risk level is then assigned by code from
            facts re-queried from the database — not by the model, and not by the LLM.
          </p>
        </Card>
      </div>

      <Card className="mt-3">
        <CardHeader
          title="Priority worklist"
          description="Ordered by expected value: the money a successful save is worth, minus what the action costs."
          action={
            <Link
              href="/worklist"
              className="text-[12px] text-[var(--accent)] hover:underline"
            >
              All {isError(worklist) ? "" : worklist.customers.length} →
            </Link>
          }
        />
        {isError(worklist) ? (
          <ErrorPanel message={worklist.error} />
        ) : (
          <WorklistTable
            customers={worklist.customers.slice(0, 6)}
            currency={overview.currency}
            dense
          />
        )}
      </Card>

      <p className="mt-3 text-[11.5px] text-[var(--text-subtle)]">{overview.note}</p>
    </>
  );
}
