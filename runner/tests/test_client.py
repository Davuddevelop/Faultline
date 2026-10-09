"""The runner's HTTP client against a mocked control plane: an empty claim
sets how long to wait, and extra headers ride along with the token."""

from __future__ import annotations

import httpx

from teeter_runner.client import Client, extra_headers


def _client(handler, **kw) -> Client:
    c = Client("https://cp.example", "tt_run_x", **kw)
    c.http = httpx.Client(base_url=c.api, headers=c.http.headers, transport=httpx.MockTransport(handler))
    return c


def test_an_empty_claim_takes_its_pause_from_retry_after():
    c = _client(lambda req: httpx.Response(204, headers={"Retry-After": "10"}))
    assert c.claim(wait_s=20) is None and c.retry_after == 10.0
    c = _client(lambda req: httpx.Response(204))
    assert c.claim() is None and c.retry_after == 0.0              # a long-polling server: ask again now
    c = _client(lambda req: httpx.Response(204, headers={"Retry-After": "86400"}))
    c.claim()
    assert c.retry_after == 300.0                                  # capped: a runner never sleeps for a day


def test_a_job_clears_the_pause():
    job = {"job": {"id": "j"}, "campaign": {"ref": "C-0001"}}
    c = _client(lambda req: httpx.Response(200, json=job))
    c.retry_after = 10.0
    assert c.claim() == job and c.retry_after == 0.0


def test_extra_headers_come_from_options_and_the_environment(monkeypatch):
    monkeypatch.setenv("TEETER_HEADERS", "CF-Access-Client-Id: abc\nx-vercel-protection-bypass: s3cret")
    h = extra_headers(["X-Team: robots", "Authorization: Bearer nope", "not a header"])
    assert h == {"CF-Access-Client-Id": "abc", "x-vercel-protection-bypass": "s3cret", "X-Team": "robots"}
    seen = {}

    def handler(req):
        seen.update(req.headers)
        return httpx.Response(200, json={"name": "r"})

    c = _client(handler)
    c.register(name="r")
    assert seen["authorization"] == "Bearer tt_run_x"           # the token cannot be overridden
    assert seen["cf-access-client-id"] == "abc"
