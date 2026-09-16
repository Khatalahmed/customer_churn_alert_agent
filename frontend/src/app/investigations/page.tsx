import Link from "next/link";

import {
  Card,
  ErrorPanel,
  NotMeasured,
  PageHeader,
  RiskBadge,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import { api, attempt, isError } from "@/lib/api";
import { percent } from "@/lib/format";
import { isAvailable } from "@/types/api";

export const dynamic = "force-dynamic";

export default async function InvestigationsPage() {
  const investigations = await attempt(api.investigations());

  if (isError(investigations)) {
    return (
      <>
        <PageHeader title="Investigations" />
        <ErrorPanel message={investigations.error} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Investigations"
        description="The agent reads ticket text and review prose for the customers the model shortlisted, and writes the explanation. It does not decide the risk level — code does that, from facts re-queried from the database."
      />

      {!isAvailable(investigations) ? (
        <NotMeasured reason={investigations.reason} how={investigations.how} />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-x-8 gap-y-2 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] px-5 py-3.5 text-[12px]">
            <span className="text-[var(--text-muted)]">
              <strong className="tnum font-semibold text-[var(--text)]">
                {investigations.customers.length}
              </strong>{" "}
              customers investigated
            </span>
            <span className="text-[var(--text-muted)]">
              <strong className="tnum font-semibold text-[var(--text)]">
                {investigations.tool_calls}
              </strong>{" "}
              tool calls recorded
            </span>
            <Link
              href="/evaluations#reliability"
              className="ml-auto text-[var(--accent)] hover:underline"
            >
              Agent reliability →
            </Link>
          </div>

          <Card padded={false} className="overflow-hidden">
            <Table>
              <thead>
                <tr>
                  <Th>Customer</Th>
                  <Th>Risk</Th>
                  <Th align="right">P(churn)</Th>
                  <Th>What the agent concluded</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {investigations.customers.map((customer) => (
                  <tr
                    key={customer.user_id}
                    className="transition-colors hover:bg-[var(--surface-2)]"
                  >
                    <Td>
                      <Link
                        href={`/investigations/${customer.user_id}`}
                        className="font-medium hover:text-[var(--accent)]"
                      >
                        {customer.full_name}
                      </Link>
                      <div className="tnum text-[11px] text-[var(--text-subtle)]">
                        #{customer.user_id}
                      </div>
                    </Td>
                    <Td>
                      <RiskBadge level={customer.risk_level} />
                    </Td>
                    <Td align="right" className="tnum">
                      {percent(customer.churn_probability)}
                    </Td>
                    <Td className="max-w-[640px] text-[var(--text-muted)]">
                      <span className="line-clamp-2">{customer.reason}</span>
                    </Td>
                    <Td align="right">
                      <Link
                        href={`/investigations/${customer.user_id}`}
                        className="text-[11.5px] text-[var(--accent)] hover:underline"
                      >
                        Trace
                      </Link>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>

          {!investigations.trace_available ? (
            <p className="mt-3 text-[11.5px] text-[var(--text-subtle)]">
              No tool trace was saved for this run, so the per-customer steps are unavailable.
            </p>
          ) : null}
        </>
      )}
    </>
  );
}
