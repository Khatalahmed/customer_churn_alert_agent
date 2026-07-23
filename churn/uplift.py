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
NOTE : in production you target the MODEL's flagged customers; here we
       simulate on the known churners to demonstrate the measurement method.
"""
import json
import random

random.seed(7)

with open("churn_truth.json") as f:
    truth = json.load(f)

churned = [r for r in truth if r["churned"]]


def winnability(r) -> float:
    """Coupon lift for one customer, based on WHY they churned.

    Fixable pain (support / delivery) -> a targeted coupon + fix wins them
    back. Product pickiness -> harder to win back with a coupon.
    """
    lift = (0.35 * r.get("support_pain", 0.5)
            + 0.25 * r.get("delivery_pain", 0.5)
            - 0.20 * r.get("pickiness", 0.5))
    return max(0.0, min(0.6, lift))


BASE_RETURN = 0.08   # chance a churned customer drifts back on their own

# split the churned customers into treatment (coupon) and control (hold-out)
random.shuffle(churned)
cut = int(len(churned) * 0.7)
treatment, control = churned[:cut], churned[cut:]


def simulate(group, give_coupon: bool) -> int:
    """Simulate how many customers in the group return."""
    returned = 0
    for r in group:
        prob = BASE_RETURN + (winnability(r) if give_coupon else 0.0)
        if random.random() < prob:
            returned += 1
    return returned


t_ret = simulate(treatment, give_coupon=True)
c_ret = simulate(control, give_coupon=False)
t_rate = t_ret / len(treatment)
c_rate = c_ret / len(control)
uplift = t_rate - c_rate

print("=" * 62)
print("RETENTION UPLIFT  (coupon treatment vs hold-out control)")
print("=" * 62)
print(f"Treatment (coupon):    {t_ret:>2}/{len(treatment)} returned = {t_rate:5.0%}")
print(f"Control   (hold-out):  {c_ret:>2}/{len(control)} returned = {c_rate:5.0%}")
print("-" * 62)
print(f"UPLIFT = {uplift:+.0%}   (extra returns CAUSED by the coupon)")
print(f"Without a hold-out you'd have wrongly claimed {t_rate:.0%} success.")
print("=" * 62)