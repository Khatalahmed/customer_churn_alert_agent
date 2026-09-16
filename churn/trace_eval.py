"""
trace_eval.py

WHAT : Grades HOW an agent run happened, not just what it concluded. Reads
       the recorded tool-call trace plus the predictions, and checks rules a
       correct run must satisfy.
WHY   : Precision measures the verdicts. It cannot see that the agent skipped
       the review check for four customers, investigated someone who was never
       shortlisted, or looped on one tool until the budget ran out. Those bugs
       change behaviour long before they change a headline number - and on a
       later model or prompt they appear silently.
FLOW  : load trace + predictions -> apply each rule -> print pass/fail ->
        exit non-zero if any rule fails, so CI can gate on it.
LOGIC: every rule is a plain function of (calls, predictions), so the tests
       can feed it hand-built traces and prove each rule catches its own bug.
"""
import json
import sys

from .config import PREDICTIONS_PATH, TRACE_PATH

RANKER = "get_churn_candidates"
TICKETS = "get_user_tickets"
REVIEWS = "get_user_reviews"
KNOWN_TOOLS = {RANKER, TICKETS, REVIEWS}


def _ids_for(calls, tool) -> list[int]:
    return [c["args"]["user_id"] for c in calls
            if c["tool"] == tool and "user_id" in c.get("args", {})]


def check_trajectory(calls: list[dict], predictions: list[dict]) -> list[dict]:
    """Return one result per rule: {rule, passed, detail}."""
    investigated = {p["user_id"] for p in predictions}
    tools_used = [c["tool"] for c in calls]
    ticket_ids, review_ids = _ids_for(calls, TICKETS), _ids_for(calls, REVIEWS)
    results = []

    def rule(name, passed, detail=""):
        results.append({"rule": name, "passed": bool(passed), "detail": detail})

    rule("ranks before investigating",
         bool(tools_used) and tools_used[0] == RANKER,
         f"first tool was {tools_used[0] if tools_used else 'none'}")

    ranker_calls = tools_used.count(RANKER)
    rule("ranks exactly once", ranker_calls == 1, f"{ranker_calls} calls")

    missing_tickets = sorted(investigated - set(ticket_ids))
    rule("checked tickets for every customer", not missing_tickets,
         f"missing: {missing_tickets}" if missing_tickets else "")

    missing_reviews = sorted(investigated - set(review_ids))
    rule("checked reviews for every customer", not missing_reviews,
         f"missing: {missing_reviews}" if missing_reviews else "")

    strays = sorted((set(ticket_ids) | set(review_ids)) - investigated)
    rule("investigated nobody off the shortlist", not strays,
         f"stray user_ids: {strays}" if strays else "")

    repeats = sorted({uid for uid in ticket_ids + review_ids
                      if ticket_ids.count(uid) > 1 or review_ids.count(uid) > 1})
    rule("no customer investigated twice", not repeats,
         f"repeated: {repeats}" if repeats else "")

    unknown = sorted({t for t in tools_used if t not in KNOWN_TOOLS})
    rule("used only the tools it was given", not unknown,
         f"unexpected: {unknown}" if unknown else "")

    budget = 2 * len(investigated) + 3          # tickets + reviews per customer, plus slack
    rule("stayed within the call budget", len(calls) <= budget,
         f"{len(calls)} calls, budget {budget}")

    failed = [c for c in calls if not c.get("ok", True)]
    rule("no tool call errored", not failed, f"{len(failed)} failed calls")

    return results


def main():
    with open(TRACE_PATH) as f:
        calls = json.load(f)["calls"]
    with open(PREDICTIONS_PATH) as f:
        predictions = json.load(f)

    results = check_trajectory(calls, predictions)
    passed = sum(r["passed"] for r in results)

    print("=" * 70)
    print(f"TRAJECTORY EVAL  ({len(calls)} tool calls, {len(predictions)} customers)")
    print("=" * 70)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['rule']:<40} {r['detail']}")
    print("-" * 70)
    print(f"{passed}/{len(results)} rules passed")

    slowest = sorted(calls, key=lambda c: c.get("ms", 0), reverse=True)[:3]
    if slowest:
        print("slowest calls: " + ", ".join(
            f"{c['tool']}({c.get('args', {}).get('user_id', '')}) {c.get('ms', 0)}ms"
            for c in slowest))
    print("=" * 70)
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
