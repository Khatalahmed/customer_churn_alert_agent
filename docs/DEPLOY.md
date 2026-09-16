# Deploying ChurnGuard for free

Two hosts, no credit card, about twenty minutes.

| Piece | Host | Free tier |
|---|---|---|
| The API (FastAPI + XGBoost + SHAP) | **Hugging Face Spaces**, Docker SDK | 2 vCPU / 16GB RAM, sleeps when idle |
| The interface (Next.js) | **Vercel**, Hobby | 100GB bandwidth a month |

They are separate because their needs are opposite: the API is a 1.5GB image that has to hold a
model in memory, and the UI is a thin server-rendered layer that should sit on a CDN. Deploy the
API first — the UI needs its address.

---

## 1. The API, on Hugging Face Spaces

**Create the Space.** At [huggingface.co/new-space](https://huggingface.co/new-space):

- Owner: you · Space name: `churnguard-api`
- License: MIT
- **Space SDK: Docker** → **Blank**
- Hardware: CPU basic (free) · Visibility: Public

**Give it its two files.** A Space is a git repository containing, in this case, nothing but a
`Dockerfile` and a `README.md` — the build clones this project itself.

```bash
git clone https://huggingface.co/spaces/<your-username>/churnguard-api
cd churnguard-api

# from a checkout of this project
cp /path/to/customer_churn_alert_agent/deploy/hf-space/Dockerfile .
cp /path/to/customer_churn_alert_agent/deploy/hf-space/README.md .

git add . && git commit -m "ChurnGuard API" && git push
```

Pushing starts the build. It takes roughly **5–8 minutes**, because it does real work: installs
the dependencies, runs the simulator, trains the calibrated model, and measures the outcome
experiment. Watch it under the Space's **Logs** tab.

**Check it.** When the build finishes:

```
https://<your-username>-churnguard-api.hf.space/health
```

should answer with the analysis time and the number of customers scored. `/docs` gives you the
interactive API.

> **Why nothing large is uploaded.** The 50MB database and the 2.1MB model are not in git and are
> not downloaded. The simulator is seeded against a frozen clock, so the build *regenerates* them
> byte-identically. The only artefacts that travel with the repository are the agent's own output
> — 28KB of predictions and tool trace — because they come from a paid LLM run and no build can
> reproduce them.

---

## 2. The interface, on Vercel

At [vercel.com/new](https://vercel.com/new), import the GitHub repository, then change **one**
setting before deploying:

- **Root Directory** → `frontend`

Everything else auto-detects. Then add the environment variable:

| Name | Value |
|---|---|
| `CHURN_API_URL` | `https://<your-username>-churnguard-api.hf.space` |

No trailing slash. Add it for Production, Preview and Development.

Deploy. Your interface is live at `https://<project>.vercel.app`.

**There is no CORS configuration, because there is nothing to configure.** Every fetch happens in
a server component or a route handler, so the browser only ever talks to Vercel and Vercel talks
to the Space. The API's address never reaches client code.

---

## 3. What a visitor should be told

Three behaviours are consequences of the free tier, not bugs. Say so somewhere visible rather
than letting someone conclude the app is broken:

1. **The first load after a quiet spell is slow.** A free Space sleeps when idle; waking it and
   loading the model takes 30–60 seconds. Every load after that is fast.
2. **"Mark as contacted" does not survive a restart.** The Space's filesystem is ephemeral, so the
   contact log resets. The action works, and the worklist updates — it just forgets eventually.
3. **The data is synthetic.** 3,000 simulated customers. The results are a statement about
   engineering and evaluation quality, never about business impact.

---

## Updating a deployment

**The interface** redeploys on every push to `main` — Vercel watches the repository.

**The API does not**, because its Dockerfile clones the project at build time rather than
tracking it. Rebuild it when the backend changes:

```bash
cd churnguard-api
git commit --allow-empty -m "rebuild against latest main" && git push
```

Or use the Space's **Settings → Factory rebuild**. After a backend change that alters an API
payload, redeploy the UI too — the two are versioned independently, and a rename in one is a
`NaN` in the other.

---

## If something is wrong

| Symptom | Cause |
|---|---|
| Every page says "Service unreachable" | `CHURN_API_URL` unset, misspelled, or has a trailing slash |
| Pages load but panels say "not measured yet" | that artefact was not produced — the panel names the command that makes it |
| The Space build fails during training | the free CPU tier ran out of memory; retry, or shrink `NUM_CUSTOMERS` in `churn/quick_commerce_sim.py` |
| First request times out | the Space is waking up; wait and reload |
| `/investigations` is empty | `churn_predictions.json` is missing from the repository — it must stay tracked |
