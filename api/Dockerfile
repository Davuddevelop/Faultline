# The control plane: the API under /v1, and the website and the app at /.
# It never imports the engine, so the image carries no MuJoCo.
#
#   docker build -f api/Dockerfile -t teeter-api .        (from the repository root)
#
# Configuration is the environment only; see teeter_api/settings.py. State
# (artifacts, and the demo's token files) lives in /data. Give it
# TEETER_DATABASE_URL for Postgres; without one it keeps a SQLite file there.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore

# one uid for both images, so the runner can read the token the demo writes
RUN useradd --uid 10001 --no-create-home --home-dir /srv --shell /usr/sbin/nologin teeter && mkdir /data && chown teeter /data
WORKDIR /srv

COPY api/pyproject.toml api/
COPY api/teeter_api api/teeter_api
RUN pip install ./api

COPY teeter site
ENV TEETER_SITE_DIR=/srv/site TEETER_STATE_DIR=/data

USER teeter
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=10 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health', timeout=2)"]
CMD ["teeter-api", "serve", "--host", "0.0.0.0", "--port", "8000"]
