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
- Cost tracking in `main.py` → ~₹5 per scan; input:output tokens ≈ 27:1.

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
- Recall at threshold 0.5: gradual-faders **61%**, cliff-droppers **42%**.
- Traps are the weak spot: vacationers **42%** and loyal buyers **36%** flagged, vs **15%** of regular customers — likely because few orders/reviews make their rate features noisy.
- Lesson: an in-sample number quietly looked great. The script now prints both columns so the gap can't hide again.

---

## STAGE 11 — Presentation (turning it into a job)

**What:**
- `README.md` → a full case study: architecture diagram, results table, per-archetype eval, engineering decisions, "considered and rejected" list, run instructions.
- Pushed to **GitHub** (public), with a green **CI badge**.
- `INTERVIEW_PREP.md` (git-ignored, personal) → Q1–Q9 + a 60-second pitch + numbers to memorise.

**Lesson:** *A brilliant project you can't present is worth less than a modest one you can. The last stage is being able to TALK about it.*

---

## The whole project in one line

> An **XGBoost model** ranks customers by *risk × value*; a **deep agent** with
> three sub-agents investigates the top slice and **verifies every fact against
> the database**; the output is a prioritised retention report — and **every
> claim is measured**, including the techniques that didn't work.

---

## What we deliberately did NOT build (and why)

RAG, knowledge graph, A2A protocol, Kubernetes, fine-tuning, fancy UI, a live
dashboard — each is real technology, just not the right fit for *this* problem.
**Knowing when to stop adding is part of the design.**
