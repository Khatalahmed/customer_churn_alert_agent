---
title: ChurnGuard API
emoji: 🚨
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# ChurnGuard API

The read-only service behind [ChurnGuard](https://github.com/Khatalahmed/customer_churn_alert_agent):
a churn early-warning system where an XGBoost model predicts **who** will stop ordering in the
next 14 days, plain code decides **how urgent**, and an LLM multi-agent explains **why** — with
every claim checked against the database.

There is **no LLM in this service's request path**. Everything it serves is the calibrated model
plus a deterministic rubric, so it answers in milliseconds and costs nothing per request.

## Endpoints

| Path | What it returns |
|---|---|
| `/health` | the analysis time and how many customers are scored |
| `/worklist` | today's shortlist, priced, most valuable first |
| `/customers/{id}` | one customer: risk, evidence, recommendation, economics |
| `/customers/{id}/timeline` | every observable event before the analysis time |
| `/customers/{id}/explanation` | SHAP contributions for that customer |
| `/investigations` | what the agent concluded, and its tool calls |
| `/evaluations` | what the last training run measured |
| `/reliability` | evidence, prose and trajectory checks, recomputed on request |
| `/outcomes` | the hold-out experiment and its statistical conclusion |
| `/economics` | the intervention menu and every assumption behind it |

Interactive docs: [`/docs`](/docs).

## About the data

The database is **synthetic and rebuilt at image-build time** by a seeded simulator against a
frozen reference clock, so this Space regenerates the same 3,000 customers every time. Results
here are a statement about engineering and evaluation quality, never about business impact.

Two limits worth knowing:

- The Space **sleeps when idle**. The first request after a nap takes a while to wake it and
  load the model.
- The filesystem is **ephemeral**. `POST /contacted` works, but anything it records is lost when
  the Space restarts.
