# Everyday commands. CI runs the same ones (.github/workflows/ci.yml).
#
#   make install      .venv/ with the engine, the API and the runner, editable
#   make test         all three test suites (SQLite; set TEETER_TEST_DATABASE_URL for Postgres too)
#   make check        the published campaign record still matches the engine
#   make dev          the product on this machine, without Docker (scripts/dev.sh)
#   make up / down    the product in Docker: Postgres, the API and app, a runner
#   make images       build the API and runner images only

VENV ?= .venv
PY   := $(abspath $(VENV))/bin/python
PIP  := $(abspath $(VENV))/bin/pip

.PHONY: install test test-harness test-api test-runner check dev up down images

# the engine first, so pip finds it here and never looks for it on an index
$(VENV)/bin/teeter:
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e "harness[dev]"
	$(PIP) install -q -e "api[dev]"
	$(PIP) install -q -e "runner[dev]"

install: $(VENV)/bin/teeter

test: test-harness test-api test-runner

test-harness: install
	cd harness && $(PY) -m pytest tests -q

test-api: install
	cd api && $(PY) -m pytest tests -q

test-runner: install
	cd runner && $(PY) -m pytest tests -q

check: install
	$(PY) tools/publish_campaign.py --check

dev: install
	VENV=$(VENV) scripts/dev.sh

up:
	docker compose up --build -d
	@docker compose logs setup | grep -A1 "sign in" || true

down:
	docker compose down

images:
	docker build -f api/Dockerfile -t teeter-api:dev .
	docker build -f runner/Dockerfile -t teeter-runner:dev .
