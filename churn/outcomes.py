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
import random
from datetime import datetime, timedelta

from .config import ACTION_LOG_PATH, HORIZON_DAYS

CONTROL_FRACTION = 0.3          # held back, gets nothing, so uplift is measurable


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


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Confidence interval for a rate, sane at small n (unlike normal approx)."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    spread = z * ((p * (1 - p) / total + z**2 / (4 * total**2)) ** 0.5) / denom
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def measure_uplift(log: dict, churned_ids: set) -> dict:
    """Compare what happened to the treated group and the control group."""
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

    # uplift = churn we avoided = control churn rate - treated churn rate
    result["uplift"] = round(result["control"]["churn_rate"] - result["treated"]["churn_rate"], 3)
    # conclusive only if the two intervals do not overlap at all. With a
    # handful of customers per arm they almost always do - which is the
    # honest answer, not a defect.
    t_lo, t_hi = result["treated"]["ci"]
    c_lo, c_hi = result["control"]["ci"]
    result["conclusive"] = t_hi < c_lo or c_hi < t_lo
    result["needed_per_arm"] = _sample_size_hint(result["control"]["churn_rate"])
    return result


def _sample_size_hint(base_rate: float, detectable: float = 0.5) -> int:
    """Roughly how many customers per arm to detect a `detectable` relative cut
    in churn - the number that turns "inconclusive" into a plan."""
    p = max(base_rate, 0.01)
    q = p * (1 - detectable)
    diff = p - q
    if diff <= 0:
        return 0
    return int(round(16 * (p * (1 - p) + q * (1 - q)) / diff**2))


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
    verdict = ("outside the noise" if result["conclusive"]
               else f"INCONCLUSIVE - the intervals overlap. To detect a halving of "
                    f"churn you would need ~{result['needed_per_arm']} customers per arm")
    print(f"Measured uplift (churn avoided): {result['uplift']:+.0%}   {verdict}")
    print("In this simulator an intervention changes nothing about a customer's")
    print("future, so ~0 is the correct answer. The loop reports what happened.")
    print("=" * 70)


if __name__ == "__main__":
    main()
