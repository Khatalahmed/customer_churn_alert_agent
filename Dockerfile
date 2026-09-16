# ChurnGuard API image.
#
# Built by .github/workflows/publish-image.yml on every push to main, pushed to
# ghcr.io, and pulled from there by Azure Container Apps. The same file runs
# locally:
#
#   docker build -t churnguard-api .
#   docker run -p 8000:8000 churnguard-api
#
# The data and the model are NOT copied in: they are rebuilt here. The
# simulator is seeded against a frozen reference clock, so this build produces
# the same customers and the same model as a local run.

FROM ghcr.io/astral-sh/uv:bookworm-slim

# Run as an unprivileged user; everything the build writes is owned by it, so
# POST /contacted can still record to the working directory.
RUN useradd --create-home --uid 1000 app
USER app
ENV HOME=/home/app
WORKDIR /home/app/api

# the pinned Python, then dependencies before the code, for layer caching
COPY --chown=app:app .python-version ./
RUN uv python install
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=app:app . .

# The demo's state, in pipeline order:
#   1. the synthetic database and its answer key
#   2. the calibrated model and model_metrics.json
#   3. the action log the outcome experiment reads
RUN uv run --no-sync python -m churn.quick_commerce_sim init \
    && uv run --no-sync python -m churn.train_model \
    && uv run --no-sync python -m churn.outcomes

EXPOSE 8000
# exec so uvicorn, not the shell, receives the platform's stop signal.
# To run the offline agent instead:
#   docker run --env-file .env churnguard-api uv run --no-sync python -m churn.main
CMD ["sh", "-c", "exec uv run --no-sync uvicorn churn.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
