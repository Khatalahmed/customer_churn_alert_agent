import { WorklistTable } from "@/components/worklist/WorklistTable";
import { ErrorPanel, Empty, PageHeader, Stat } from "@/components/ui/primitives";
import { api, attempt, isError } from "@/lib/api";
import { money, moment } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function WorklistPage() {
  const worklist = await attempt(api.worklist(15));

  if (isError(worklist)) {
    return (
      <>
        <PageHeader title="Worklist" />
        <ErrorPanel message={worklist.error} />
      </>
    );
  }

  const currency = worklist.customers[0]?.currency ?? "Rs";
  const marginAtRisk = worklist.customers.reduce((sum, c) => sum + c.margin_at_risk, 0);
  const cost = worklist.customers.reduce((sum, c) => sum + (c.worth_doing ? c.cost : 0), 0);

  return (
    <>
      <PageHeader
        title="Worklist"
        description={`The customers to act on as of ${moment(worklist.analysis_time)} — chosen by the model, graded by the rubric, and priced before they reach this table.`}
      />

      {worklist.customers.length === 0 ? (
        <Empty
          title="No customers require attention"
          body="Your current worklist is clear. Everyone scored is either below the risk threshold or was contacted in the last 30 days."
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-x-10 gap-y-4 rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] px-5 py-4">
            <Stat label="Customers" value={worklist.customers.length} hint="top by churn risk" />
            <Stat
              label="Worth acting on"
              value={`${worklist.worth_doing} / ${worklist.customers.length}`}
              hint="expected value above cost"
            />
            <Stat
              label="Margin at risk"
              value={money(marginAtRisk, currency)}
              hint="present value, all listed"
            />
            <Stat
              label="Intervention cost"
              value={money(cost, currency)}
              hint="if every worthwhile action is taken"
            />
            <Stat
              label="Expected value"
              value={money(worklist.expected_value_total, currency)}
              hint="net of that cost"
            />
          </div>

          <WorklistTable customers={worklist.customers} currency={currency} />

          <p className="mt-4 max-w-3xl text-[11.5px] leading-relaxed text-[var(--text-subtle)]">
            {worklist.note}. Expected value is P(churn) × the present value of the customer&rsquo;s
            margin × the intervention&rsquo;s assumed uplift, minus its cost — and the cost is paid
            for everyone contacted, including those who were never going to leave.
          </p>
        </>
      )}
    </>
  );
}
