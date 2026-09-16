"""
outcomes.py

WHAT : Closes the loop. Logs what we did to whom (holding back a random
       control group), then - once the horizon has passed - checks what
       actually happened and measures the uplift we really got.
WHY   : Everything upstream is a prediction. This is the only part that finds
       out whether acting on it helped. Without a hold-out you cannot: the
       customers you contact are the ones most likely to leave, so their
       churn rate looks terrible however well the coupon worked.
FLOW  : log_actions() writes an action log, assigning a share of the worklist
        to a control group that gets nothing -> later, measure_uplift() joins
        the log with what happened and reports both rates, the difference,
        and a confidence interval.
LOGIC: the control group is chosen by a seeded random draw, so it is
       reproducible and not "the ones we felt like skipping" - self-selected
       controls are how uplift measurements lie.
NOTE : in THIS simulator an intervention changes nothing about a customer's
       future, so an honest loop should measure an uplift of roughly zero.
       That is the point: the machinery reports what happened, including
       "nothing". Real uplift needs real interventions.
"""
import json
import math
import random
from datetime import datetime, timedelta

from .config import ACTION_LOG_PATH, HORIZON_DAYS

CONTROL_FRACTION = 0.3          # held back, gets nothing, so uplift is measurable
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


def log_actions(worklist: dict, path=ACTION_LOG_PATH, seed: int = 42) -> dict:
    """Record who we would act on, who is held back, and what we predicted."""
    customers = worklist["customers"]
    control = assign_control([c["user_id"] for c in customers], seed=seed)
    entries = [{
        "user_id": c["user_id"],
        "as_of": worklist["analysis_time"],
        "group": "control" if c["user_id"] in control else "treated",
        "intervention": "none" if c["user_id"] in control else c["intervention"],
        "churn_probability": c["churn_probability"],
        "expected_value": c["expected_value"],
    } for c in customers]
    log = {"analysis_time": worklist["analysis_time"],
           "horizon_days": HORIZON_DAYS, "entries": entries}
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
    result["power"] = {**sample_size_per_arm(rate), "base_rate_from": basis}
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

    log = log_actions(build_worklist())
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
