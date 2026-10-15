"""Where artifacts live: replays, traces, archives.

Two backends behind the same three calls, and nothing outside this module
knows which is in use:

  LocalStorage   a directory; development, tests, and a self-hosted server
                 with a disk
  BlobStorage    a private Vercel Blob store, for the hosted control plane,
                 whose functions have no disk that lasts

Artifacts describe a customer's robot in motion, so they are never public:
the store is private and the API is its only reader, streaming each one to a
signed-in member of the workspace that owns it.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import Protocol

import httpx

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*(/[A-Za-z0-9][A-Za-z0-9._\-]*){0,4}$")
MAX_BYTES = 32 * 1024 * 1024


def valid_name(name: str) -> bool:
    """Artifact names are relative paths of plain segments: no '..', no
    leading slash, nothing that could climb out of a campaign's folder."""
    return bool(_SAFE.match(name)) and ".." not in name


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)                      # atomic: a reader never sees half a file
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def delete_prefix(self, prefix: str) -> None:
        base = self.root / prefix
        if base.exists():
            for p in sorted(base.rglob("*"), reverse=True):
                p.unlink() if p.is_file() else p.rmdir()
            base.rmdir()


class BlobError(RuntimeError):
    pass


class BlobStorage:
    """A private Vercel Blob store, over its HTTP API: the same requests the
    official clients make (the `vercel` Python package, @vercel/blob), with
    nothing but httpx. Writes go to the Blob API; reads go straight to the
    store's private host with the same token."""

    API = "https://vercel.com/api/blob"
    VERSION = "11"

    def __init__(self, token: str, *, client: httpx.Client | None = None) -> None:
        parts = token.split("_")            # vercel_blob_rw_<store id>_<secret>
        if len(parts) < 5 or not parts[3]:
            raise BlobError("BLOB_READ_WRITE_TOKEN does not look like a Vercel Blob read-write token")
        self.token, self.store = token, parts[3]
        self.http = client or httpx.Client(timeout=30.0)

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        return {"authorization": f"Bearer {self.token}", "x-api-version": self.VERSION,
                "x-api-blob-request-id": f"{self.store}:{int(time.time() * 1000)}:{uuid.uuid4().hex[:8]}",
                "x-api-blob-request-attempt": "0", **(extra or {})}

    def _check(self, r: httpx.Response, what: str) -> httpx.Response:
        if r.status_code >= 400:
            try:
                err = r.json().get("error") or {}
            except ValueError:
                err = {}
            raise BlobError(f"{what}: {r.status_code} {err.get('code', '')} {err.get('message', r.text[:200])}".strip())
        return r

    def url(self, key: str) -> str:
        return f"https://{self.store}.private.blob.vercel-storage.com/{key}"

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        headers = self._headers({"x-content-type": content_type, "x-add-random-suffix": "0",
                                 "x-allow-overwrite": "1", "x-vercel-blob-access": "private"})
        self._check(self.http.put(self.API, params={"pathname": key}, content=data, headers=headers), f"put {key}")
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> bytes:
        r = self.http.get(self.url(key), headers={"authorization": f"Bearer {self.token}"}, follow_redirects=True)
        if r.status_code == 404:
            raise FileNotFoundError(key)
        return self._check(r, f"get {key}").content

    def delete_prefix(self, prefix: str) -> None:
        cursor = None
        while True:
            params = {"prefix": prefix.rstrip("/") + "/", "limit": 1000, **({"cursor": cursor} if cursor else {})}
            page = self._check(self.http.get(self.API, params=params, headers=self._headers()), f"list {prefix}").json()
            urls = [b["url"] for b in page.get("blobs", [])]
            if urls:
                self._check(self.http.post(f"{self.API}/delete", json={"urls": urls},
                                           headers=self._headers({"content-type": "application/json"})),
                            f"delete {prefix}")
            cursor = page.get("cursor")
            if not page.get("hasMore") or not cursor:
                return


def make_storage(settings) -> Storage:
    if settings.storage == "blob":
        if not settings.blob_token:
            raise BlobError("TEETER_STORAGE=blob needs BLOB_READ_WRITE_TOKEN, from a private Vercel Blob store")
        return BlobStorage(settings.blob_token)
    if settings.storage == "local":
        return LocalStorage(settings.storage_dir)
    raise ValueError(f"TEETER_STORAGE must be 'local' or 'blob', not {settings.storage!r}")
