"""Shufersal publishes on its own portal: prices.shufersal.co.il.

The portal is an HTML table (``#gridContainer``) filtered by ``catID`` and
``storeId``. Each row links to a short-lived Azure blob URL with the .gz file.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

import requests
from lxml import html as lxml_html

from ..models import FileType, RemoteFile
from .base import ChainInfo, Source

log = logging.getLogger(__name__)

BASE_URL = "https://prices.shufersal.co.il/"
CATEGORY = {
    FileType.PRICE: 1,
    FileType.PRICE_FULL: 2,
    FileType.PROMO: 3,
    FileType.PROMO_FULL: 4,
    FileType.STORES: 5,
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


def parse_listing(page_html: str, base_url: str = BASE_URL) -> list[tuple[str, str]]:
    """Return [(file_name, absolute_url)] from one listing page.

    Deliberately loose: any link to a .gz/.xml/.zip file counts. Browsers insert
    <tbody> into tables but the raw HTML may not have one, so we don't rely on
    the table structure at all.
    """
    doc = lxml_html.fromstring(page_html)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in doc.xpath("//a[@href]"):
        href = (a.get("href") or "").strip()
        url = urljoin(base_url, href)
        name = urlparse(url).path.rsplit("/", 1)[-1]
        if not name.lower().endswith((".gz", ".xml", ".zip")):
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append((name, url))
    return out


def last_page(page_html: str) -> int:
    doc = lxml_html.fromstring(page_html)
    pages = [1]
    for href in doc.xpath('//*[@id="gridContainer"]//tfoot//a/@href'):
        for part in href.replace("?", "&").split("&"):
            if part.startswith("page="):
                try:
                    pages.append(int(part[5:]))
                except ValueError:
                    pass
    return max(pages)


class ShufersalSource(Source):
    def __init__(self, chain: ChainInfo, timeout: int = 60, retries: int = 3):
        super().__init__(chain, timeout, retries)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        def call():
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            return r
        return self.with_retries(f"GET {url}", call)

    def _list(self, cat: int, store_id: int | None) -> list[RemoteFile]:
        url = urljoin(BASE_URL, "FileObject/UpdateCategory")
        params: dict = {"catID": cat}
        if store_id is not None:
            params["storeId"] = store_id
        first = self._get(url, params).text
        pages = [first]
        # a single store's listing fits on one page; the full listing does not
        if store_id is None:
            for p in range(2, min(last_page(first), 50) + 1):
                pages.append(self._get(url, {**params, "page": p}).text)
        files = []
        links = 0
        for page in pages:
            for name, link in parse_listing(page):
                links += 1
                rf = self._remote(name, link)
                if rf:
                    files.append(rf)
                else:
                    log.debug("shufersal: unrecognised file name %s", name)
        if not files:
            snippet = " ".join(first.split())[:600]
            log.warning("shufersal: catID=%s storeId=%s -> %d links, 0 usable files. Page starts: %s",
                        cat, store_id, links, snippet)
        return files

    def list_files(self, file_type: FileType, store_ids: Iterable[int] | None = None) -> list[RemoteFile]:
        cat = CATEGORY[file_type]
        if file_type is FileType.STORES or store_ids is None:
            return [f for f in self._list(cat, None) if f.meta.file_type is file_type]
        out: list[RemoteFile] = []
        for sid in store_ids:
            out += [f for f in self._list(cat, sid) if f.meta.file_type is file_type and f.meta.store_id == sid]
        return out

    def download(self, f: RemoteFile) -> bytes:
        return self._get(f.url).content

    def close(self) -> None:
        self.session.close()
