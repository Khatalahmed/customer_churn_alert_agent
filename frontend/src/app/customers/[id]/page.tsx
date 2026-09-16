import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Radar } from "lucide-react";

import { EvidencePanel } from "@/components/customer/Evidence";
import { ModelSignal } from "@/components/customer/ModelSignal";
import { Recommendation } from "@/components/customer/Recommendation";
import { CustomerTimeline } from "@/components/customer/Timeline";
import { Card, ErrorPanel, RiskBadge, Stat } from "@/components/ui/primitives";
import { ApiError, api, attempt, isError } from "@/lib/api";
import { money, percent } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function CustomerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const userId = Number(id);
  if (!Number.isInteger(userId)) notFound();

  let customer;
  try {
    customer = await api.customer(userId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <ErrorPanel message={error instanceof Error ? error.message : "Unknown error"} />;
  }

  // The heavy panels load in parallel and fail independently: a missing model
  // artefact must not take the page down with it.
  const [timeline, explanation, investigation] = await Promise.all([
    attempt(api.timeline(userId)),
    attempt(api.explanation(userId)),
    attempt(api.investigation(userId)),
  ]);

  const investigated = !isError(investigation) && investigation.available;

  return (
    <>
      <Link
        href="/worklist"
        className="mb-4 inline-flex items-center gap-1.5 text-[12px] text-[var(--text-subtle)] transition-colors hover:text-[var(--text)]"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
        Back to worklist
      </Link>

      <header className="mb-5 flex flex-wrap items-start justify-between gap-5">
        <div className="flex items-center gap-4">
          <span
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[18px] text-[17px] font-black text-white shadow-[var(--shadow-accent)]"
            style={{ background: "var(--accent-grad)" }}
            aria-hidden
          >
            {customer.full_name
              .split(" ")
              .map((part) => part[0])
              .slice(0, 2)
              .join("")}
          </span>
          <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[26px] font-black tracking-tight">{customer.full_name}</h1>
            <RiskBadge level={customer.risk_level} />
            {customer.contacted_recently ? (
              <span className="text-[11px] text-[var(--text-subtle)]">contacted recently</span>
            ) : null}
          </div>
          <p className="tnum mt-1 text-[12px] font-semibold text-[var(--text-subtle)]">
            Customer #{customer.user_id}
          </p>
          </div>
        </div>

        <div className="flex flex-wrap items-start gap-x-9 gap-y-4">
          <Stat
            label="Churn probability"
            value={percent(customer.churn_probability)}
            hint="next 14 days, calibrated"
          />
          <Stat
            label="Margin at risk"
            value={money(customer.margin_at_risk, customer.currency)}
            hint="present value of the stream"
          />
          <Stat
            label="Orders / month"
            value={customer.orders_per_month.toFixed(1)}
            hint={`avg ${money(customer.avg_order_value, customer.currency)} per order`}
          />
          {investigated ? (
            <Link
              href={`/investigations/${customer.user_id}`}
              className="flex items-center gap-1.5 self-center rounded-[var(--radius-control)] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[12.5px] font-medium transition-colors hover:border-[var(--border-strong)]"
            >
              <Radar className="h-3.5 w-3.5" aria-hidden />
              Agent investigation
            </Link>
          ) : null}
        </div>
      </header>

      <Recommendation customer={customer} />

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <EvidencePanel customer={customer} />
        <ModelSignal explanation={isError(explanation) ? { available: false, reason: explanation.error, how: "" } : explanation} />
      </div>

      <div className="mt-3">
        {isError(timeline) ? (
          <ErrorPanel message={timeline.error} />
        ) : (
          <CustomerTimeline timeline={timeline} />
        )}
      </div>

      {investigated && investigation.available ? (
        <Card className="mt-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--text-subtle)]">
            What the agent wrote
          </p>
          <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-muted)]">
            {investigation.customer.reason}
          </p>
          <p className="mt-3 border-t border-[var(--border)] pt-3 text-[11px] text-[var(--text-subtle)]">
            Written by the LLM, then fact-checked: every figure in it was re-queried, and so was
            every claim the prose verifier could parse.{" "}
            <Link
              href={`/investigations/${customer.user_id}`}
              className="text-[var(--accent)] hover:underline"
            >
              See how it got there →
            </Link>
          </p>
        </Card>
      ) : null}
    </>
  );
}
