import { Check, X } from "lucide-react";

import { CalibrationChart } from "@/components/evaluation/Calibration";
import {
  Badge,
  Card,
  CardHeader,
  ErrorPanel,
  Field,
  Metric,
  NotMeasured,
  PageHeader,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import { api, attempt, isError } from "@/lib/api";
import { compact, decimal, lift, moment, percent, percentShort, points } from "@/lib/format";
import { isAvailable } from "@/types/api";

export const dynamic = "force-dynamic";

export default async function EvaluationsPage() {
  const [evaluations, reliability, outcomes] = await Promise.all([
    attempt(api.evaluations()),
    attempt(api.reliability()),
    attempt(api.outcomes()),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Measured, not claimed"
        title="Evaluations"
        description="What this system has actually been measured to do — on a held-out snapshot the model never saw, and on the agent run currently in the repository."
      />

      {/* ---------------- model ---------------- */}
      {isError(evaluations) ? (
        <ErrorPanel message={evaluations.error} />
      ) : !isAvailable(evaluations) ? (
        <NotMeasured reason={evaluations.reason} how={evaluations.how} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric
              label="PR-AUC"
              value={decimal(evaluations.pr_auc, 3)}
              hint={`${lift(evaluations.pr_auc_lift)} its floor of ${decimal(evaluations.pr_auc_floor, 3)} — the honest summary at a ${percent(evaluations.base_rate, 1)} base rate`}
            />
            <Metric
              label="Precision @ 15"
              value={percentShort(evaluations.at_k[0].precision)}
              hint={`${lift(evaluations.at_k[0].lift)} better than picking at random`}
            />
            <Metric
              label="ROC-AUC"
              value={decimal(evaluations.roc_auc, 3)}
              hint="flattering at this base rate — quoted second, never first"
            />
            <Metric
              label="Brier score"
              value={decimal(evaluations.brier_calibrated, 4)}
              hint={`from ${decimal(evaluations.brier_raw, 4)} before calibration`}
            />
          </div>

          <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr]">
            <Card>
              <CardHeader
                title="How far down the list is worth going"
                description="Precision and recall at each shortlist size. The agent investigates the top 15."
              />
              <Table>
                <thead>
                  <tr>
                    <Th align="right">K</Th>
                    <Th align="right">Precision</Th>
                    <Th align="right">Lift</Th>
                    <Th align="right">Recall</Th>
                  </tr>
                </thead>
                <tbody>
                  {evaluations.at_k.map((row) => (
                    <tr key={row.k}>
                      <Td align="right" className="tnum font-medium">
                        {row.k}
                      </Td>
                      <Td align="right" className="tnum">
                        {percent(row.precision, 1)}
                      </Td>
                      <Td align="right" className="tnum text-[var(--text-muted)]">
                        {lift(row.lift)}
                      </Td>
                      <Td align="right" className="tnum">
                        {percent(row.recall, 1)}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <dl className="mt-3 border-t border-[var(--border)] pt-2">
                <Field
                  label="Grouped CV AUC"
                  value={`${decimal(evaluations.cv_auc_mean, 3)} ± ${decimal(evaluations.cv_auc_std, 3)}`}
                  note="a customer never spans folds"
                />
                <Field
                  label="Held-out snapshot"
                  value={`${compact(evaluations.test_customers)} customers, ${evaluations.test_churn} churn`}
                  note={`cut off ${evaluations.test_cutoff.slice(0, 10)}`}
                />
              </dl>
            </Card>

            <Card>
              <CardHeader
                title="Is a probability a probability?"
                description="Predicted against observed, in quantile buckets. Close to the diagonal means the number can be multiplied by money."
              />
              <CalibrationChart rows={evaluations.calibration} />
              <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-subtle)]">
                Calibration is what licenses every rupee figure in this product. It is not free:
                it reorders slightly, costing PR-AUC, because the shipped model averages a fold
                ensemble rather than rescaling one model.
              </p>
            </Card>
          </div>

          <Card className="mt-3">
            <CardHeader
              title="What the model relies on"
              description="Gain-based importance from the booster. Exposure counts earn their place by telling the model how much to trust each rate."
            />
            <ul className="space-y-2">
              {evaluations.feature_importance.slice(0, 8).map((row) => (
                <li key={row.feature} className="flex items-center gap-3">
                  <span className="w-[190px] shrink-0 truncate font-mono text-[11.5px] text-[var(--text-muted)]">
                    {row.feature}
                  </span>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                    <span
                      className="block h-full rounded-full bg-[var(--accent)]"
                      style={{
                        width: `${(row.importance / evaluations.feature_importance[0].importance) * 100}%`,
                      }}
                    />
                  </span>
                  <span className="tnum w-[46px] shrink-0 text-right text-[11.5px]">
                    {decimal(row.importance, 3)}
                  </span>
                </li>
              ))}
            </ul>
          </Card>

          <p className="mt-2 text-[11px] text-[var(--text-subtle)]">
            Measured {moment(evaluations.measured_at.replace("T", " ").slice(0, 19))} by{" "}
            <code className="font-mono">churn.train_model</code>, on a snapshot dated after every
            training cutoff.
          </p>
        </>
      )}

      {/* ---------------- agent ---------------- */}
      <h2
        id="reliability"
        className="mt-10 scroll-mt-20 text-[22px] font-black tracking-tight"
      >
        Agent reliability
      </h2>
      <p className="mb-3 mt-1 max-w-3xl text-[12.5px] leading-relaxed text-[var(--text-muted)]">
        Accuracy says the verdict was right. These say the agent earned it: that its figures are
        true, that its sentences are true, and that it worked the way it was supposed to.
      </p>

      {isError(reliability) ? (
        <ErrorPanel message={reliability.error} />
      ) : !isAvailable(reliability) ? (
        <NotMeasured reason={reliability.reason} how={reliability.how} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric
              label="Evidence fidelity"
              value={percentShort(reliability.evidence.fidelity)}
              hint={`${reliability.evidence.matched} of ${reliability.evidence.checked} cited figures re-queried and matched`}
            />
            <Metric
              label="Prose fidelity"
              value={percentShort(reliability.prose.fidelity)}
              hint={`${reliability.prose.supported} of ${reliability.prose.claims} claims in the written reasons`}
            />
            <Metric
              label="Trajectory"
              value={`${reliability.trajectory.passed} / ${reliability.trajectory.total}`}
              hint={`rules passed over ${reliability.trajectory.tool_calls} tool calls`}
            />
            <Metric
              label="Failed tool calls"
              value={reliability.trajectory.errors}
              hint="errors during the run"
            />
          </div>

          <div className="mt-3 grid gap-3 lg:grid-cols-[1.2fr_1fr]">
            <Card>
              <CardHeader
                title="Trajectory rules"
                description="Graded from the recorded tool calls, not from the answer."
              />
              <ul className="space-y-1.5">
                {reliability.trajectory.rules.map((rule) => (
                  <li key={rule.rule} className="flex items-start gap-2.5 text-[12.5px]">
                    <span
                      className={
                        rule.passed
                          ? "mt-0.5 text-[var(--low)]"
                          : "mt-0.5 text-[var(--high)]"
                      }
                      aria-hidden
                    >
                      {rule.passed ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
                    </span>
                    <span className="flex-1">{rule.rule}</span>
                    <span className="text-[11px] text-[var(--text-subtle)]">{rule.detail}</span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <CardHeader
                title="What the prose checker could not check"
                description="Coverage is published next to fidelity so a high score cannot hide a narrow check."
              />
              <dl>
                <Field
                  label="Clause coverage"
                  value={percent(reliability.prose.coverage, 0)}
                  note="clauses yielding a checkable claim"
                />
                <Field
                  label="Unchecked clauses"
                  value={reliability.prose.unchecked_clauses}
                  note="mostly rubric restatement"
                />
                <Field label="Customers checked" value={reliability.customers} />
              </dl>
              <p className="mt-2 border-t border-[var(--border)] pt-2.5 text-[11px] leading-relaxed text-[var(--text-subtle)]">
                Claims are extracted by pattern, not by a second model — a model checking a model
                needs its own verifier. The price is comprehension, so the uncovered share is
                reported rather than rounded away.
              </p>
            </Card>
          </div>
        </>
      )}

      {/* ---------------- outcome experiment ---------------- */}
      <h2 className="mt-10 text-[22px] font-black tracking-tight">Did acting on it help?</h2>
      <p className="mb-3 mt-1 max-w-3xl text-[12.5px] leading-relaxed text-[var(--text-muted)]">
        Part of the worklist is held back by a seeded random draw. Without a control the number is
        meaningless: the customers you contact are the ones most likely to leave.
      </p>

      {isError(outcomes) ? (
        <ErrorPanel message={outcomes.error} />
      ) : !isAvailable(outcomes) ? (
        <NotMeasured reason={outcomes.reason} how={outcomes.how} />
      ) : (
        <Card>
          <div className="grid gap-5 lg:grid-cols-[1fr_1fr_1.1fr]">
            <div>
              <p className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
                Observed result
              </p>
              <p className="tnum mt-1.5 text-[24px] font-semibold">
                {points(outcomes.absolute_uplift_pp)}
              </p>
              <p className="mt-1 text-[11.5px] text-[var(--text-subtle)]">
                churn avoided, in percentage points
              </p>
              <p className="mt-2 text-[11.5px] text-[var(--text-muted)]">
                Relative:{" "}
                {outcomes.relative_uplift === null
                  ? "undefined — no control churn to remove"
                  : percent(outcomes.relative_uplift, 0)}
              </p>
            </div>

            <div>
              <p className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
                Statistical conclusion
              </p>
              <p className="mt-1.5">
                <Badge tone={outcomes.conclusive ? "good" : "neutral"}>
                  {outcomes.conclusive ? "Conclusive" : "Inconclusive"}
                </Badge>
              </p>
              <dl className="mt-2">
                <Field label="Fisher exact p" value={outcomes.p_value.toFixed(3)} />
                <Field
                  label="95% CI on the difference"
                  value={`${points(outcomes.difference_ci_pp[0])} … ${points(outcomes.difference_ci_pp[1])}`}
                />
              </dl>
            </div>

            <div>
              <p className="text-[11px] uppercase tracking-wide text-[var(--text-subtle)]">
                What would settle it
              </p>
              <p className="tnum mt-1.5 text-[24px] font-semibold">
                {compact(outcomes.power.per_arm)}
              </p>
              <p className="mt-1 text-[11.5px] text-[var(--text-subtle)]">
                customers per arm — {outcomes.power.assumptions}
              </p>
              <p className="mt-2 text-[11px] text-[var(--text-subtle)]">
                Planned from the {outcomes.power.base_rate_from}.
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 border-t border-[var(--border)] pt-3 sm:grid-cols-2">
            {(["treated", "control"] as const).map((arm) => {
              const group = outcomes[arm];
              return (
                <div key={arm} className="flex items-baseline justify-between gap-3">
                  <span className="text-[12px] capitalize text-[var(--text-muted)]">{arm}</span>
                  <span className="tnum text-[12.5px]">
                    {group.churned} / {group.n} churned ={" "}
                    <strong className="font-semibold">{percent(group.churn_rate, 1)}</strong>
                    <span className="ml-2 text-[11px] text-[var(--text-subtle)]">
                      95% CI {percent(group.ci[0], 0)}–{percent(group.ci[1], 0)}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-[var(--text-subtle)]">
            A worklist this size cannot measure retention uplift, and this panel says so rather
            than presenting the observed difference as a finding. In this dataset an intervention
            changes nothing about a customer&rsquo;s future, so approximately zero is the correct
            answer.
          </p>
        </Card>
      )}
    </>
  );
}
