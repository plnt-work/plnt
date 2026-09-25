# plnt server: the multi-tenant API with the web console at /console.
#
#   docker build -t plnt .
#   docker run -p 8787:8787 -v plnt-data:/data -e PLNT_ADMIN_TOKEN=... plnt
#
# All state lives in /data (PLNT_HOME). Mount a volume there.

FROM node:22-slim AS console
WORKDIR /src/console
COPY console/package.json console/package-lock.json ./
RUN npm ci
COPY console/ ./
RUN npm run build  # writes /src/plnt/server/console

FROM python:3.12-slim AS wheel
WORKDIR /src
RUN pip install --no-cache-dir build
COPY pyproject.toml setup.py MANIFEST.in README.md LICENSE CHANGELOG.md ./
COPY plnt/ plnt/
COPY registry/bundles/ registry/bundles/
COPY --from=console /src/plnt/server/console/ plnt/server/console/
RUN python -m build --wheel --outdir /dist

FROM python:3.12-slim
COPY --from=wheel /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl \
    && useradd --create-home --uid 10001 plnt \
    && mkdir /data && chown plnt /data
USER plnt
ENV PLNT_HOME=/data PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/v1/health')"
CMD ["plnt", "serve", "--host", "0.0.0.0", "--port", "8787"]
