"""
uplift.py

WHAT : Measures whether retention coupons actually WORK, using a hold-out
       group (a mini A/B test). Some churned customers get a coupon
       (treatment), some do not (control). We simulate who returns and
       measure the UPLIFT = the extra returns caused by the coupon.
WHY  : Coupons cost money. We must prove they CAUSE customers to return,
       beyond those who would have returned anyway. A hold-out group is the
       only honest way to measure this.
FLOW : take the churned customers -> split into treatment (coupon) and
       control (hold-out) -> simulate returns using each customer's hidden
       "winnability" -> compare return rates.
LOGIC: uplift = return_rate(treatment) - return_rate(control). Only the
       "persuadable" customers create uplift. A coupon to a lost cause or a
       sure-thing is wasted money. Winnability is higher for customers who
       left over FIXABLE issues (support/delivery) than the just-unhappy.
NOTE : this is a METHOD CHECK, not evidence that coupons work. The coupon
       effect is planted by winnability() below, so the "true" uplift is
       known by construction. What we measure is whether a hold-out test
       recovers that planted effect, and how noisy a single test is. In
       production you would target the MODEL's flagged customers and the
       effect would be unknown - that is when the hold-out matters.
"""
import json
import random
import statistics

from .config import TRUTH_PATH

BASE_RETURN = 0.08   # chance a churned customer drifts back on their own


def winnability(r) -> float:
    """Coupon lift for one customer, based on WHY they churned.

    Fixable pain (support / delivery) -> a targeted coupon + fix wins them
    back. Product pickiness -> harder to win back with a coupon.
    """
    lift = (0.35 * r.get("support_pain", 0.5)
            + 0.25 * r.get("delivery_pain", 0.5)
            - 0.20 * r.get("pickiness", 0.5))
    return max(0.0, min(0.6, lift))


def simulate(group, give_coupon: bool, rng: random.Random) -> int:
    """Simulate how many customers in the group return."""
    returned = 0
    for r in group:
        prob = BASE_RETURN + (winnability(r) if give_coupon else 0.0)
        if rng.random() < prob:
            returned += 1
    return returned


def run_uplift(truth: list[dict], seed: int = 7) -> dict:
    """Split the churned customers 70/30 and simulate treatment vs control."""
    rng = random.Random(seed)
    churned = [r for r in truth if r["churned"]]

    # split the churned customers into treatment (coupon) and control (hold-out)
    rng.shuffle(churned)
    cut = int(len(churned) * 0.7)
    treatment, control = churned[:cut], churned[cut:]

    t_ret = simulate(treatment, give_coupon=True, rng=rng)
    c_ret = simulate(control, give_coupon=False, rng=rng)
    t_rate = t_ret / len(treatment)
    c_rate = c_ret / len(control)
    return {
        "t_ret": t_ret, "t_n": len(treatment), "t_rate": t_rate,
        "c_ret": c_ret, "c_n": len(control), "c_rate": c_rate,
        "uplift": t_rate - c_rate,
    }


def planted_effect(truth: list[dict]) -> float:
    """The true average uplift, known because we planted it (mean winnability)."""
    return statistics.mean(winnability(r) for r in truth if r["churned"])


def uplift_spread(truth: list[dict], n_runs: int = 1000) -> dict:
    """Repeat the test with different random splits: how much does one test vary?"""
    estimates = sorted(run_uplift(truth, seed=s)["uplift"] for s in range(n_runs))
    return {
        "mean": statistics.mean(estimates),
        "low": estimates[int(n_runs * 0.025)],     # 95% of single tests land
        "high": estimates[int(n_runs * 0.975)],    # between low and high
    }


def main():
    with open(TRUTH_PATH) as f:
        truth = json.load(f)
    u = run_uplift(truth)
    true_effect = planted_effect(truth)
    spread = uplift_spread(truth)

    print("=" * 66)
    print("RETENTION UPLIFT - METHOD CHECK  (coupon vs hold-out, simulated)")
    print("=" * 66)
    print("One test:")
    print(f"  Treatment (coupon):    {u['t_ret']:>2}/{u['t_n']} returned = {u['t_rate']:5.0%}")
    print(f"  Control   (hold-out):  {u['c_ret']:>2}/{u['c_n']} returned = {u['c_rate']:5.0%}")
    print(f"  Estimated uplift:      {u['uplift']:+.0%}")
    print(f"  (without a hold-out you'd have claimed {u['t_rate']:.0%} success)")
    print("-" * 66)
    print("Does the method work?")
    print(f"  Planted true effect:   {true_effect:+.0%}   (set by winnability(), known)")
    print(f"  Mean over 1000 tests:  {spread['mean']:+.0%}   (unbiased if close to planted)")
    print(f"  95% of single tests:   {spread['low']:+.0%} to {spread['high']:+.0%}   "
          f"(n={u['t_n'] + u['c_n']} is small)")
    print("=" * 66)
    print("NOTE: the coupon effect is simulated. This validates the hold-out")
    print("      measurement, not whether real coupons win customers back.")


if __name__ == "__main__":
    main()
