"""Registry of supported chains. Adding a Cerberus chain is one line."""

from __future__ import annotations

from .base import ChainInfo, Source, latest_per_store
from .cerberus import CerberusSource
from .shufersal import ShufersalSource

CHAINS: dict[str, ChainInfo] = {
    c.key: c
    for c in [
        ChainInfo("shufersal", "7290027600007", "שופרסל", "Shufersal"),
        ChainInfo("rami_levy", "7290058140886", "רמי לוי", "Rami Levy"),
        ChainInfo("osher_ad", "7290103152017", "אושר עד", "Osher Ad"),
        ChainInfo("yohananof", "7290803800003", "יוחננוף", "Yohananof"),
        ChainInfo("tiv_taam", "7290873255550", "טיב טעם", "Tiv Taam"),
    ]
}

# public Cerberus usernames, published by the chains themselves
CERBERUS_USERS: dict[str, tuple[str, str]] = {
    "rami_levy": ("RamiLevi", ""),
    "osher_ad": ("osherad", ""),
    "yohananof": ("yohananof", ""),
    "tiv_taam": ("TivTaam", ""),
}


def make_source(key: str, timeout: int = 60, retries: int = 3) -> Source:
    chain = CHAINS[key]
    if key == "shufersal":
        return ShufersalSource(chain, timeout=timeout, retries=retries)
    if key in CERBERUS_USERS:
        user, pwd = CERBERUS_USERS[key]
        return CerberusSource(chain, user, pwd, timeout=timeout, retries=retries)
    raise KeyError(f"no source implemented for chain {key!r}")


__all__ = ["CHAINS", "ChainInfo", "Source", "latest_per_store", "make_source"]
