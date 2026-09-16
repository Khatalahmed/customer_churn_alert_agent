import Link from "next/link";
import { ArrowLeft, Check, ListOrdered, MessageSquare, Star, X } from "lucide-react";

import {
  Card,
  CardHeader,
  ErrorPanel,
  NotMeasured,
  RiskBadge,
  Stat,
} from "@/components/ui/primitives";
import { api, attempt, isError } from "@/lib/api";
import { cn, duration, percent } from "@/lib/format";
import { isAvailable, type ToolCall } from "@/types/api";

export const dynamic = "force-dynamic";

/** Which sub-agent owns a tool — the architecture, read off the trace. */
const AGENTS: Record<string, { agent: string; icon: typeof Star; describes: string }> = {
  get_churn_candidates: {
    agent: "Risk ranker",
    icon: ListOrdered,
    describes: "Ranked the scored customers and returned the shortlist",
  },
  get_user_tickets: {
    agent: "Ticket analyst",
    icon: MessageSquare,
    describes: "Read the support history and counted what is still open",
  },
  get_user_reviews: {
    agent: "Review analyst",
    icon: Star,
    describes: "Read the review text and took the worst rating",
  },
};

function Step({ call }: { call: ToolCall }) {
  const meta = AGENTS[call.tool];
  const Icon = meta?.icon ?? ListOrdered;
  return (
    <li className="flex items-start gap-3 border-b border-[var(--border)] py-3 last:border-0">
      <span
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
          call.ok
            ? "border-[var(--low-border)] bg-[var(--low-soft)] text-[var(--low)]"
            : "border-[var(--high-border)] bg-[var(--high-soft)] text-[var(--high)]",
        )}
        aria-hidden
      >
        {call.ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-[12.5px] font-medium">{meta?.agent ?? call.tool}</span>
          <code className="font-mono text-[11px] text-[var(--text-subtle)]">
            {call.tool}({Object.entries(call.args).map(([k, v]) => `${k}=${String(v)}`).join(", ")})
          </code>
          <span className="tnum ml-auto text-[11px] text-[var(--text-subtle)]">
            {duration(call.ms)}
          </span>
        </div>
        <p className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-[var(--text-subtle)]">
          <Icon className="h-3 w-3" aria-hidden />
          {meta?.describes ?? "Tool call"}
          {call.ok ? null : <span className="text-[var(--high)]">— failed</span>}
        </p>
      </div>
    </li>
  );
}

export default async function InvestigationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const userId = Number(id);
  const investigation = await attempt(api.investigation(userId));

  if (isError(investigation)) {
    return <ErrorPanel message={investigation.error} />;
  }

  if (!isAvailable(investigation)) {
    return (
      <>
        <Link
          href="/investigations"
          className="mb-4 inline-flex items-center gap-1.5 text-[12px] text-[var(--text-subtle)] hover:text-[var(--text)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          All investigations
        </Link>
        <NotMeasured reason={investigation.reason} how={investigation.how} />
      </>
    );
  }

  const { customer, steps } = investigation;
  const agentsUsed = new Set(steps.map((s) => AGENTS[s.tool]?.agent ?? s.tool));

  return (
    <>
      <Link
        href="/investigations"
        className="mb-4 inline-flex items-center gap-1.5 text-[12px] text-[var(--text-subtle)] transition-colors hover:text-[var(--text)]"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
        All investigations
      </Link>

      <header className="mb-5 flex flex-wrap items-start justify-between gap-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[20px] font-semibold tracking-tight">{customer.full_name}</h1>
            <RiskBadge level={customer.risk_level} />
          </div>
          <p className="tnum mt-1 text-[12px] text-[var(--text-subtle)]">
            Investigation · customer #{customer.user_id} ·{" "}
            <Link href={`/customers/${customer.user_id}`} className="hover:text-[var(--text)]">
              open Customer 360 →
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap gap-x-9 gap-y-3">
          <Stat label="Churn probability" value={percent(customer.churn_probability)} />
          <Stat label="Sub-agents used" value={agentsUsed.size} />
          <Stat label="Tool calls" value={steps.length} hint="for this customer" />
        </div>
      </header>

      <Card>
        <CardHeader
          title="Conclusion"
          description="Written by the LLM. The risk level beside it was not — that is computed in code from facts re-queried from the database."
        />
        <p className="text-[13.5px] leading-relaxed">{customer.reason}</p>
      </Card>

      <Card className="mt-3">
        <CardHeader
          title="How it got there"
          description="Every tool call the run made for this customer, in order, with what each returned and how long it took. Observable actions only — no hidden reasoning is shown, because none is recorded."
        />
        {steps.length === 0 ? (
          <p className="text-[12px] text-[var(--text-subtle)]">
            No tool trace was saved for this run.
          </p>
        ) : (
          <ol>
            {steps.map((call, index) => (
              <Step key={`${call.tool}-${index}`} call={call} />
            ))}
          </ol>
        )}
      </Card>

      <Card className="mt-3">
        <CardHeader
          title="What was checked afterwards"
          description="The same three checks that run over every investigation."
        />
        <ul className="space-y-2 text-[12px] text-[var(--text-muted)]">
          <li>
            <strong className="font-medium text-[var(--text)]">Evidence fidelity</strong> — each of
            the six figures in the agent&rsquo;s schema was re-computed from the database and
            compared.
          </li>
          <li>
            <strong className="font-medium text-[var(--text)]">Prose fidelity</strong> — the claims
            inside the sentence above were parsed and re-queried: ticket counts and categories,
            star ratings, what a complaint says, login movements.
          </li>
          <li>
            <strong className="font-medium text-[var(--text)]">Trajectory</strong> — nine rules over
            the tool calls: ranked once, checked tickets and reviews for everyone, investigated
            nobody off the shortlist, stayed inside the call budget.
          </li>
        </ul>
        <Link
          href="/evaluations#reliability"
          className="mt-3 inline-block text-[12px] text-[var(--accent)] hover:underline"
        >
          See the results for this run →
        </Link>
      </Card>
    </>
  );
}
