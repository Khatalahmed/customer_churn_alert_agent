# uv base image; uv installs the exact Python from .python-version
FROM ghcr.io/astral-sh/uv:bookworm-slim

WORKDIR /app

# install the pinned Python version (reads .python-version)
COPY .python-version ./
RUN uv python install

# install dependencies first (better layer caching; skip dev deps like pytest)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# copy the rest of the code
COPY . .

# build the synthetic data + train the model at image-build time (no API key needed)
RUN uv run python -m churn.quick_commerce_sim init && uv run python -m churn.train_model

# default: run the churn agent (pass provider key at runtime: docker run --env-file .env)
CMD ["uv", "run", "python", "-m", "churn.main"]
