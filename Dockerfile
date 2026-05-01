# syntax=docker/dockerfile:1.7
#
# archithreat — multi-stage container build
#
# Stage 1: build the wheel from source.
# Stage 2: install the wheel + [web] extras into a slim runtime image
#          and run the FastAPI app under uvicorn as a non-root user.
#
# Build args:
#   VERSION  — image/package version  (default: 0.0.0-dev)
#   REVISION — git commit SHA         (default: unknown)

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Stage 1 — builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build tooling for lxml et al. Kept in builder only; not in runtime layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# PEP 517 build frontend.
RUN pip install --no-cache-dir "build>=1.2"

# Copy the minimum needed to build the wheel. The .dockerignore keeps tests,
# .venv, .git, browser/, etc. out of context.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m build --wheel --outdir /wheels

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG VERSION=0.0.0-dev
ARG REVISION=unknown

# OCI image labels (populated from build args; see release.yaml).
LABEL org.opencontainers.image.title="archithreat" \
      org.opencontainers.image.description="ArchiMate to threat-model converter" \
      org.opencontainers.image.source="https://github.com/rondlite/archithreat" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/archithreat/.local/bin:${PATH}"

# Runtime libs only (no -dev headers, no compilers). curl is used by HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user, fixed UID 1000 to match common host conventions.
RUN groupadd --system --gid 1000 archithreat \
    && useradd --system --uid 1000 --gid 1000 \
        --home-dir /home/archithreat --create-home \
        --shell /usr/sbin/nologin archithreat

# Copy the wheel built in stage 1 and install it + the [web] extra into the
# user-local site-packages. Installing as the unprivileged user keeps the
# install rooted under /home/archithreat/.local with no root-owned bits.
COPY --from=builder /wheels /wheels

USER 1000
WORKDIR /home/archithreat

RUN pip install --user --no-cache-dir /wheels/archithreat-*.whl \
    && pip install --user --no-cache-dir "archithreat[web]" \
        --no-index --find-links /wheels \
        || pip install --user --no-cache-dir "$(ls /wheels/archithreat-*.whl)[web]"

EXPOSE 8000

# Liveness probe — /healthz is intentionally cheap and dependency-free.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8000/healthz || exit 1

# Defaults from web/settings.py kick in when no env vars are set.
CMD ["uvicorn", "archithreat.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
