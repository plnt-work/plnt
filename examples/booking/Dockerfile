# Single image for both `api` (uvicorn) and `worker` (Temporal worker).
# Build context MUST be the umbrella `den-agent/` directory so this can
# COPY both ../plnt and ./plnt-cloud — see docker-compose.yml.
#
# Source is also bind-mounted at runtime (../plnt → /src/plnt,
# ./plnt-cloud → /src/plnt-cloud), so editing Python files on the host
# is picked up by uvicorn --reload / a worker restart without rebuilding.
# The COPY here only exists so `pip install -e` has something to install
# against at image-build time; the bind mounts override it at run time.

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl is only used by the worker-entrypoint sanity check ("did /env/.env
# actually mount?"). git is required because pip's editable install of
# plnt picks up a setuptools_scm-style version from git metadata.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# plnt (the runtime) and plnt-cloud (this repo) are both installed
# editable. Order matters: plnt-cloud's pyproject pulls plnt by name, so
# plnt must already be importable.
COPY plnt/ /src/plnt/
RUN pip install --no-cache-dir -e /src/plnt

COPY plnt-cloud/pyproject.toml /src/plnt-cloud/pyproject.toml
COPY plnt-cloud/ /src/plnt-cloud/
RUN pip install --no-cache-dir -e /src/plnt-cloud

# Worker entrypoint enforces the .env sourcing discipline from CLAUDE.md.
COPY plnt-cloud/scripts/worker-entrypoint.sh /usr/local/bin/worker-entrypoint.sh
RUN chmod +x /usr/local/bin/worker-entrypoint.sh

WORKDIR /src/plnt-cloud

# Default to the api command; the worker service overrides with
# entrypoint: ["/usr/local/bin/worker-entrypoint.sh"].
EXPOSE 8080
CMD ["uvicorn", "surface.app:app", "--host", "0.0.0.0", "--port", "8080"]
