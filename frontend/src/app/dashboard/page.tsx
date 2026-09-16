import Link from "next/link";
import { AlertTriangle, ArrowRight, IndianRupee, TrendingUp, Users, Wallet } from "lucide-react";

import { ProofBand } from "@/components/dashboard/ProofBand";
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
  // The proof band's two sources are cached server-side, so they cost a
  // request on the first load of an analysis period and nothing after.
  const [overview, worklist, evaluations, reliability] = await Promise.all([
    attempt(api.overview()),
    attempt(api.worklist()),
    attempt(api.evaluations()),
    attempt(api.reliability()),
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
        eyebrow="Today"
        title="Overview"
        description={`What needs attention as of ${moment(overview.analysis_time)}. Every figure is computed from data before that moment only.`}
      >
        <Link
          href="/worklist"
          className="flex items-center gap-2 rounded-[var(--radius-control)] px-4 py-2 text-[13px] font-semibold text-white transition-all duration-200 hover:opacity-90 hover:shadow-[0_0_20px_rgba(99,102,241,0.4)]"
          style={{ background: "var(--accent-grad)" }}
        >
          Open worklist
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </PageHeader>

      <ProofBand evaluations={evaluations} reliability={reliability} />

      {/* Metric cards — staggered entrance */}
      <div className="metric-stagger grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Metric
          label="Customers scored"
          value={compact(overview.scored_customers)}
          icon={<Users className="h-[17px] w-[17px]" strokeWidth={2.2} />}
          hint="every customer active at the analysis time"
        />
        <Metric
          label="High risk"
          value={overview.risk_mix.HIGH}
          tone="HIGH"
          icon={<AlertTriangle className="h-[17px] w-[17px]" strokeWidth={2.2} />}
          hint="unresolved complaint and falling logins"
        />
        <Metric
          label="Medium risk"
          value={overview.risk_mix.MEDIUM}
          tone="MEDIUM"
          icon={<TrendingUp className="h-[17px] w-[17px]" strokeWidth={2.2} />}
          hint="one of the two signals"
        />
        <Metric
          label="Margin at risk"
          value={money(overview.margin_at_risk, overview.currency)}
          icon={<Wallet className="h-[17px] w-[17px]" strokeWidth={2.2} />}
          hint="on the shortlist, discounted"
        />
        <Metric
          label="Expected value"
          value={money(overview.expected_value_total, overview.currency)}
          icon={<IndianRupee className="h-[17px] w-[17px]" strokeWidth={2.2} />}
          hint={`${overview.worth_doing} of ${overview.shortlist_size} actions pay for themselves`}
        />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[1.35fr_1fr]">
        {/* Risk distribution chart */}
        <Card accent>
          <CardHeader
            title="Where the risk sits"
            description={`All ${compact(overview.scored_customers)} scored customers by churn probability. The shortlist is the red tail — the model's job is to find it, not to raise everyone's score.`}
          />
          <RiskDistribution bins={overview.probability_distribution} cutoff={shortlistCutoff} />
        </Card>

        {/* Risk level breakdown */}
        <Card>
          <CardHeader
            title="Risk levels"
            description={overview.risk_mix_scope}
          />
          <dl className="space-y-4">
            {(["HIGH", "MEDIUM", "LOW"] as const).map((level) => {
              const count = overview.risk_mix[level];
              const share = overview.shortlist_size ? count / overview.shortlist_size : 0;
              const gradMap = {
                HIGH:   "linear-gradient(90deg, #ef4444, #f87171)",
                MEDIUM: "linear-gradient(90deg, #f59e0b, #fbbf24)",
                LOW:    "linear-gradient(90deg, #22c55e, #4ade80)",
              };
              const glowMap = {
                HIGH:   "rgba(239,68,68,0.3)",
                MEDIUM: "rgba(245,158,11,0.25)",
                LOW:    "rgba(34,197,94,0.2)",
              };
              return (
                <div key={level}>
                  <div className="flex items-baseline justify-between">
                    <dt className="text-[12px] font-medium text-[var(--text-muted)]">{level}</dt>
                    <dd className="tnum text-[13px] font-semibold text-[var(--text)]">
                      {count}
                      <span className="ml-1.5 text-[11px] font-normal text-[var(--text-subtle)]">
                        {percent(share, 0)}
                      </span>
                    </dd>
                  </div>
                  <div
                    className="mt-2 h-2 overflow-hidden rounded-full"
                    style={{ background: "var(--surface-3)" }}
                  >
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.max(share * 100, count ? 2 : 0)}%`,
                        background: gradMap[level],
                        boxShadow: `0 0 8px ${glowMap[level]}`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </dl>
          <p
            className="mt-5 pt-4 text-[11.5px] leading-relaxed text-[var(--text-subtle)]"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            The model picks <em>who</em> to look at. The risk level is then assigned by code from
            facts re-queried from the database — not by the model, and not by the LLM.
          </p>
        </Card>
      </div>

      {/* Priority worklist */}
      <Card className="mt-3">
        <CardHeader
          title="Priority worklist"
          description="Ordered by expected value: the money a successful save is worth, minus what the action costs."
          action={
            <Link
              href="/worklist"
              className="flex items-center gap-1 text-[12px] font-medium text-[var(--accent)] transition-colors hover:text-[var(--accent-bright)]"
            >
              <TrendingUp className="h-3.5 w-3.5" aria-hidden />
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

      <p className="mt-4 text-[11.5px] text-[var(--text-subtle)]">{overview.note}</p>
    </>
  );
}
