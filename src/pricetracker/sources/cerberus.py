"""Cerberus — the shared FTP platform many chains use (Rami Levy, Osher Ad,
Yohananof, Tiv Taam, Keshet…): ``url.retail.publishedprices.co.il``.

Each chain has its own public username (password usually empty). The server
speaks explicit FTPS. One directory holds every file the chain published in the
last day or so, so we list once and filter locally.
"""

from __future__ import annotations

import io
import logging
import socket
from collections.abc import Iterable
from ftplib import FTP_TLS, error_perm

from ..models import FileType, RemoteFile
from .base import ChainInfo, Source

log = logging.getLogger(__name__)

HOST = "url.retail.publishedprices.co.il"


class CerberusSource(Source):
    def __init__(self, chain: ChainInfo, username: str, password: str = "",
                 timeout: int = 60, retries: int = 3, host: str = HOST):
        super().__init__(chain, timeout, retries)
        self.username = username
        self.password = password
        self.host = host
        self._ftp: FTP_TLS | None = None
        self._listing: list[str] | None = None

    # ------------------------------------------------------------ connection
    def _connect(self) -> FTP_TLS:
        if self._ftp is not None:
            try:
                self._ftp.voidcmd("NOOP")
                return self._ftp
            except Exception:  # noqa: BLE001 - stale connection
                self._ftp = None
        ftp = FTP_TLS(self.host, timeout=self.timeout)
        ftp.trust_server_pasv_ipv4_address = True
        ftp.login(self.username, self.password)  # AUTH TLS on the control channel
        ftp.set_pasv(True)
        self._ftp = ftp
        return ftp

    def _reset(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.close()
            except Exception:  # noqa: BLE001
                pass
        self._ftp = None

    def _names(self) -> list[str]:
        if self._listing is None:
            def call():
                try:
                    return self._connect().nlst()
                except (OSError, EOFError, error_perm):
                    self._reset()
                    raise
            self._listing = self.with_retries("NLST", call)
            log.info("%s: %d files on FTP", self.chain.key, len(self._listing))
        return self._listing

    # --------------------------------------------------------------- Source
    def list_files(self, file_type: FileType, store_ids: Iterable[int] | None = None) -> list[RemoteFile]:
        wanted = set(store_ids) if store_ids is not None else None
        out = []
        for name in self._names():
            if not name.lower().endswith((".gz", ".xml", ".zip")):
                continue
            rf = self._remote(name, f"ftp://{self.host}/{name}")
            if rf is None or rf.meta.file_type is not file_type:
                continue
            if rf.meta.chain_id != self.chain.chain_id:
                continue
            if wanted is not None and file_type is not FileType.STORES and rf.meta.store_id not in wanted:
                continue
            out.append(rf)
        return out

    def download(self, f: RemoteFile) -> bytes:
        def call():
            buf = io.BytesIO()
            ftp = self._connect()
            try:
                ftp.voidcmd("TYPE I")
                expected = None
                try:
                    expected = ftp.size(f.name)
                except error_perm:
                    pass
                ftp.retrbinary(f"RETR {f.name}", buf.write)
            except (OSError, EOFError, socket.timeout, error_perm):
                self._reset()
                raise
            data = buf.getvalue()
            if expected is not None and len(data) != expected:
                raise IOError(f"truncated transfer {len(data)}/{expected} bytes")
            return data
        return self.with_retries(f"RETR {f.name}", call)

    def close(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.quit()
            except Exception:  # noqa: BLE001
                pass
        self._ftp = None
