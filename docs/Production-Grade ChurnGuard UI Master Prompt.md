# ROLE

You are a senior product designer + staff frontend engineer specializing in production-grade B2B SaaS applications, data-heavy dashboards, AI agent interfaces, and developer tools.

You are working on an existing project:

**Repository:** `Khatalahmed/customer_churn_alert_agent`

The backend/ML/agent architecture already exists. Your job is to build a **premium, production-quality frontend UI** around the existing system.

The result must look like a real SaaS product that could be shown to:

* Senior software engineers
* AI/ML engineers
* Product engineers
* Hiring managers
* Technical founders
* Enterprise customers

It must NOT look like a generic portfolio dashboard, Streamlit prototype, AI toy, or template dump.

---

# 1. FIRST: UNDERSTAND THE EXISTING PROJECT

Before writing frontend code:

1. Inspect the entire repository.
2. Understand:

   * FastAPI endpoints
   * ML prediction pipeline
   * XGBoost model
   * calibration
   * churn scoring
   * deterministic risk rubric
   * LangGraph/deep-agent architecture
   * risk-ranker
   * ticket analyst
   * review analyst
   * evidence verifier
   * economic/action planner
   * outcomes measurement
   * database schema
   * existing API responses
   * existing scripts
   * existing tests
3. Identify what data is already available through APIs.
4. Do NOT invent backend functionality that does not exist.
5. Reuse existing APIs wherever possible.
6. If an API is missing for a useful UI feature, clearly identify the gap before implementing a workaround.
7. Do not modify ML logic, agent logic, evaluation methodology, or business logic merely to make the frontend easier.

The frontend must adapt to the existing backend, not the other way around.

---

# 2. PRODUCT VISION

Turn the project into a product called:

**ChurnGuard**

Subtitle:

**Customer Churn Early-Warning & Retention Intelligence**

Core product promise:

> Identify customers likely to churn, understand why, verify the evidence, and recommend economically justified interventions.

The UI should communicate four things in this order:

**Decision → Evidence → Economics → AI reasoning**

Do NOT make the product feel like:

> "Here is an AI chatbot."

The product is an operational decision system powered by ML + agents.

---

# 3. DESIGN DIRECTION

Use the visual quality bar of modern premium B2B products such as:

* Linear
* Stripe
* Vercel
* Notion
* Datadog
* modern enterprise analytics products

Do NOT copy any product's exact design.

The aesthetic should be:

* Minimal
* Premium
* Technical
* Calm
* Dense but readable
* Data-first
* Professional
* High information density
* Excellent typography
* Strong visual hierarchy
* Subtle animations
* Extremely consistent spacing

Avoid:

* Huge gradients
* Excessive glassmorphism
* Neon AI aesthetics
* Excessive rounded cards
* Giant hero sections
* Cartoonish illustrations
* Generic dashboard templates
* Excessive shadows
* Unnecessary animations
* Fake AI effects

The UI should feel like **serious enterprise software**.

---

# 4. TECHNOLOGY

Use the project's existing frontend stack if one already exists.

If a frontend does not exist, use:

* Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui
* Lucide icons
* Recharts or an appropriate charting library
* TanStack Query for API state if useful

Use strong TypeScript typing.

Avoid unnecessary dependencies.

Create reusable components rather than duplicating UI.

---

# 5. DESIGN SYSTEM

Create a consistent design system before building pages.

## Typography

Prefer:

* Geist / Inter

Hierarchy:

* Page title
* Section title
* Metric
* Body
* Secondary metadata
* Caption

Typography must be clean and restrained.

## Spacing

Use a consistent 4/8px spacing system.

Avoid random margins.

## Radius

Use approximately:

* 8px for controls
* 10–12px for cards
* slightly larger radius only where justified

## Borders

Prefer subtle borders over heavy shadows.

## Colors

Use semantic colors intentionally.

Risk:

* HIGH → red
* MEDIUM → amber
* LOW → green

Do not color every element.

Use risk colors only where they carry meaning.

Financial values should remain visually distinct from risk indicators.

---

# 6. APPLICATION STRUCTURE

Build this navigation:

```text
ChurnGuard
│
├── Overview
│
├── Worklist
│
├── Customers
│
├── Investigations
│
├── Analytics
│
└── Evaluations
```

Sidebar should be compact and professional.

Top bar should contain:

* Global search
* Command palette shortcut
* Current system status
* User/profile area if authentication exists

---

# 7. OVERVIEW DASHBOARD

Create `/dashboard`.

The dashboard should answer:

> "What requires my attention right now?"

Top-level metrics:

* Customers analyzed
* High risk
* Medium risk
* Margin at risk
* Recommended actions
* Intervention cost
* Expected value

Use real backend data.

Do NOT use fake hardcoded metrics unless clearly marked as demo data.

---

## Dashboard layout

### Section 1 — Executive metrics

Premium metric cards:

```text
Customers analyzed
2,487

High risk
4

Medium risk
10

Margin at risk
₹X,XXX

Recommended actions
15
```

Include contextual secondary information where available.

---

### Section 2 — Risk overview

Show:

* Risk distribution
* Churn probability distribution if available
* Recent churn trend if available

Charts must be simple and readable.

Do not create charts merely for decoration.

---

### Section 3 — Priority worklist

Display the highest-priority customers.

Columns:

* Customer
* Risk
* Churn probability
* Primary reason
* Recommended action
* Expected value
* Verification status

Example:

```text
C1024
HIGH
18.2%
2 unresolved tickets
Resolve ticket + call
₹420
✓ Verified
```

Clicking the row should open Customer 360.

---

# 8. WORKLIST

This is the CORE PRODUCT SCREEN.

Create `/worklist`.

The purpose is operational action.

Users should immediately understand:

**Who → Why → What → Is it worth it?**

Table columns:

```text
Customer
Risk
P(churn)
Primary signal
Evidence
Recommended action
Expected value
Status
```

Add filters:

```text
All
High risk
Medium risk
Low risk
Positive expected value
Needs investigation
Verified
```

Add sorting:

* Highest churn probability
* Highest expected value
* Highest margin at risk
* Risk level
* Customer value

Add search.

Make the table feel like a professional enterprise work queue.

Use sticky table headers if appropriate.

---

# 9. CUSTOMER 360

Create:

`/customers/[id]`

This should be one of the strongest screens in the application.

Header:

```text
Customer C1024

HIGH RISK

18.2%
Churn probability
```

Show:

* Customer ID
* Customer status
* Churn probability
* Risk level
* Margin at risk
* Recommended intervention
* Expected value

---

## Customer timeline

Create a visually excellent customer trajectory.

Show, where data exists:

* Orders
* Login activity
* Reviews
* Support tickets
* Complaints
* Satisfaction changes

Use meaningful charts.

Avoid chart overload.

---

## ML explanation

Create a section:

### Why the model is concerned

Show the top contributing features.

Example:

```text
Login frequency
↓ 42%

Unresolved tickets
2

Recent review rating
3.1

Recent orders
↓ 35%
```

If SHAP values exist, visualize them appropriately.

Clearly distinguish:

**Model signal**

from

**Agent evidence**

Do not imply SHAP proves causality.

---

# 10. EVIDENCE SECTION

Create:

### Evidence supporting the assessment

Use cards/timeline entries for:

### Support

```text
2 unresolved tickets

Refund issue
Created 4 days ago

✓ Verified against database
```

### Reviews

```text
Average rating declined

4.3 → 3.1

✓ Verified
```

### Engagement

```text
Recent login activity declined

✓ Verified
```

Every evidence item should visually indicate whether it was verified.

---

# 11. RECOMMENDATION CARD

Create a prominent but restrained recommendation component.

Example:

```text
RECOMMENDED ACTION

Resolve open ticket + call

Expected value
₹420

Intervention cost
₹250

Break-even probability
10.8%

✓ Economically justified
```

If the intervention was downgraded:

```text
Original recommendation
Resolve ticket + call

Selected action
Automated email

Reason
Paid intervention did not meet expected-value threshold.
```

Make this extremely clear.

Do not hide economic assumptions.

---

# 12. AGENT INVESTIGATION

Create:

`/investigations/[id]`

This page should expose the multi-agent architecture.

Show:

```text
Investigation

✓ Risk Ranker
  Customer trajectory analyzed

✓ Ticket Analyst
  2 unresolved tickets found

✓ Review Analyst
  Satisfaction decline detected

✓ Evidence Verifier
  All cited facts verified
```

Represent this as a clean investigation timeline.

Avoid flashy "AI thinking" animations.

The UI should communicate **controlled orchestration**, not pretend to expose hidden chain-of-thought.

Show only observable tool/action summaries and verified outputs.

---

# 13. AGENT TRACE

Provide an expandable trace.

Example:

```text
Risk Ranker
├── Retrieved customer risk profile
├── Checked ranking
└── Returned candidate

Ticket Analyst
├── Queried support tickets
├── Found 2 unresolved
└── Classified evidence

Review Analyst
├── Queried reviews
└── Detected rating decline

Verifier
├── Checked 17 facts
└── 17 / 17 verified
```

Use accordions/drawers.

Do not expose hidden reasoning or chain-of-thought.

Expose:

* Tool name
* Action
* Result
* Duration if available
* Verification status
* Error state

---

# 14. EVALUATIONS PAGE

Create:

`/evaluations`

This page is extremely important for the project's technical credibility.

Show model metrics:

```text
PR-AUC
0.069

Random baseline
0.014

ROC-AUC
0.839

Precision @ 15
13%

Recall @ 50
17%

Recall @ 100
29%

Brier score
0.0135
```

Display baseline comparisons visually.

Include:

* Random baseline
* Rules
* Logistic regression
* XGBoost raw
* XGBoost calibrated

Make it obvious that calibration improves probability quality while ranking behavior can differ.

---

# 15. AGENT RELIABILITY

Create a separate section:

### Agent reliability

Metrics:

```text
Evidence fidelity
100%

Prose fidelity
100%

Trajectory checks
9 / 9

Unexpected tool calls
0

Budget compliance
✓
```

Make this look like an engineering observability interface.

---

# 16. OUTCOME MEASUREMENT

Show the intervention outcome experiment.

Include:

* Treated customers
* Control customers
* Churn rate
* Absolute uplift
* Relative uplift
* Confidence interval
* Fisher exact p-value
* Conclusive / inconclusive status
* Required sample size

Clearly distinguish:

**Observed result**

from

**Statistical conclusion**

For example:

```text
Observed uplift

−9.1 pp

Statistical result

Inconclusive

Fisher exact p
1.00
```

Do not visually imply statistical significance when it does not exist.

---

# 17. ECONOMIC ANALYTICS

Create:

`/analytics`

Show:

### Intervention economics

Compare:

```text
Intervention
Cost
Expected uplift
Expected value
Break-even probability
Break-even margin
Robustness
```

Visualize expected-value sensitivity where useful.

Show uncertainty bands.

Make assumptions accessible:

```text
Margin rate
25%

Monthly survival
93%

Monthly discount
1%

Value horizon
12 months

Uplift uncertainty
±50%
```

Include an "Assumptions" drawer rather than hiding these numbers.

Clearly label the current rupee values as **illustrative assumptions**, not measured business outcomes.

---

# 18. CUSTOMER SEARCH

Implement global search / command palette.

Shortcut:

```text
⌘K
```

Windows:

```text
Ctrl+K
```

Allow:

```text
Search customers
Go to worklist
View high-risk customers
Open evaluations
Open analytics
```

If customer search API exists, support customer lookup.

---

# 19. STATES

Every major component must support:

### Loading

Use skeleton loaders.

### Empty

Example:

```text
No customers require attention.

Your current worklist is clear.
```

### Error

Show useful recovery messages.

### No results

When filters return nothing:

```text
No customers match these filters.
```

### Partial data

Never crash because optional data is missing.

---

# 20. RESPONSIVENESS

Desktop is the primary target because this is an operational SaaS application.

Still support:

* Laptop
* Tablet
* Mobile

On mobile:

* Sidebar becomes drawer
* Tables become cards or horizontally scrollable
* Charts remain readable
* Critical metrics remain visible

Do not simply shrink desktop UI.

---

# 21. ACCESSIBILITY

Follow strong accessibility practices:

* Keyboard navigation
* Visible focus states
* Semantic HTML
* ARIA labels where appropriate
* Good contrast
* Do not rely only on color to communicate risk
* Accessible tables
* Accessible dialogs
* Screen-reader-friendly controls

---

# 22. MICRO-INTERACTIONS

Use subtle interactions:

* Row hover
* Smooth drawer opening
* Tooltip
* Skeleton transitions
* Filter transitions
* Chart hover
* Copy-to-clipboard feedback
* Success verification animation

Avoid:

* Excessive motion
* Bouncing
* Spinning AI brains
* Fake "thinking" animations
* Distracting gradients

The product should feel fast.

---

# 23. DATA INTEGRITY

This is critical.

Never fabricate data.

Do not create fake:

* Churn probabilities
* Customer names
* Ticket counts
* Agent outputs
* Economic values
* Evaluation metrics

If the backend doesn't provide something:

1. Determine whether an existing endpoint can support it.
2. If not, show an appropriate unavailable state.
3. Do not silently invent data.

The UI must faithfully represent backend truth.

---

# 24. SECURITY

Never expose:

* API keys
* Azure credentials
* Environment variables
* Secrets
* Database credentials

Never put server secrets into client-side code.

Use server-side API routes/proxying where appropriate.

---

# 25. PERFORMANCE

Optimize for a fast dashboard.

Use:

* Server components where appropriate
* React Query/TanStack Query where useful
* Lazy loading for heavy charts
* Pagination
* Memoization where justified
* Avoid unnecessary API calls
* Avoid rendering huge tables at once

Do not prematurely optimize everything.

Prioritize perceived performance.

---

# 26. CODE QUALITY

Use:

* TypeScript strict mode
* Reusable components
* Clear component naming
* Feature-based organization
* Typed API clients
* Centralized API handling
* Error boundaries where useful

Suggested structure:

```text
frontend/
├── app/
│   ├── dashboard/
│   ├── worklist/
│   ├── customers/
│   ├── investigations/
│   ├── analytics/
│   └── evaluations/
│
├── components/
│   ├── layout/
│   ├── dashboard/
│   ├── worklist/
│   ├── customer/
│   ├── investigation/
│   ├── analytics/
│   ├── evaluation/
│   └── ui/
│
├── lib/
│   ├── api/
│   ├── formatting/
│   └── utils/
│
└── types/
```

Adapt this to the actual repository structure.

---

# 27. FORMATTING

Use professional formatting.

Examples:

```text
₹4,200
18.2%
13%
0.839
4.9×
9 / 9
17 / 17
```

Do not display raw floating-point garbage such as:

```text
0.182384728
```

Use meaningful precision.

---

# 28. VISUAL HIERARCHY

Every screen should answer:

### Level 1

What is happening?

### Level 2

Who needs attention?

### Level 3

Why?

### Level 4

What should we do?

### Level 5

Is it economically justified?

### Level 6

Can I trust the evidence?

This hierarchy is more important than decorative design.

---

# 29. DEMO EXPERIENCE

The application should be optimized for a 3–5 minute recruiter demo.

Ideal flow:

```text
Dashboard
   ↓
Open high-risk customer
   ↓
See churn probability
   ↓
See ML signals
   ↓
See verified evidence
   ↓
See agent investigation
   ↓
See recommended intervention
   ↓
See expected value
   ↓
Open Evaluation
   ↓
Show model + agent reliability
```

A recruiter should understand the entire project without reading the source code.

---

# 30. LANDING / PRODUCT IDENTITY

If the application has a login/landing screen, keep it minimal.

Example:

```text
ChurnGuard

Customer churn intelligence
for teams that want to act
before customers leave.

[ Open dashboard ]
```

Do NOT build a marketing website unless the existing project requires one.

The application itself is the portfolio showcase.

---

# 31. DO NOT OVERBUILD

Do NOT add:

* Chatbot for the sake of having a chatbot
* Fake AI assistant
* Fake notifications
* Fake customer data
* Fake metrics
* Unnecessary CRUD
* Billing
* Team management
* Complex authentication
* Dark patterns
* Decorative charts

Every component must have a product reason.

---

# 32. IMPLEMENTATION PROCESS

Follow this sequence.

## Phase 1 — Audit

Inspect the repository and document:

* Existing frontend
* Existing API endpoints
* Data structures
* Available metrics
* Missing endpoints

Do not code yet.

## Phase 2 — Architecture

Design:

* Routes
* Components
* API client
* Data flow
* State management
* Design tokens

## Phase 3 — Design system

Implement:

* Typography
* Colors
* Spacing
* Buttons
* Badges
* Cards
* Tables
* Tabs
* Dialogs
* Tooltips
* Skeletons

## Phase 4 — Core product

Build:

1. Dashboard
2. Worklist
3. Customer 360

These have highest priority.

## Phase 5 — AI/technical visibility

Build:

4. Investigation
5. Agent trace
6. Evaluations

## Phase 6 — Economics

Build:

7. Analytics
8. Outcome measurement

## Phase 7 — Polish

Perform a full UI review.

Check:

* Alignment
* Typography
* spacing
* empty states
* loading states
* responsive behavior
* accessibility
* visual hierarchy
* data formatting
* error handling
* API correctness

---

# 33. QUALITY BAR

Before considering the frontend complete, ask:

### Product

Does this feel like a real product?

### Design

Would a senior designer approve the visual hierarchy?

### Engineering

Would a senior frontend engineer approve the architecture?

### AI

Does the UI clearly communicate ML + agents + verification without pretending the AI is magic?

### Data

Is every number traceable to the backend?

### Trust

Can a user understand why a recommendation was made?

### Economics

Can a user understand whether the intervention is worth doing?

### Portfolio

Could I confidently show this application during an AI engineering interview?

If the answer to any of these is no, improve it before finishing.

---

# 34. FINAL RULE

Do not optimize for:

> "How many UI components can we build?"

Optimize for:

> **"How convincingly can this interface demonstrate the quality of the underlying AI engineering system?"**

The final product should make the following architecture visually obvious:

```text
Customer Data
      ↓
Point-in-Time Features
      ↓
Calibrated XGBoost
      ↓
Risk Shortlist
      ↓
Multi-Agent Investigation
      ↓
Evidence Verification
      ↓
Deterministic Risk Rubric
      ↓
Economic Intervention Planning
      ↓
Operational Worklist
      ↓
Outcome Measurement
```

Build the frontend so that this entire pipeline feels like **one coherent production product**.

Do not stop at a functional UI.

Iterate until it looks polished, intentional, consistent, and portfolio-ready.
