"""The control plane, over HTTPS. Every call is outbound.

Calls that are safe to repeat (all of them but the first claim of a job) are
retried with backoff on network errors and 5xx, so a flaky office network
costs a few seconds, not a campaign. A 409 means the lease is gone and is
never retried: the job belongs to someone else now.
"""

from __future__ import annotations

import time
from typing import Any

import httpx


class LeaseLost(Exception):
    """The control plane says this runner no longer holds the job."""


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}")
        self.status, self.message = status, message


class Client:
    def __init__(self, api: str, token: str, *, timeout: float = 30.0, retries: int = 5) -> None:
        self.api = api.rstrip("/")
        self.retries = retries
        self.http = httpx.Client(base_url=self.api, timeout=timeout,
                                 headers={"Authorization": f"Bearer {token}",
                                          "User-Agent": "teeter-runner"})

    def close(self) -> None:
        self.http.close()

    def _call(self, method: str, path: str, *, retry: bool = True, **kw) -> httpx.Response:
        delay = 1.0
        for attempt in range(self.retries + 1 if retry else 1):
            try:
                r = self.http.request(method, path, **kw)
            except httpx.TransportError as exc:
                if attempt >= self.retries or not retry:
                    raise ApiError(0, f"cannot reach {self.api}: {exc}") from exc
            else:
                if r.status_code == 409:
                    raise LeaseLost(r.json().get("error", {}).get("message", "lease lost"))
                if r.status_code < 500 or not retry or attempt >= self.retries:
                    if r.status_code >= 400:
                        try:
                            msg = r.json()["error"]["message"]
                        except Exception:
                            msg = r.text[:500]
                        raise ApiError(r.status_code, msg)
                    return r
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
        raise ApiError(0, "unreachable")              # pragma: no cover

    # ── the runner protocol ────────────────────────────────────────────
    def register(self, **info: Any) -> dict:
        return self._call("POST", "/v1/runner/register", json=info).json()

    def claim(self, wait_s: float = 20.0) -> dict | None:
        r = self._call("POST", "/v1/runner/claim", json={"wait_s": wait_s}, timeout=wait_s + 30)
        return None if r.status_code == 204 else r.json()

    def heartbeat(self, job: str, progress: dict) -> dict:
        return self._call("POST", f"/v1/runner/jobs/{job}/heartbeat", json={"progress": progress}).json()

    def evaluations(self, job: str, rows: list[dict]) -> dict:
        return self._call("POST", f"/v1/runner/jobs/{job}/evaluations", json={"evaluations": rows}).json()

    def artifact(self, job: str, name: str, data: bytes, content_type: str) -> dict:
        return self._call("PUT", f"/v1/runner/jobs/{job}/artifacts/{name}", content=data,
                          headers={"Content-Type": content_type}).json()

    def complete(self, job: str, result: dict) -> dict:
        return self._call("POST", f"/v1/runner/jobs/{job}/complete", json={"result": result}).json()

    def fail(self, job: str, error: str, *, retryable: bool = False, canceled: bool = False) -> dict:
        return self._call("POST", f"/v1/runner/jobs/{job}/fail",
                          json={"error": error, "retryable": retryable, "canceled": canceled}).json()

    # ── what people and CI call ────────────────────────────────────────
    def get(self, path: str, **params) -> dict:
        return self._call("GET", path, params=params).json()

    def post(self, path: str, body: dict) -> dict:
        return self._call("POST", path, json=body, retry=False).json()
