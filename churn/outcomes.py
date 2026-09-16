"""
outcomes.py

WHAT : Closes the loop. Logs what we did to whom (holding back a random
       control group), then — once the horizon has passed — checks what
       actually happened and measures the uplift we really got.

WHAT IT MEASURES
  The intervention experiment: did acting on the model's shortlist
  reduce churn, compared to a random hold-out group that got nothing?
  Reports absolute uplift (percentage points of churn avoided), relative
  uplift (share of would-be churn removed), a Fisher exact p-value, and
  a Newcombe confidence interval on the difference.

WHAT IT DOES NOT MEASURE
  - Whether the model's predictions are accurate (that is eval.py / metrics.py).
  - Whether a specific intervention's assumed uplift (in actions.py) is correct;
    the experiment measures the NET effect of (model targeting + intervention),
    not the intervention in isolation.
  - Anything about customers NOT in the worklist (the control group is a hold-out
    from the worklist, not a random sample of the whole customer base).

WHEN TO UPDATE
  Run `python -m churn.outcomes` after every worklist cycle once the horizon
  has passed (horizon_days after the analysis time).
  The reported sample sizes will almost certainly be too small to be conclusive
  at this scale; the power calculation shows how many customers per arm would
  be needed to settle the question.
"""
import json
import math
import random
from datetime import datetime, timedelta

from .config import ACTION_LOG_PATH, HORIZON_DAYS

# The previous 15-person worklist with a 30% control arm could never answer a
# causal question.  A dedicated experiment uses a 600-person cohort, balanced
# 1:1, which targets the ~300 customers per arm required by the power plan.
CONTROL_FRACTION = 0.5
EXPERIMENT_COHORT_SIZE = 600
EXPERIMENT_TARGET_PER_ARM = EXPERIMENT_COHORT_SIZE // 2
EXPERIMENT_INTERVENTION = "email_nudge"
ALPHA = 0.05                    # two-sided significance level for "conclusive"
MIN_EVENTS_FOR_PLANNING = 5     # below this, an observed rate is not worth planning on

# Normal quantiles, tabulated rather than imported: this module needs four
# numbers, not a dependency. z_alpha is two-sided.
Z_ALPHA_BY_LEVEL = {0.10: 1.6449, 0.05: 1.9600, 0.01: 2.5758}
Z_POWER_BY_LEVEL = {0.80: 0.8416, 0.90: 1.2816, 0.95: 1.6449}
Z_ALPHA = Z_ALPHA_BY_LEVEL[ALPHA]


def assign_control(user_ids, fraction: float = CONTROL_FRACTION, seed: int = 42) -> set:
    """Pick the control group by a seeded draw - never by judgement."""
    rng = random.Random(seed)
    ids = sorted(user_ids)
    n_control = round(len(ids) * fraction)
    return set(rng.sample(ids, n_control)) if n_control else set()


def assign_control_stratified(customers: list[dict], fraction: float = CONTROL_FRACTION,
                              seed: int = 42, strata: int = 10) -> set:
    """Randomise within risk bands so treatment and control start comparable.

    Ranking drives selection, so a simple draw can put too many of the very
    highest-risk customers in one arm.  We split the already-selected cohort
    into contiguous probability bands and randomise within each band.  This
    preserves random assignment while avoiding avoidable baseline imbalance.
    """
    ranked = sorted(customers, key=lambda c: (-float(c["churn_probability"]), c["user_id"]))
    rng = random.Random(seed)
    control: set[int] = set()
    for start in range(0, len(ranked), max(1, math.ceil(len(ranked) / strata))):
        band = ranked[start:start + max(1, math.ceil(len(ranked) / strata))]
        n_control = round(len(band) * fraction)
        control.update(rng.sample([c["user_id"] for c in band], n_control))
    return control


def log_actions(worklist: dict, path=ACTION_LOG_PATH, seed: int = 42,
                experiment_intervention: str | None = None) -> dict:
    """Record a randomised intervention experiment without changing the model.

    `experiment_intervention` makes every treated customer receive one named
    action.  This is essential: a mixed bundle can estimate the policy's net
    effect, but cannot measure the uplift of any individual intervention.
    """
    customers = worklist["customers"]
    control = assign_control_stratified(customers, seed=seed)
    entries = [{
        "user_id": c["user_id"],
        "as_of": worklist["analysis_time"],
        "group": "control" if c["user_id"] in control else "treated",
        "intervention": "none" if c["user_id"] in control else (
            experiment_intervention or c["intervention"]),
        "recommended_intervention": c["intervention"],
        "churn_probability": c["churn_probability"],
        "expected_value": c["expected_value"],
    } for c in customers]
    log = {"analysis_time": worklist["analysis_time"],
           "horizon_days": HORIZON_DAYS,
           "experiment": {
               "assignment": "stratified random 1:1 treatment/control by churn-risk band",
               "intervention": experiment_intervention,
               "target_per_arm": EXPERIMENT_TARGET_PER_ARM if experiment_intervention else None,
               "uplift_status": "measured after the horizon; not used in expected value automatically",
           },
           "entries": entries}
    with open(path, "w") as f:
        json.dump(log, f, indent=2)
    return log


def _wilson_interval(successes: int, total: int, z: float = Z_ALPHA) -> tuple[float, float]:
    """Confidence interval for a rate, sane at small n (unlike normal approx)."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    spread = z * ((p * (1 - p) / total + z**2 / (4 * total**2)) ** 0.5) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def _fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """p-value for the 2x2 table [[a, b], [c, d]] by Fisher's exact test.

    Exact, not asymptotic: a chi-square or normal approximation is invalid at
    the counts this loop actually produces (one churn in eleven customers).
    Two-sided in the conventional way - sum the probability of every table at
    least as extreme as the observed one, given the same margins.
    """
    row1, row2 = a + b, c + d
    col1, total = a + c, a + b + c + d
    if total == 0 or row1 == 0 or row2 == 0 or col1 == 0 or col1 == total:
        return 1.0

    def prob(x):
        return (math.comb(row1, x) * math.comb(row2, col1 - x)) / math.comb(total, col1)

    observed = prob(a)
    lo = max(0, col1 - row2)
    hi = min(row1, col1)
    # 1e-9 tolerance: floating point must not drop a table of equal probability
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1)
                        if prob(x) <= observed * (1 + 1e-9)))


def _newcombe_difference_ci(s1: int, n1: int, s2: int, n2: int,
                            z: float = Z_ALPHA) -> tuple[float, float]:
    """Confidence interval for the DIFFERENCE of two rates (Newcombe's method).

    This is the interval that answers the question. Comparing two separate
    per-arm intervals and asking whether they overlap is a different, wrong
    test: non-overlap implies significance, but overlap does NOT imply the
    absence of it, so the old check called real effects inconclusive.
    """
    if n1 == 0 or n2 == 0:
        return (-1.0, 1.0)
    p1, p2 = s1 / n1, s2 / n2
    l1, u1 = _wilson_interval(s1, n1, z)
    l2, u2 = _wilson_interval(s2, n2, z)
    diff = p1 - p2
    lower = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (max(-1.0, lower), min(1.0, upper))


def sample_size_per_arm(base_rate: float, relative_cut: float = 0.5,
                        alpha: float = 0.05, power: float = 0.80) -> dict:
    """Customers per arm needed to detect a `relative_cut` reduction in churn.

    The standard two-proportion formula, with both z terms spelled out:

        n = (z_alpha * sqrt(2 p_bar q_bar) + z_beta * sqrt(p1 q1 + p2 q2))^2
            / (p1 - p2)^2

    The previous version multiplied the summed variances by a flat 16, which
    is the shortcut for the AVERAGE variance - so it asked for roughly twice
    the customers actually needed, and named neither alpha nor power.
    """
    z_a, z_b = Z_ALPHA_BY_LEVEL.get(alpha), Z_POWER_BY_LEVEL.get(power)
    if z_a is None or z_b is None:
        raise ValueError(f"alpha must be one of {sorted(Z_ALPHA_BY_LEVEL)} and "
                         f"power one of {sorted(Z_POWER_BY_LEVEL)}")
    p1 = min(max(base_rate, 1e-6), 1.0)
    p2 = p1 * (1 - relative_cut)
    diff = p1 - p2
    if diff <= 0:
        return {"per_arm": 0, "assumptions": "no detectable difference requested"}
    p_bar = (p1 + p2) / 2
    n = ((z_a * math.sqrt(2 * p_bar * (1 - p_bar))
          + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / diff ** 2
    return {
        "per_arm": int(math.ceil(n)),
        "base_rate": round(p1, 4),
        "target_rate": round(p2, 4),
        "alpha": alpha,
        "power": power,
        "assumptions": (f"two-sided alpha={alpha}, power={power:.0%}, detecting a "
                        f"{relative_cut:.0%} cut from {p1:.1%} to {p2:.1%}"),
    }


def planning_base_rate(log: dict, control_churned: int, control_n: int) -> tuple[float, str]:
    """The churn rate to plan the next experiment around.

    An arm with no events gives a rate of 0, and a power calculation on 0 is
    meaningless. With too few events to trust, fall back to the model's own
    calibrated probabilities for these customers - which is the best estimate
    of their churn rate that exists before the experiment runs.
    """
    if control_churned >= MIN_EVENTS_FOR_PLANNING:
        return control_churned / control_n, "observed control churn rate"
    probs = [e["churn_probability"] for e in log.get("entries", [])
             if e.get("churn_probability") is not None]
    if probs:
        return sum(probs) / len(probs), "mean calibrated churn probability (too few control events)"
    return 0.01, "1% fallback (no data to plan from)"


def measure_uplift(log: dict, churned_ids: set) -> dict:
    """Compare what happened to the treated group and the control group.

    Reports the difference two ways, because "9%" means two different things:
      absolute_uplift_pp - percentage POINTS of churn avoided (9% -> 0% is 9 pp)
      relative_uplift    - the share of would-be churn removed (9% -> 0% is 100%)
    `actions.py` prices interventions with the RELATIVE meaning, so mixing the
    two silently inflates or deflates every rupee figure downstream.
    """
    groups = {"treated": [], "control": []}
    for e in log["entries"]:
        groups[e["group"]].append(e["user_id"] in churned_ids)

    result = {}
    for name, outcomes in groups.items():
        n = len(outcomes)
        churned = sum(outcomes)
        lo, hi = _wilson_interval(churned, n)
        result[name] = {"n": n, "churned": churned,
                        "churn_rate": churned / n if n else 0.0,
                        "ci": (round(lo, 3), round(hi, 3))}

    t, c = result["treated"], result["control"]
    difference = c["churn_rate"] - t["churn_rate"]        # churn avoided
    result["absolute_uplift_pp"] = round(difference * 100, 1)
    result["relative_uplift"] = (round(difference / c["churn_rate"], 3)
                                 if c["churn_rate"] > 0 else None)
    lo, hi = _newcombe_difference_ci(c["churned"], c["n"], t["churned"], t["n"])
    result["difference_ci_pp"] = (round(lo * 100, 1), round(hi * 100, 1))
    result["p_value"] = round(_fisher_exact_two_sided(
        c["churned"], c["n"] - c["churned"], t["churned"], t["n"] - t["churned"]), 4)
    result["conclusive"] = result["p_value"] < ALPHA
    rate, basis = planning_base_rate(log, c["churned"], c["n"])
    power = sample_size_per_arm(rate)
    # underpowered: the actual per-arm n is < 10% of what 80%-power requires.
    # This is not a binary pass/fail — it shows HOW far the experiment falls
    # short, so the power table can be read in context.
    actual_per_arm = min(t["n"], c["n"])
    required = power["per_arm"]
    result["power"] = {**power, "base_rate_from": basis,
                       "actual_per_arm": actual_per_arm}
    result["underpowered"] = (required > 0 and actual_per_arm < required * 0.10)
    experiment = log.get("experiment", {})
    treated_actions = {e.get("intervention") for e in log["entries"]
                       if e.get("group") == "treated"}
    one_intervention = len(treated_actions) == 1
    action = next(iter(treated_actions), None) if one_intervention else None
    result["measured_uplift"] = {
        "status": "measured" if one_intervention else "policy_bundle_only",
        "intervention": action,
        "scope": ("randomised net effect of the named intervention versus no action "
                  "within this model-selected cohort" if one_intervention else
                  "randomised net effect of a mixed intervention policy; not an intervention-specific uplift"),
        "relative_uplift": result["relative_uplift"],
        "absolute_uplift_pp": result["absolute_uplift_pp"],
        "conclusive": result["conclusive"],
        "ready_to_replace_assumption": bool(one_intervention and result["conclusive"]),
        "target_per_arm": experiment.get("target_per_arm"),
        "additional_per_arm_needed": max(0, (experiment.get("target_per_arm") or 0) - actual_per_arm),
    }
    return result


def horizon_passed(log: dict, now: str) -> bool:
    """Has enough time passed since the actions to see the outcome?"""
    end = datetime.fromisoformat(log["analysis_time"]) + timedelta(days=log["horizon_days"])
    return datetime.fromisoformat(now) >= end


def main():
    from .config import connect_readonly, reference_now
    from .eval import future_churners
    from .pipeline import build_worklist

    conn = connect_readonly()
    now = reference_now(conn)
    conn.close()

    # Deliberately separate from the 15-person operating worklist.  This is a
    # low-cost, single-treatment experiment with 300 treated and 300 control
    # customers; it measures an email nudge, not a heterogeneous policy.
    log = log_actions(build_worklist(top_n=EXPERIMENT_COHORT_SIZE),
                      experiment_intervention=EXPERIMENT_INTERVENTION)
    churned = future_churners(log["analysis_time"])
    ready = horizon_passed(log, now)

    print("=" * 70)
    print(f"INTERVENTION LOOP  (acted at {log['analysis_time']}, "
          f"{log['horizon_days']}-day horizon, now {now})")
    print("=" * 70)
    treated = sum(1 for e in log["entries"] if e["group"] == "treated")
    print(f"Logged {len(log['entries'])} customers: {treated} treated, "
          f"{len(log['entries']) - treated} held back as control")
    if not ready:
        print("Horizon has not passed yet - nothing to measure.")
        return

    result = measure_uplift(log, churned)
    for name in ("treated", "control"):
        g = result[name]
        print(f"  {name:<8} {g['churned']}/{g['n']} churned = {g['churn_rate']:.0%} "
              f"(95% CI {g['ci'][0]:.0%}-{g['ci'][1]:.0%})")
    print("-" * 70)
    lo, hi = result["difference_ci_pp"]
    relative = result["relative_uplift"]
    print(f"Churn avoided (absolute): {result['absolute_uplift_pp']:+.1f} percentage points "
          f"(95% CI {lo:+.1f} to {hi:+.1f} pp)")
    print(f"Churn avoided (relative): "
          + (f"{relative:+.0%} of would-be churn" if relative is not None
             else "undefined - no churn in the control arm to remove"))
    print(f"Fisher exact p = {result['p_value']:.3f}  ->  "
          + ("CONCLUSIVE at alpha=0.05" if result["conclusive"]
             else "INCONCLUSIVE: this result is what chance looks like at this sample size"))
    power = result["power"]
    print(f"To settle it: ~{power['per_arm']:,} customers per arm "
          f"({power['assumptions']}; base rate from {power['base_rate_from']})")
    print("In this simulator an intervention changes nothing about a customer's")
    print("future, so ~0 is the correct answer. The loop reports what happened.")
    print("=" * 70)


if __name__ == "__main__":
    main()
