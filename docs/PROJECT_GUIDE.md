# Customer Churn Early-Warning Agent — Project Guide

> **Who this is for:** a brand-new intern who just joined and needs to understand
> WHAT we are building, WHY it matters, and HOW to build it — step by step,
> with zero prior knowledge assumed.

---

## 1. WHAT are we building?

An AI system for a quick-commerce app (think **Blinkit / Zepto**) that:

1. **Predicts** which customers are about to quietly stop using the app (churn),
2. **Investigates** the risky ones to find *evidence* of why they're leaving,
3. **Proves** every claim against the database (no AI hallucinations),
4. **Recommends** a retention action (coupon / call / ignore) that a human approves,
5. **Measures** its own accuracy honestly — with real numbers, not vibes.

### The story in one picture

```
 A loyal customer...          ...goes quiet...        ...and is gone.
 ┌──────────────┐          ┌──────────────┐        ┌──────────────┐
 │ 12 orders    │          │ logins drop  │        │ now uses a   │
 │ 5-star revs  │  ──────► │ 100 → 10     │ ─────► │ rival app    │
 │ refers pals  │          │ no complaint │        │ forever      │
 └──────────────┘          └──────────────┘        └──────────────┘
                                  ▲
                                  │
                     OUR AGENT CATCHES THEM HERE,
                     while a coupon can still win them back.
```

**Churn** = a customer who used to use the platform quietly stops.
They never complain. They never say goodbye. **But the data changes before
they leave** — and that's what we detect.

---

## 2. WHY are we building it?

### Why the business cares
- App companies are valued on **active users**, not just profit
  (Zomato/Swiggy had huge valuations while losing money — because of user counts).
- Every silently-lost customer directly hurts valuation.
- Catching them **early** — while a coupon or a call can still win them back —
  is worth automating.

### Why this is an AI-agent problem (and not just a SQL script)
Honest answer: counting "who didn't log in for 14 days" IS just SQL.
The LLM earns its place for three things only:
1. **Reading unstructured text** — ticket descriptions and review texts
   ("packet was leaking" + 1-star + silence = a story a SQL query can't tell).
2. **Synthesizing weak signals** into one judged verdict with a written,
   evidence-based explanation per customer.
3. **Orchestrating** the investigation flexibly without hardcoding every path.

Know this answer cold — "why do you need an LLM at all?" is the #1
interview question for this project.

### Why it matters for the portfolio
This project proves **multi-agent orchestration + data science fusion** —
the skill top firms interview for in 2026. (RAG is proven by the HR Helpdesk
project; MCP at scale by the Hostel MCP project. Each project carries ONE flag.)

---

## 3. HOW does it work? (Architecture)

```
 ┌────────────────────────────────────────────────────────────────┐
 │                        WEEKLY RUN                              │
 │                                                                │
 │  STEP A: PREDICT (cheap, fast, all customers)                  │
 │     XGBoost model scores every customer's churn risk           │
 │     using features: login slope, days since last order,        │
 │     ticket count, avg rating, monthly spend.                   │
 │     SHAP values explain WHY each score is high.                │
 │                                                                │
 │  STEP B: INVESTIGATE (expensive, only top-N risky customers)   │
 │                   ┌─────────────────┐                          │
 │                   │   DEEP AGENT    │  plans to-dos, delegates,│
 │                   │  (the manager)  │  collects evidence       │
 │                   └───────┬─────────┘                          │
 │            ┌──────────────┼──────────────┐                     │
 │            ▼              ▼              ▼                     │
 │     ┌────────────┐ ┌────────────┐ ┌────────────┐               │
 │     │ Sub-agent 1│ │ Sub-agent 2│ │ Sub-agent 3│               │
 │     │  Activity  │ │  Negative  │ │  Bad or    │               │
 │     │  trend     │ │  tickets   │ │  missing   │               │
 │     │  (logins)  │ │            │ │  reviews   │               │
 │     └─────┬──────┘ └─────┬──────┘ └─────┬──────┘               │
 │           └───── all query SQLite (read-only) ────┘            │
 │                                                                │
 │  STEP C: VERIFY                                                │
 │     Evidence verifier re-checks every claim against the DB.    │
 │     A critic agent challenges each verdict ("vacation, not     │
 │     churn?") before anything reaches a human.                  │
 │                                                                │
 │  STEP D: REPORT + HUMAN APPROVAL                               │
 │     Per-customer verdict + evidence + suggested action.        │
 │     A human approves (HITL). Decisions are remembered so       │
 │     the same customer isn't re-flagged next week.              │
 │                                                                │
 │  STEP E: LEARN                                                 │
 │     Coupons are measured against a hold-out group →            │
 │     real uplift, not guesses. Model watches its own drift.     │
 └────────────────────────────────────────────────────────────────┘
```

### The golden rule of the design
**The deep agent never touches the database.** It only plans and delegates.
Each sub-agent has exactly ONE job. This design is OURS (from the instructor) —
the AI may write code, but it does not invent the architecture.

---

## 4. The data (there is no real company, so we fake one)

We can't get Blinkit's real database, so **Step 1 of the build is generating
synthetic data** with a simulator script (`quick_commerce_sim.py`):

- **6 tables:** `users`, `products`, `orders`, `auth_audit_log`,
  `support_tickets`, `reviews` (SQLite — one local file, zero setup).
- **120 days** of realistic history for **40 customers**
  (logins, orders, tickets, reviews, weekend spikes, failed logins).
- **The trick that makes the project work:** ~25% of customers are
  deliberately marked as churned — they stop producing activity 2–8 weeks
  before "today". **These planted churners are the answer key.**
  If our agent finds them (and doesn't falsely flag active users),
  we can compute REAL precision and recall.

> Why plant churners? If every customer stayed active, the agent would have
> nothing to find. And because WE planted them, we know the ground truth —
> which makes honest evaluation possible. Almost no student project has this.

---

## 5. HOW to build it — the Three Rings

Build in rings. **Each ring is a complete, working, committable milestone.**
Never start ring N+1 until ring N runs end-to-end.

### RING 1 — The Instructor's Core (the homework)

| Step | What you do | Definition of done |
|------|-------------|--------------------|
| 0 | Project setup: `uv init`, add `deepagents` + `langchain-google-genai`, `.env` (MODEL_NAME, PROJECT_ID), `.gitignore`, private git repo | `uv add` succeeds; `.env` NOT tracked by git |
| 1 | Get `quick_commerce_sim.py` (copy from instructor's repo — don't hand-type 704 lines of boilerplate), run `python quick_commerce_sim.py init` | `qcommerce.db` exists; summary shows ~10/40 customers dormant |
| 2 | Write deterministic tools with `@tool`: `get_inactive_users(days, top_n)`, `get_user_tickets(user_id)`, `get_user_reviews(user_id)` — fixed SQL, read-only connection | Each tool returns correct rows when called directly from Python |
| 3 | Build the three sub-agents (`create_agent`), each with one tool, one prompt, structured output (Pydantic) | Each sub-agent answers correctly when invoked alone |
| 4 | Build the deep agent (`create_deep_agent`): planning prompt, the 3 sub-agents, to-do list, final at-risk report | One command produces a churn report naming real dormant users |
| 5 | Verify manually: does the report match the DB's planted churners? | You can defend every name on the list with SQL |

### RING 2 — The 5/5 Layer (production credibility)

| Step | What you add | Why |
|------|--------------|-----|
| 6 | **Eval harness**: compare agent's flagged list vs the simulator's ground truth → precision & recall, saved to JSON | Turns "it seems to work" into "0.9 precision" |
| 7 | **XGBoost scoring tool**: train on features from the DB; agent calls it to pick top-N candidates BEFORE investigating | ML predicts cheaply; LLM investigates only the worthy — fixes cost & scale |
| 8 | **PII middleware**: redact phone/email before any LLM call; keep DB connection read-only | Safety story — "can be trusted near production data" |
| 9 | **Memory across runs**: store flagged/contacted customers; don't re-flag for 30 days | Systems thinking, not scripts |
| 10 | **Tracing + cost log** (LangSmith/Langfuse): know what each run costs | "What does a run cost?" — you'll have an answer |
| 11 | **MCP server** exposing the tools + **Dockerfile** + scheduled run | 2026 standards, right-sized deployment |

### RING 3 — The Elite Tier (what nobody else has)

| Step | What you add | The sentence it buys you |
|------|--------------|--------------------------|
| 12 | **SHAP explainability** feeding the agent's narrative | "The model flags her for login collapse; the agent confirms the unresolved refund ticket" |
| 13 | **Churn archetypes** in the simulator (cliff-dropper, gradual fader, vacationer, loyal bulk-buyer) + per-archetype recall | "I catch 95% of cliff-droppers but 60% of faders — here's why" |
| 14 | **Critic agent**: challenges each verdict before HITL; measure precision with vs without | "Multi-agent debate, with measured false-positive reduction" |
| 15 | **Drift check** (PSI/KS on features vs training distribution) | "My model knows when it's stale" |
| 16 | **Uplift loop**: simulator makes couponed customers return probabilistically; hold-out group; measure real retention uplift | "Measured ROI against a hold-out — L5 territory" |

---

## 6. What we deliberately DO NOT build (and why)

> This section goes in the final README too. Knowing what NOT to build
> is the judgment top firms actually pay for.

| Rejected | One-line reason |
|----------|-----------------|
| **A2A protocol** | Our agents live in one system; A2A is for cross-organization agent interop we don't have. MCP covers our interop. |
| **Kubernetes** | It's a weekly batch job over one SQLite file. Docker + a schedule is the *correct* deployment for this scale. |
| **Fine-tuning** | No data volume (40 synthetic customers) and no measured prompting failure to fix. Order is: prompt → tools → fine-tune. |
| **Fancy UI** | The product is decision quality — eval numbers and the report. Markdown + one Plotly chart is sufficient. |
| **Knowledge graph** | Relationships are one foreign-key hop deep; SQL answers everything exactly. Would reconsider if churn spread through referral networks. |
| **RAG** | Data is structured — retrieval is SQL, which is exact and free. No document corpus exists here. (RAG is proven in the HR Helpdesk project.) |

---

## 7. Tech stack

| Layer | Choice | Note |
|-------|--------|------|
| Language / tooling | Python 3.12 + `uv` | `uv init`, `uv add`, `uv run` |
| Agent harness | `deepagents` (LangChain/LangGraph) | planning, sub-agents, filesystem, memory built in |
| LLM | Gemini Flash via `langchain-google-genai` | model name + project ID from `.env` — swappable by config, never hardcoded |
| Database | SQLite (`qcommerce.db`) | one file, zero setup; only the connection string changes for Postgres/MySQL |
| ML | XGBoost + SHAP (Ring 2/3) | scikit-learn style, trained on simulator features |
| Safety | PII redaction middleware, read-only DB, injection hooks | before-LLM / before-tool |
| Evals | Custom precision/recall harness vs planted ground truth | the project's crown |
| Ops | LangSmith/Langfuse tracing, Docker, MCP server | Ring 2 |

---

## 8. Rules for the intern (how we work)

1. **Type the code yourself** (except the 704-line simulator — copy that).
   Typing builds understanding; pasting builds nothing.
2. **One step at a time.** Run it, read the output, understand it,
   THEN move to the next step.
3. **Every ring ends with a git commit** (and a tag: `ring-1`, `ring-2`, `ring-3`).
4. **Secrets live in `.env`, never in code, never in git.** Verify with `git status`.
5. **If a step fails, read the error before asking.** The error usually names
   the file and line. That's the job.
6. **The architecture is decided** (Section 3). LLMs may write code for you,
   but they don't get to change the design.

---

## 9. Glossary (plain words)

| Term | Meaning |
|------|---------|
| **Churn** | A customer quietly stops using the platform |
| **Deep agent** | An agent that plans a task, delegates to sub-agents, and reasons over their findings |
| **Sub-agent** | A smaller agent with exactly one job |
| **HITL** | Human-in-the-loop — a person approves before action is taken |
| **Synthetic data** | Realistic fake data we generate ourselves |
| **Ground truth** | The known correct answer (here: which customers we planted as churned) |
| **Precision** | Of everyone we flagged, how many were truly churning? |
| **Recall** | Of everyone truly churning, how many did we catch? |
| **Uplift** | Extra retention caused by our action, measured against a group we left alone |
| **SHAP** | A method that explains WHY an ML model gave a particular score |
| **Drift** | When live data stops looking like the data the model was trained on |
| **MCP** | Model Context Protocol — the 2026 standard for exposing tools to any AI client |
| **PII** | Personally identifiable information (phone, email) — never send it to an LLM |

---

*Reference: instructor's repo — https://github.com/GenAIDevelopment/customer_churn_alert_agent
(simulator from commit `4571d58`). The three-sub-agent design is from the
18 July Deep Agents class; context engineering ideas from the 21 June class.*
