"""Find suspicious prices.

1. **Within-chain outliers** — one branch prices a barcode very differently
   from the chain's other branches. We compare inside a chain on purpose:
   chains have different price levels (that's the cross-chain comparison in
   the marts, not an anomaly), but branches of one chain should agree, so a
   gap there is usually a file error or a local price change worth flagging.
   Robust z-score (median / MAD), so one extreme price can't hide itself by
   inflating the spread.
2. **Jumps** — a single change of more than ±30% within the last 7 days.

Both are typical data-quality *and* business signals: a typo in a chain's
file, or a real price hike worth reporting.
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

Z_THRESHOLD = 3.5        # Iglewicz & Hoaglin's recommended cut-off for modified z-scores
MIN_RELATIVE_GAP = 0.25  # and at least 25% away from the median, so tiny MADs don't flag noise
MIN_PEERS = 3
JUMP_PCT = 30.0


def robust_outliers(prices: pd.DataFrame) -> pd.DataFrame:
    """prices: columns chain_id, store_id, product_key, price → flagged rows.

    Peers = the same product in the other branches of the SAME chain.
    """
    if prices.empty:
        return prices.assign(peer_median=[], peer_count=[], robust_z=[], kind=[])
    keys = ["chain_id", "product_key"]
    g = prices.groupby(keys)["price"]
    df = prices.assign(
        peer_median=g.transform("median"),
        peer_count=g.transform("count"),
    )
    df["abs_dev"] = (df["price"] - df["peer_median"]).abs()
    mad = df.groupby(keys)["abs_dev"].transform("median")
    # MAD can be 0 when most stores share one price; fall back to mean abs deviation
    mean_ad = df.groupby(keys)["abs_dev"].transform("mean")
    scale = mad.where(mad > 0, mean_ad * 1.2533)
    df["robust_z"] = np.where(scale > 0, 0.6745 * (df["price"] - df["peer_median"]) / scale, 0.0)
    rel_gap = (df["price"] / df["peer_median"] - 1).abs()
    flagged = df[(df["peer_count"] >= MIN_PEERS) & (df["robust_z"].abs() >= Z_THRESHOLD) & (rel_gap >= MIN_RELATIVE_GAP)]
    flagged = flagged.assign(kind=np.where(flagged["robust_z"] > 0, "overpriced", "underpriced"))
    return flagged.drop(columns=["abs_dev"])


def detect(db, today: date | None = None) -> int:
    today = today or date.today()
    rows = db.query(
        """SELECT f.chain_id, f.store_id, f.product_key, f.regular_price
           FROM marts.fct_current_price f
           JOIN marts.dim_product p USING (product_key)
           WHERE p.is_barcode AND NOT p.is_weighted"""
    )
    prices = pd.DataFrame(rows, columns=["chain_id", "store_id", "product_key", "price"])
    prices["price"] = prices["price"].astype(float)
    out = robust_outliers(prices)

    jumps = db.query(
        """SELECT chain_id, store_id, product_key, new_price, previous_price, pct_change
           FROM marts.fct_price_changes
           WHERE change_date > current_date - 7 AND abs(pct_change) >= %s""",
        (JUMP_PCT,),
    )

    records = [
        (today, r.chain_id, int(r.store_id), r.product_key, round(r.price, 2), round(r.peer_median, 2),
         int(r.peer_count), round(float(r.robust_z), 2), r.kind)
        for r in out.itertuples()
    ]
    records += [
        (today, j[0], int(j[1]), j[2], float(j[3]), float(j[4]), 1, float(j[5]), "jump")
        for j in jumps
    ]
    with db.transaction():
        db.execute("DELETE FROM analytics.price_anomalies WHERE detected_on = %s", (today,))
        db.copy_rows(
            "analytics.price_anomalies",
            ["detected_on", "chain_id", "store_id", "product_key", "item_price", "peer_median",
             "peer_count", "robust_z", "kind"],
            records,
        )
    log.info("anomalies: %d within-chain outliers, %d jumps", len(out), len(jumps))
    return len(records)
