# A runner: the engine, the teeter CLI, and the demo allowlist. A customer's
# runner image starts from this one and adds its own robot files, policy
# checkpoints and allowlist (see runner/README.md); nothing in them leaves
# the machine it runs on.
#
#   docker build -f runner/Dockerfile -t teeter-runner .  (from the repository root)
#   docker run --rm -e TEETER_API=https://… -e TEETER_TOKEN=tt_run_… teeter-runner
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore

RUN useradd --uid 10001 --no-create-home --home-dir /srv --shell /usr/sbin/nologin teeter
WORKDIR /srv

# the engine first, from this checkout, so pip never looks for it elsewhere
COPY harness/pyproject.toml harness/README.md harness/
COPY harness/faultline harness/faultline
COPY harness/models harness/models
RUN pip install ./harness

COPY runner/pyproject.toml runner/demo-runner.yaml runner/
COPY runner/teeter_runner runner/teeter_runner
RUN pip install ./runner

USER teeter
ENTRYPOINT ["teeter"]
CMD ["runner", "start", "--config", "/srv/runner/demo-runner.yaml"]
