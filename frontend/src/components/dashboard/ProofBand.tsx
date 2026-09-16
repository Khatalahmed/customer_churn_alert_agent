import Link from "next/link";
import { ArrowUpRight, BadgeCheck, Crosshair, Route, Target } from "lucide-react";

import { Gauge } from "@/components/ui/Gauge";
import { lift, percent, percentShort } from "@/lib/format";
import { isAvailable, type Evaluations, type Reliability } from "@/types/api";

/**
 * The four numbers this system actually earned, given the place they deserve.
 *
 * Every one is read from the evaluation artefact or recomputed by the
 * reliability checks on request — none is written into this file. If a
 * measurement is missing the panel says so and disappears rather than
 * showing a flattering placeholder, which is the same rule the rest of the
 * product follows.
 */
export function ProofBand({
  evaluations,
  reliability,
}: {
  evaluations: Evaluations | { error: string };
  reliability: Reliability | { error: string };
}) {
  const evals = "error" in evaluations ? null : isAvailable(evaluations) ? evaluations : null;
  const rel = "error" in reliability ? null : isAvailable(reliability) ? reliability : null;
  if (!evals && !rel) return null;

  const topK = evals?.at_k[0];

  return (
    <section className="brand-band mb-3 rounded-[var(--radius-card)] shadow-[var(--shadow-lg)]">
      <div className="relative z-10 flex flex-wrap items-center gap-x-10 gap-y-7 px-6 py-6 sm:px-8">
        <div className="min-w-[180px] flex-1">
          <p className="text-[10.5px] font-extrabold uppercase tracking-[0.2em] text-indigo-200">
            Measured, not claimed
          </p>
          <h2 className="mt-2 text-[21px] font-black leading-tight tracking-tight text-white">
            The evidence behind
            <br />
            today&rsquo;s shortlist
          </h2>
          <Link
            href="/evaluations"
            className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-bold text-indigo-200 transition-colors hover:text-white"
          >
            See every evaluation
            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>

        {topK ? (
          <ProofStat
            icon={<Target className="h-3.5 w-3.5" aria-hidden />}
            value={lift(topK.lift)}
            label="better than random"
            detail={`${percentShort(topK.precision)} of the top ${topK.k} really churn, against a ${percent(evals!.base_rate, 1)} base rate`}
          />
        ) : null}

        {evals ? (
          <ProofStat
            icon={<Crosshair className="h-3.5 w-3.5" aria-hidden />}
            value={lift(evals.pr_auc_lift)}
            label="PR-AUC vs its floor"
            detail={`${evals.pr_auc.toFixed(3)} against the ${evals.pr_auc_floor.toFixed(3)} a coin flip scores here`}
          />
        ) : null}

        {rel ? (
          <div className="flex items-center gap-6 text-white">
            <Gauge
              value={rel.evidence.fidelity}
              label={percentShort(rel.evidence.fidelity)}
              caption="Evidence"
            />
            <Gauge
              value={rel.trajectory.total ? rel.trajectory.passed / rel.trajectory.total : 0}
              label={`${rel.trajectory.passed}/${rel.trajectory.total}`}
              caption="Trajectory"
            />
            <div className="hidden max-w-[190px] text-[11px] leading-relaxed text-indigo-200 xl:block">
              <p className="flex items-center gap-1.5 font-bold text-white">
                <BadgeCheck className="h-3.5 w-3.5" aria-hidden />
                Every cited figure re-queried
              </p>
              <p className="mt-1.5 flex items-start gap-1.5">
                <Route className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                <span>
                  and the agent graded on how it worked, not just on what it concluded
                </span>
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function ProofStat({
  icon,
  value,
  label,
  detail,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  detail: string;
}) {
  return (
    <div className="min-w-[152px]">
      <p className="flex items-center gap-1.5 text-[10.5px] font-extrabold uppercase tracking-[0.16em] text-indigo-200">
        {icon}
        {label}
      </p>
      <p className="tnum mt-1.5 text-[40px] font-black leading-none tracking-tight text-white drop-shadow-sm">
        {value}
      </p>
      <p className="mt-2 max-w-[210px] text-[11px] leading-relaxed text-indigo-200/90">{detail}</p>
    </div>
  );
}
