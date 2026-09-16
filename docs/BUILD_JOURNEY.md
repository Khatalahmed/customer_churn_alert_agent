# Build Journey — How This Project Was Built, Stage by Stage

> For a new intern. This walks through **every stage** of the project in the
> order we built it — what we did, why, and what we learned at each step.
> Read `PROJECT_GUIDE.md` first (the plan); this file is the *actual journey*.
>
> The golden rule the whole way: **build one small piece, run it, understand
> the result, then move to the next.** Never skip ahead.

---

## STAGE 0 — Project setup

**What:** Made the folder a real project.
- `uv init` → created the project. `uv add deepagents langchain-google-genai` → installed the agent framework + LLM adapter.
- `.env` → holds secrets (model name, API keys). `.gitignore` → keeps secrets and generated files out of git.

**Why:** A clean, reproducible project from day one. Secrets live in `.env`, never in code.

**Key file:** `utils.py` → `get_model()`, the single place the LLM is built. This lets us switch provider (Vertex AI / Groq / Gemini) by editing **one line in `.env`** — no code change.

**Lesson:** *Provider is config, not code.* We proved it later by switching Gemini → Groq → Vertex without touching the agent.

---

## STAGE 1 — Synthetic data (the simulator)

**What:** Built `quick_commerce_sim.py` — creates a fake but realistic SQLite database (users, orders, login audit log, support tickets, reviews) for a Blinkit/Zepto-style app.

**Why:** We have no real company data, so we make our own. The trick: some customers are **planted as churned** (they go silent) so we have a known answer key to test against.

**Then:** `explore_db.py` → we *looked at the data first* before building anything on it. This showed four kinds of "dormant" customer — proving one SQL rule isn't enough.

**Lesson:** *Never build on data you haven't looked at.*

---

## STAGE 2 — The tools

**What:** `tools.py` → three deterministic SQL tools (`get_inactive_users`, `get_user_tickets`, `get_user_reviews`), each wrapped with `@tool` so an agent can call them. All use a **read-only** database connection.

**Why:** Our questions are fixed, so hand-written SQL is fast, free, and safe. Read-only = the agent can look but never change data (least privilege).

**Then:** `test_tools.py` → tested each tool by hand *before* any agent used it.

**Lesson:** *Test a tool before an LLM calls it — so you know a wrong answer came from the LLM, not the SQL.*

---

## STAGE 3 — The agent (Ring 1 core)

**What:** The instructor's homework — one **deep agent** (manager) + three **sub-agents**, each with one job.
- `schemas.py` → Pydantic models for structured output.
- `prompts.py` → the instructions for each sub-agent + the supervisor.
- `main.py` → wires it together with `create_deep_agent`.

**Result:** The first run produced a churn report that correctly flagged real churners with evidence — and correctly ignored never-activated sign-ups.

**Lesson:** *Single responsibility per sub-agent. The deep agent never touches the database — it only plans and delegates.*

---

## STAGE 4 — Evaluation (does it actually work?)

**What:** Two measuring scripts.
- `eval.py` → compares the agent's flagged list to the answer key → **precision & recall**.
- `verifier.py` → independently re-queries the database to fact-check every number the agent cited → **evidence fidelity**.

**Result:** Precision/recall measured against ground truth; evidence fidelity ~100% (the agent doesn't make up facts).

**Lesson:** *"It looks like it works" is not proof. Numbers are proof. And you check hallucination with independent verification, not trust.*

---

## STAGE 5 — Machine learning (the DS + agent fusion)

**What:** We upgraded the simulator so churn is **caused by behaviour** (bad deliveries, unresolved tickets, low ratings), then:
- `features.py` → builds **leakage-safe** features (rates and averages, never raw counts).
- `train_model.py` → trains an **XGBoost** model, reports honest **~0.73 AUC**.
- `scoring.py` → `get_churn_candidates` tool: ranks customers by **priority = churn risk × value**.

**Then:** wired the ML into the agent — the ML ranks *everyone* cheaply, the agent investigates only the *top slice*.

**Lesson:** *Avoid data leakage. Recent-activity features give a fake 0.99 AUC because they ARE the label. An honest 0.73 beats a suspicious 0.99.*

> Later we found a deeper version of the same problem: even the 0.73 model was trained to recognise customers who had *already* left. See **Stage 12**.

---

## STAGE 6 — Explainability + lifecycle

**What:**
- `explain.py` → **SHAP** shows *why* the model flagged each customer. We used SHAP to **test features by measurement** — dropped `tenure_days` (overfit noise), kept `avg_order_value` (real signal).
- `report.py` → a business-ready **retention report** (markdown) with the SHAP reason next to the agent's evidence.
- `memory.py` + `mark_contacted.py` → the system **remembers** who was contacted and won't re-flag them for 30 days.

**Lesson:** *Explain the model, and close the loop — detect → act → remember → don't re-nag.*

---

## STAGE 7 — Elite tier (the rare stuff)

**What:**
- `critic.py` → a skeptical 4th reviewer. We **measured it and found it HURT** on our clean shortlist — kept as an honest negative result.
- `uplift.py` → coupon effect measured against a **hold-out control**. First reported as "+38% true causal uplift" — but the coupon effect is planted by the simulator, so that number was circular (and just one random draw: re-running on a later dataset gave +26%). **Corrected** to a method check: the hold-out estimate averages +31 pts, matching the planted +31, while a single test on 78 churners ranges +14 to +47 pts.
- `drift.py` → **PSI** drift detection: the model flags itself for retraining when the data shifts.
- Cost tracking in `main.py` → token usage per scan; input:output ≈ 30:1. (The rupee figure we first quoted was dropped later: prices belong in `.env`, not hard-coded, and ours were never verified.)

**Lesson:** *Measure every technique — including the ones that don't help. That honesty is the strongest signal.*

---

## STAGE 8 — Tests + CI

**What:** `tests/test_churn.py` → a **pytest** suite for the deterministic parts (no LLM). `.github/workflows/ci.yml` → **GitHub Actions** runs it on every push (regenerate data → train → test).

**Lesson:** *Tests + CI turn "a pile of scripts" into "an engineered project."*

---

## STAGE 9 — Folder restructure

**What:** Moved 25 flat files into a proper layout: `churn/` (source package), `tests/`, `scripts/`, `docs/`. Imports became package-relative; run commands became `python -m churn.<name>`.

**Lesson:** *A clean structure is standard and professional. Data artifacts stay git-ignored in the root.*

---

## STAGE 10 — Production polish (the "implement all" flow)

| # | Step | What we added | Why |
|---|------|---------------|-----|
| 1 | 🐳 **Docker** | `Dockerfile` bakes in data + model, runs with `docker run` (no API key needed for the demo) | "Here's how it deploys" |
| 2 | 🔒 **PII middleware** | `pii.py` — redacts email/phone from tool outputs before the LLM sees them | Defense-in-depth on top of data-minimisation |
| 3 | 📊 **LangSmith tracing** | 3 env vars → every LLM/sub-agent/tool call traced with latency + tokens | Full observability — *config, not code* |
| 4 | 🎭 **Churn archetypes** | Simulator plants typed churners (cliff-dropper, gradual-fader) + traps (vacationer, loyal buyer); `archetype_eval.py` measures per-type recall | The elite eval nobody has |
| 5 | ✅ **README + commit + push** | Updated the README to a case study, committed, pushed to GitHub | Make it presentable + public |

**Archetype findings (first version — in-sample, later corrected):**
- First run reported 88% / 91% recall and 15–20% trap false-alarms. That scored customers with the saved model, which had **trained on 75% of them**.

**Correction (out-of-fold):** `archetype_eval.py` switched to 5-fold cross-validation, so every customer is scored by a model that never saw them (mean over 10 fold seeds):
- Recall at threshold 0.5: gradual-faders **55%**, cliff-droppers **39%**.
- Traps are the weak spot: loyal buyers **45%** and vacationers **30%** flagged, vs **15%** of regular customers — likely because few orders/reviews make their rate features noisy.
- These are the final, reproducible numbers. Before the simulator's clock was frozen, trap rates moved by up to ~20 points between regenerations (e.g. vacationers 42% on one dataset, 24% on the next) — which is why the reference time is now fixed and stored in the database.
- Lesson: an in-sample number quietly looked great. The script now prints both columns so the gap can't hide again.

---

## STAGE 11 — Presentation (turning it into a job)

**What:**
- `README.md` → a full case study: architecture diagram, results table, per-archetype eval, engineering decisions, "considered and rejected" list, run instructions.
- Pushed to **GitHub** (public), with a green **CI badge**.
- `INTERVIEW_PREP.md` (git-ignored, personal) → Q1–Q9 + a 60-second pitch + numbers to memorise.

**Lesson:** *A brilliant project you can't present is worth less than a modest one you can. The last stage is being able to TALK about it.*

---

## STAGE 12 — From detecting churn to predicting it

**The problem we found:** the label marked customers who had *already* stopped ordering, and the features used their whole history — including the weeks after they left. So the model learned "does this look like someone who is already gone?" That's detection, not early warning.

**What:** Point-in-time snapshots.
- `features.py` → at a cutoff date T, only customers active in the 28 days before T, and only data from before T — even each ticket's status *as it was at T*.
- The label is now **"stops being active in the 14 days after T"**. Customers who had already churned by T are left out.
- `train_model.py` → trains on snapshots 70, 56 and 42 days back; tested on the snapshot 28 days back, whose labels start exactly where training's end. Cross-validation is grouped by customer.
- Scoring, the agent's tools, the verifier and eval all run "as of" the test cutoff, so the agent is graded on a future it couldn't see.
- Two new tests: deleting every row after the cutoff changes no feature; each churn event is labelled exactly once, always in the future.

**Result:**

| | Detecting past churn | Predicting the next 14 days |
|---|---|---|
| AUC | 0.73 | 0.71 out-of-time (0.63 ± 0.08 CV) |
| Churn rate | 26% | 7.3% |
| Precision@15 | ≈ 0.80 | 0.27 by probability, 0.20 for the risk × value shortlist |

Recency features stopped being leakage and became real signals — but cliff-droppers still give almost no warning, and traps are flagged twice as often as regular customers.

**The agent, re-measured at the new analysis time:** precision 0.20 (2 of 10 flagged), recall 0.12, evidence fidelity 100%. It downgraded 5 of 15 to LOW - 4 right, 1 a real churner it argued away. Of the 15 shortlisted, 3 churn within 14 days, 4 had already churned before the cutoff, and 8 never churn.

**Lesson:** *Ask what the label really means at prediction time. A model can be leakage-free feature-by-feature and still answer an easier question than the one you care about.*

---

## STAGE 13 - Baselines: does the model earn its place?

**What:** `baselines.py` scores the same held-out snapshot with the obvious alternatives - picking at random, "days since last order", "logins fell", and logistic regression - then repeats the whole comparison at every cutoff (walk-forward).

**Result on the last snapshot:** XGBoost AUC 0.71 vs logistic regression 0.64; but logistic regression wins precision@15 (0.33 vs 0.27). The "no orders in 14 days" flag picks 29 customers, gets 3 right (precision 0.10).

**Result across all three cutoffs:** mean precision@15 - XGBoost 0.16, login-drop rule 0.16, logistic regression 0.13, dormancy 0.09. Mean AUC - XGBoost 0.60, logistic regression 0.60.

**Honest conclusion:** on 38 training churn events the gradient boosting is level with a linear model and with a two-line rule; it only pulls ahead on the snapshot with the most training data.

**Lesson:** *Always measure the boring baseline. "We used XGBoost" is a choice, not a result - and on small data the simple model is often just as good.*

---

## STAGE 14 - A simulator that can be predicted, and a tuning round that mostly said "no"

**The problem:** with churn dates drawn at random, dissatisfaction decided *whether* a customer left but nothing decided *when*. The model ranked unhappy customers correctly, yet which fortnight they quit was a coin flip - precision@15 sat at the base rate.

**The fix (simulator):** during the day-by-day backfill a churn-prone customer now quits a few days after a **run of bad experiences** (cancelled orders, unresolved tickets, 1-2 star reviews), and gradual faders slow down as that frustration builds. Measured: 2.25 bad events in the fortnight before quitting vs 0.93 in a normal fortnight - cause before effect. Also scaled to 3,000 customers over 240 days (473 churners), after measuring that it helped.

**Result:** AUC 0.83 out-of-time (0.79 +/- 0.03 CV), precision@15 9.5x random, and the traps stopped being the weak spot - loyal bulk-buyers are now flagged *less* often than regular customers.

**The tuning round - what did NOT work, all measured over 10 cutoffs:**

| Tried | Result |
|---|---|
| risk x order value ranking (the original design!) | cost 40% of shortlist precision - order value carries no churn signal |
| recent-pain features | AUC 0.69 -> 0.67 |
| smoothed rates | AUC up, top-15 down |
| depth 5 | precision@15 halved (overfitting) |
| 28-day horizon | lift halved - the frustration signal fades after ~2 weeks |
| 365-day history | AUC up, top-15 lift 6.2x -> 4.0x |
| exposure counts | **kept**: AUC 0.69 -> 0.73, CV spread halved |
| 3,000 customers | **kept**: AUC 0.73 -> 0.76 |

**The ceiling:** a model handed the simulator's hidden variables reaches precision@15 of 0.21 against our 0.12 - so the top of the list is near its limit, because the quit is triggered by events that happen after the cutoff.

**Lesson:** *Measure the ranking you actually ship. The "risk x value" priority score sounded obviously right, shipped for weeks, and was quietly throwing away 40% of the shortlist's precision.*

---

## STAGE 15 - Six improvements, and the bugs they uncovered

A deliberate pass over the weakest parts, each one measured before and after.

**1. PR-AUC and calibration.** At a 1.4% churn rate ROC-AUC says 0.84 and calls XGBoost and logistic regression identical; PR-AUC says 0.069 against a 0.014 floor and separates them (0.087 vs 0.071). The raw scores were not probabilities either - class weighting pushed the top of the list to ~0.9 for a 1.4% event. Platt scaling: Brier 0.102 -> 0.0135, ranking untouched.

**2. Code decides, the LLM explains.** The agent's verdicts added nothing to precision (0.14 vs the shortlist's 0.13), and it was applying a fixed rule anyway. The rule moved to `rubric.py`; a live run then reproduced the LLM's verdicts customer for customer. `risk_level` was removed from the agent's output schema entirely, with a test to enforce it.

**3. A specific intervention, priced.** `actions.py` matches the fix to the complaint and computes expected value. The answer is uncomfortable and was kept: no paid intervention pays for itself on this shortlist - a coupon needs Rs 7,143 of margin at risk at 14% churn, and nobody has it. The plan downgrades to a Rs 5 email and reports the break-even that would justify the real fix.

**4. Trajectory evals.** `trace.py` records every tool call; `trace_eval.py` grades nine rules over it. The rules are unit-tested against hand-built broken traces (skipped review check, stray customer, tool loop), so CI covers them without an API key. A real run scores 9/9 with 31 calls for 15 customers.

**5. Scheduled scan and a service.** `pipeline.py` (score, price, write worklist, check drift, exit 2 on alert) and `api.py` (four endpoints, no LLM in the path). The first drift baseline compared today against all training snapshots pooled and flagged `total_orders` every day, because customers accumulate orders over time; the baseline is now the most recent snapshot.

**6. The learning loop.** `outcomes.py` holds back a seeded random 30% control so uplift is measurable, and reports -9%, INCONCLUSIVE, plus the number that would settle it: ~9,500 customers per arm. `retrain.py` backtests refreshing vs staying stale (PR-AUC 0.089 vs 0.072) and promotes accordingly.

**Two bugs this pass caught in its own work:**
- `promote()` first retrained on every snapshot INCLUDING the held-out test one and saved over `churn_model.pkl` - which would have turned every reported metric in-sample. Promotion now writes a separate production model flagged `evaluation_safe=False`, with a test asserting the evaluated model is never overwritten.
- After calibration, `archetype_eval` flagged nobody: it used "probability > 0.5", and calibrated scores for a 1.4% event never get close. It now flags the top 50 by risk, which is what the product does anyway.

**Lesson:** *Every improvement moved a number, and three of them moved it DOWN once measured honestly. The ones worth keeping were the ones that survived a comparison, not the ones that sounded good.*

## STAGE 16 - Verifying the sentence, not just the schema

The last honest gap in the README: `verifier.py` re-queried the six numbers the
agent fills into its Pydantic schema, but nothing checked the `reason` it wrote -
and the reason is the only part a human reads. Filling the schema correctly and
then writing "three refund tickets remain unresolved" about a customer who has
one are entirely compatible failures.

`prose_eval.py` splits each reason into clauses and extracts typed claims:
ticket counts and categories with their open/closed state, star ratings and
ranges, what a complaint actually SAYS (stale, leaking, wrong item), login
movements including the direction word, and absences ("there are no reviews").
Each claim is re-queried against the database.

**Why patterns and not a second LLM.** A model checking a model needs its own
verifier; the regress has to stop at something deterministic. The cost is
coverage - patterns only recognise claim types they were taught - so coverage is
reported next to fidelity, and a clause nothing recognises counts as UNCHECKED,
never as correct.

**Result on the live run:** 84 claims extracted from 15 reasons, all supported -
100% prose fidelity, 71% clause coverage. The uncovered portion is rubric
restatement ("Dissatisfaction: not established under the criteria"), which
contains no factual claim to check.

**Two things the build itself taught:**
- The first version read polarity per CLAUSE, so "the resolved refund ticket and
  open app-crash ticket do not qualify" was scored as an unresolved refund
  ticket - a false alarm on correct prose. Claims are now bound to their own
  comma-segment. A checker that cries wolf gets switched off.
- A checker that only ever passes is worthless. Eight corrupted reasons - one per
  claim type - are in the test suite, so the thing is proven able to fail.
- A fresh agent run then found a second false alarm: the agent writes "excluded"
  for a ticket that is OPEN but outside the rubric's serious categories, and the
  extractor read it as "closed". Both false alarms came from the checker, not the
  agent - which is the failure mode to expect, and the reason every flag gets
  read against the database before it is believed.

**Lesson:** *The structured half was the easy half. What nobody was checking was
the part everybody reads.*

---

## STAGE 17 - A review of ten items, and the three numbers that got better

An outside review listed ten things to fix, in priority order. Working
through them changed four published numbers, and three of those changes made
the project look BETTER - which is exactly why they needed checking rather
than celebrating.

**The statistics (items 1-3).** "Uplift" named two different quantities: the
loop reported control minus treated as a percentage, while actions.py used
"uplift" for the relative share of churners an intervention rescues, and
priced everything with it. Now absolute_uplift_pp and relative_uplift, with
the units in the names. "Conclusive" meant two per-arm intervals failing to
overlap, which is not a test - overlap does not imply the absence of an
effect, and 10/50 vs 2/50 (Fisher p = 0.028) was being called noise. Now
Fisher's exact test, with Newcombe's interval on the difference.

The sample-size hint multiplied summed variances by a flat 16 - the shortcut
for AVERAGE variance - and named neither alpha nor power, so it asked for
about twice what was needed. It also planned around a base rate of zero,
floored at 1%, and demanded ~9,520 per arm. A retention experiment runs on
the SHORTLIST, whose calibrated risk is 13.8%, not on the whole base at 1.4%.
The answer is ~306 per arm, and "we cannot measure this" becomes "run it for
a few weeks".

**Two PR-AUCs for one model (item 4).** train_model said 0.069, baselines
said 0.087, both labelled "XGBoost (this project)". The cause was a false
claim in calibrate()'s own docstring: "Monotonic, so the ranking is
unchanged." CalibratedClassifierCV with cv=folds averages a per-fold
ensemble, so it reorders - rank correlation 0.984, precision@15 unchanged,
PR-AUC down a fifth. The rank-preserving alternative was measured rather than
argued about: exactly monotonic, but it spends 20% of the training customers
and halves precision@15. The ensemble stays; baselines now scores what ships.

**One window (item 5).** The model compared the last 14 days with the 14
before; every module explaining the model compared 30 with 30. The evidence
query also used SQL BETWEEN, so a login on the boundary was counted twice.
Unifying them changed the output: with 30/60 windows the disengagement signal
fired on 0 of 15 shortlisted customers, which is the real reason every
earlier run reported "no HIGH verdicts at all". Over a fortnight it fires on
4 of 15.

And measuring it produced the most uncomfortable finding of the pass: the
disengagement signal does not predict churn AT ALL. Customers whose logins
fell churn at 0.91% against a 1.41% base rate - lift 0.64x, worse than
random, the same answer the login-drop baseline gave. It stays as triage,
because it decides what to DO with someone the model already picked, and
rubric.py now says so in its own docstring.

**Money, monitoring, definitions (items 6-9).** A save is now the present
value of a decaying, discounted margin stream instead of a flat six months,
and every recommendation carries a sensitivity band - 14 of 15 still pay at
half the assumed uplift, the coupon never does. Drift watches three ways
(PSI, KS, and the score distribution), and turning KS on immediately paged
three times on nothing: at n~2,500 its 5% critical value is 0.038, so a
cohort ageing by two orders is "significant". KS now has to clear a practical
floor too. "Active" and "churned" moved out of a SQL clause into labels.py
with the measurement attached: the label is reproducible from raw events, but
it needs ~3 months of follow-up (94% precision) and is worthless at 14 days
(11%), because a quiet customer and a departed one look identical until they
have had time to come back. critic.py is labelled an experiment, with an AST
test keeping it out of every live module.

**Lesson:** *Three of the four corrected numbers moved in the flattering
direction - a smaller experiment, a higher coverage, a cheaper answer. A
reviewer who only checks the numbers that look bad audits half the work.*

---

---

## The whole project in one line

> An **XGBoost model** ranks customers by *churn risk*; a **deep agent** with
> three sub-agents investigates the top slice and **verifies every fact against
> the database**; the output is a prioritised retention report — and **every
> claim is measured**, including the techniques that didn't work.

---

## What we deliberately did NOT build (and why)

RAG, knowledge graph, A2A protocol, Kubernetes, fine-tuning, fancy UI, a live
dashboard — each is real technology, just not the right fit for *this* problem.
**Knowing when to stop adding is part of the design.**
