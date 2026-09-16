# Deploying ChurnGuard

| Piece | Host | Cost |
|---|---|---|
| The API (FastAPI + XGBoost + SHAP) | **Azure Container Apps**, Consumption plan | inside the monthly free grant, if nothing else in the subscription spends it |
| The image | **GitHub Container Registry** | free for public images |
| The interface (Next.js) | **Vercel**, Hobby | free |

Deploy the API first — the UI needs its address.

> **Why not Azure Container Registry?** It has no free tier: Basic is a flat daily fee whether
> anything pulls from it or not. Container Apps pulls a public ghcr.io image with no credentials,
> so the registry costs nothing.
>
> **Why no LLM service?** The API never calls one. The agent runs offline and its output —
> `churn_predictions.json` and `agent_trace.json` — is committed and baked into the image. The
> served path is the calibrated model plus deterministic code, answering in milliseconds.

---

## 1. The image, built by GitHub Actions

Nothing to run. Every push to `main` runs CI, and when CI passes,
`.github/workflows/publish-image.yml` builds the root `Dockerfile` and pushes

```
ghcr.io/khatalahmed/churnguard-api:<12-char commit sha>
ghcr.io/khatalahmed/churnguard-api:latest
```

**Once, after the first publish:** GitHub creates the package *private*. On GitHub, open
**your profile → Packages → churnguard-api → Package settings → Change visibility → Public**.
Until then Azure cannot pull it.

The image rebuilds the database and model at build time from the seeded simulator, so nothing
large is ever uploaded, and `.dockerignore` is an allowlist — only `churn/`, the lockfile and the
two agent artefacts go in, never `.env` or anything else in the checkout.

## 2. The API, on Azure Container Apps

Subscriptions are limited in how many environments they may hold per region, so reuse one if
you have it. The app still gets its own resource group, so removing it never touches whatever
else shares the environment:

```bash
az containerapp env list -o table          # reuse one of these if it exists

az group create -n churnguard-rg -l southeastasia

ENV_ID=$(az containerapp env show -n <env-name> -g <env-resource-group> --query id -o tsv)

az containerapp create -n churnguard-api -g churnguard-rg   --environment "$ENV_ID"   --image ghcr.io/khatalahmed/churnguard-api:latest   --ingress external --target-port 8000   --cpu 1 --memory 2Gi   --min-replicas 0 --max-replicas 1   --query properties.configuration.ingress.fqdn -o tsv
```

With no environment yet, create one first — `--logs-destination none` avoids Log Analytics
ingestion charges, and live logs still stream with `az containerapp logs show`:

```bash
az containerapp env create -n churnguard-env -g churnguard-rg -l southeastasia   --logs-destination none
```

The last command prints the address. `https://<fqdn>/health` should answer with the analysis
time and the number of customers scored; `/docs` is the interactive API.

Why these settings:

- **`--min-replicas 0`** is what makes it free: an idle app costs nothing and wakes on the next
  request. The price is a cold start of a minute or so after a quiet spell.
- **`--max-replicas 1`** caps the bill. A demo does not need to scale out, and one replica keeps
  the contact log in one place.
- **1 vCPU / 2 GiB**: the model and SHAP explainer are held in memory.

### Redeploying

Container Apps does not notice when `latest` moves. After a new image is published, pin the
exact commit — which also makes rollback a matter of naming an older sha:

```bash
az containerapp update -n churnguard-api -g churnguard-rg \
  --image ghcr.io/khatalahmed/churnguard-api:<sha>
```

### Staying inside the free grant

The grant — 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests a month — is **per
subscription**, shared by every Container App in it. One app with `--min-replicas 1` and a full
vCPU spends it in about two days, after which *every* app is billed. Check before assuming $0:

```bash
az containerapp list --query "[].{name:name, min:properties.template.scale.minReplicas}" -o table
```

An app that must stay awake — a polling bot with no HTTP ingress, say — cannot scale to zero,
because nothing would ever wake it. Budget for those rather than breaking them.

### Removing it

```bash
az group delete -n churnguard-rg
```

This removes the app only; a shared environment in another resource group is left alone.

## 3. The interface, on Vercel

At [vercel.com/new](https://vercel.com/new), import the GitHub repository and change **one**
setting before deploying:

- **Root Directory** → `frontend`

Add the environment variable, with no trailing slash, for Production, Preview and Development:

| Name | Value |
|---|---|
| `CHURN_API_URL` | `https://<fqdn from step 2>` |

There is no CORS to configure: every fetch happens in a server component or route handler, so the
browser only talks to Vercel, and Vercel talks to Azure. The UI redeploys on every push to `main`.

---

## What a visitor should be told

1. **The first load after a quiet spell is slow.** The app scaled to zero; waking it and loading
   the model takes about a minute.
2. **"Mark as contacted" does not survive a restart.** The container's filesystem is ephemeral.
3. **The data is synthetic.** 3,000 simulated customers. The results are a statement about
   engineering and evaluation quality, never about business impact.

## If something is wrong

| Symptom | Cause |
|---|---|
| Every page says "Service unreachable" | `CHURN_API_URL` unset, misspelled, or has a trailing slash |
| `containerapp create` fails pulling the image | the ghcr.io package is still private (step 1) |
| First request times out | the app is waking from zero; wait and reload |
| Panels say "not measured yet" | that artefact was not produced — the panel names the command |
| `/investigations` is empty | `churn_predictions.json` is missing from the image — it must stay tracked and allowlisted in `.dockerignore` |
| The deployed app is behind `main` | it is pinned to an older sha; run the redeploy command |

## Alternative: Hugging Face Spaces

`deploy/hf-space/` holds a working Docker Space (verified to build and serve). Docker Spaces
currently require a paid Hugging Face plan, which is why this guide uses Azure instead.
