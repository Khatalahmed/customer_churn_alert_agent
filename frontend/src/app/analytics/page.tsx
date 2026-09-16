import {
  Badge,
  Card,
  CardHeader,
  ErrorPanel,
  Field,
  NotMeasured,
  PageHeader,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import { api, attempt, isError } from "@/lib/api";
import { money, moneySigned, percent } from "@/lib/format";
import { isAvailable } from "@/types/api";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage() {
  const [economics, worklist] = await Promise.all([
    attempt(api.economics()),
    attempt(api.worklist()),
  ]);

  if (isError(economics)) {
    return (
      <>
        <PageHeader title="Analytics" />
        <ErrorPanel message={economics.error} />
      </>
    );
  }
  if (!isAvailable(economics)) {
    return (
      <>
        <PageHeader title="Analytics" />
        <NotMeasured reason={economics.reason} how={economics.how} />
      </>
    );
  }

  const currency = economics.currency;
  const chosen = isError(worklist)
    ? []
    : Object.entries(
        worklist.customers.reduce<Record<string, { count: number; value: number }>>(
          (acc, customer) => {
            const key = customer.intervention_label;
            acc[key] ??= { count: 0, value: 0 };
            acc[key].count += 1;
            acc[key].value += customer.expected_value;
            return acc;
          },
          {},
        ),
      );

  return (
    <>
      <PageHeader
        eyebrow="Unit economics"
        title="Analytics"
        description="What each intervention would have to be worth before it is worth doing — and what the current worklist actually justifies."
      />

      <div className="rounded-[var(--radius-card)] border border-[var(--medium-border)] bg-[var(--medium-soft)] px-4 py-3">
        <p className="text-[12px] leading-relaxed text-[var(--text-muted)]">
          <strong className="font-medium text-[var(--medium)]">Illustrative figures.</strong>{" "}
          {economics.note}. Every rupee below follows from the assumptions in the panel at the
          bottom of this page; replace them with real finance numbers before believing any of it.
        </p>
      </div>

      <Card className="mt-3">
        <CardHeader
          title="Intervention economics"
          description={`What each action costs, what share of would-be churners it is assumed to rescue, and how much margin must be at risk before it pays — shown at a ${percent(economics.example_probability, 0)} churn probability.`}
        />
        <Table>
          <thead>
            <tr>
              <Th>Intervention</Th>
              <Th align="right">Cost</Th>
              <Th align="right">Assumed uplift</Th>
              <Th align="right">Break-even margin</Th>
              <Th>Reach on this worklist</Th>
            </tr>
          </thead>
          <tbody>
            {economics.interventions
              .filter((intervention) => intervention.key !== "none")
              .map((intervention) => {
                const used = chosen.find(([label]) => label === intervention.label);
                return (
                  <tr key={intervention.key} className="hover:bg-[var(--surface-2)]">
                    <Td className="font-medium">{intervention.label}</Td>
                    <Td align="right" className="tnum">
                      {money(intervention.cost, currency)}
                    </Td>
                    <Td align="right" className="tnum">
                      {percent(intervention.uplift, 0)}
                    </Td>
                    <Td align="right" className="tnum">
                      {intervention.break_even_margin === null
                        ? "—"
                        : money(intervention.break_even_margin, currency)}
                    </Td>
                    <Td>
                      {used ? (
                        <span className="text-[12px]">
                          {used[1].count} customer{used[1].count === 1 ? "" : "s"} ·{" "}
                          <span className="tnum">{moneySigned(used[1].value, currency)}</span>
                        </span>
                      ) : (
                        <span className="text-[11.5px] text-[var(--text-subtle)]">
                          never selected
                        </span>
                      )}
                    </Td>
                  </tr>
                );
              })}
          </tbody>
        </Table>
        <p className="mt-3 text-[11.5px] leading-relaxed text-[var(--text-subtle)]">
          A break-even margin above what the customers are worth is the whole finding: on this
          shortlist no paid intervention pays for itself, so the plan recommends the near-free
          email and reports what would have justified the real fix.
        </p>
      </Card>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Assumptions"
            description="Kept in the open, because an expected value is only as good as these."
          />
          <dl>
            <Field
              label="Gross margin rate"
              value={percent(economics.assumptions.margin_rate, 0)}
              note="of order value"
            />
            <Field
              label="Monthly survival"
              value={percent(economics.assumptions.monthly_survival, 0)}
              note="a rescued customer can still leave"
            />
            <Field
              label="Monthly discount"
              value={percent(economics.assumptions.monthly_discount, 0)}
              note="future money is worth less"
            />
            <Field
              label="Value horizon"
              value={`${economics.assumptions.value_horizon_months} months`}
            />
            <Field
              label="Uplift uncertainty"
              value={`±${percent(economics.assumptions.uplift_uncertainty, 0)}`}
              note="the sensitivity band"
            />
          </dl>
          <p className="mt-3 border-t border-[var(--border)] pt-3 text-[11.5px] leading-relaxed text-[var(--text-muted)]">
            Together these make a save worth{" "}
            <strong className="font-medium">
              {economics.assumptions.months_equivalent.toFixed(1)} months
            </strong>{" "}
            of margin rather than an arbitrary multiple:{" "}
            {money(economics.assumptions.present_value_of_1000_per_month, currency)} for a customer
            worth {money(1000, currency)} a month, decayed and discounted.
          </p>
        </Card>

        <Card>
          <CardHeader
            title="What the worklist actually justifies"
            description="The plan downgrades any action whose expected value does not clear its cost."
          />
          {isError(worklist) ? (
            <ErrorPanel message={worklist.error} />
          ) : (
            <>
              <dl>
                <Field
                  label="Actions worth taking"
                  value={`${worklist.worth_doing} of ${worklist.customers.length}`}
                />
                <Field
                  label="Total expected value"
                  value={money(worklist.expected_value_total, currency)}
                />
                <Field
                  label="Robust to a halved uplift"
                  value={`${worklist.customers.filter((c) => c.robust).length} of ${worklist.customers.length}`}
                  note="still positive at half the assumed effect"
                />
                <Field
                  label="Downgraded from a paid fix"
                  value={worklist.customers.filter((c) => c.downgraded_from).length}
                />
              </dl>
              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-[var(--border)] pt-3">
                {chosen.map(([label, stats]) => (
                  <Badge key={label} tone="neutral">
                    {label} × {stats.count}
                  </Badge>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
