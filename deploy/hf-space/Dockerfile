# ChurnGuard API — Hugging Face Space (Docker SDK)
#
# This file lives in the SPACE repository, not in the project repository. It
# clones the project at build time, which keeps the Space to two files and
# means a rebuild always picks up main.
#
# The data and the model are NOT downloaded: they are rebuilt here. The
# simulator is seeded (RANDOM_SEED = 42) against a frozen reference clock, so
# this build regenerates byte-identical data to a local one, and the model
# trained on it is the same model. That is why a 50MB database never has to
# live in git.

FROM ghcr.io/astral-sh/uv:bookworm-slim

# git, to clone the project at build time
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face runs the container as uid 1000; everything it writes must be
# owned by that user, including the artefacts built below.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

# Bump this to force a rebuild that picks up new commits.
ARG REVISION=main
RUN git clone --depth 1 --branch "$REVISION" \
    https://github.com/Khatalahmed/customer_churn_alert_agent.git .

# Runtime dependencies only: pytest and friends are not needed to serve.
RUN uv python install && uv sync --frozen --no-dev

# Build the demo's state, in the order the pipeline expects:
#   1. the synthetic database and its answer key
#   2. the calibrated model and model_metrics.json
#   3. the action log the outcome experiment reads
# The agent's own output (predictions, trace) is cloned with the repo: it
# comes from a paid LLM run and cannot be regenerated here.
RUN uv run python -m churn.quick_commerce_sim init \
    && uv run python -m churn.train_model \
    && uv run python -m churn.outcomes

# Spaces route to 7860 by default; app_port in the Space README must match.
EXPOSE 7860
CMD ["uv", "run", "uvicorn", "churn.api:app", "--host", "0.0.0.0", "--port", "7860"]
