"""Where artifacts live: replays, traces, archives.

A local directory in development. Production uses an S3-compatible bucket
behind the same three calls; nothing outside this module knows which.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*(/[A-Za-z0-9][A-Za-z0-9._\-]*){0,4}$")
MAX_BYTES = 32 * 1024 * 1024


def valid_name(name: str) -> bool:
    """Artifact names are relative paths of plain segments: no '..', no
    leading slash, nothing that could climb out of a campaign's folder."""
    return bool(_SAFE.match(name)) and ".." not in name


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def put(self, key: str, data: bytes) -> str:
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
