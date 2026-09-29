FROM node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6 AS frontend
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STEG_DATA_DIR=/data STEG_FRONTEND_DIR=/app/frontend/dist \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY pyproject.toml ./
COPY steganalysis ./steganalysis
COPY script.py ./
RUN pip install --no-cache-dir --no-deps . && \
    useradd --uid 10001 --create-home analyst && mkdir /data && chown analyst:analyst /data
COPY --from=frontend /ui/dist ./frontend/dist
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/cases',timeout=3)" || exit 1
CMD ["python", "-m", "uvicorn", "steganalysis.api:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]

FROM runtime AS verification
USER root
COPY uv.lock ./
RUN pip install --no-cache-dir uv==0.12.20 && \
    uv export --quiet --frozen --all-groups --no-emit-project --output-file /tmp/check-requirements.txt && \
    pip install --no-cache-dir --require-hashes -r /tmp/check-requirements.txt
COPY tests ./tests
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp=/tmp/steganalysis-tests"]

FROM runtime AS production
