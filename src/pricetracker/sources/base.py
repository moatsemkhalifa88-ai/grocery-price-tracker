"""Common interface every chain source implements."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from ..models import FileName, FileType, RemoteFile

log = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class ChainInfo:
    key: str
    chain_id: str
    name_he: str
    name_en: str


class Source(ABC):
    """A place we can list and download a chain's transparency files from."""

    def __init__(self, chain: ChainInfo, timeout: int = 60, retries: int = 3):
        self.chain = chain
        self.timeout = timeout
        self.retries = retries

    @abstractmethod
    def list_files(self, file_type: FileType, store_ids: Iterable[int] | None = None) -> list[RemoteFile]:
        """Files of ``file_type`` (optionally only for ``store_ids``), any order."""

    @abstractmethod
    def download(self, f: RemoteFile) -> bytes:
        """Raw bytes of one file."""

    def close(self) -> None:  # noqa: B027 - optional hook
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------------------------------------------------------------- utils
    def _remote(self, name: str, url: str) -> RemoteFile | None:
        meta = FileName.parse(name)
        if meta is None or meta.is_null:
            return None
        return RemoteFile(chain_key=self.chain.key, name=name, url=url, meta=meta)

    def with_retries(self, what: str, fn: Callable[[], T]) -> T:
        delay = 2.0
        for attempt in range(1, self.retries + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - network errors are varied
                if attempt == self.retries:
                    raise
                log.warning("%s: %s failed (%s), retry %d/%d in %.0fs",
                            self.chain.key, what, exc, attempt, self.retries, delay)
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("unreachable")


def latest_per_store(files: Iterable[RemoteFile]) -> dict[int | None, RemoteFile]:
    """Keep only the newest file for every store id."""
    best: dict[int | None, RemoteFile] = {}
    for f in files:
        cur = best.get(f.meta.store_id)
        if cur is None or (f.meta.published_at or datetime.min) > (cur.meta.published_at or datetime.min):
            best[f.meta.store_id] = f
    return best
