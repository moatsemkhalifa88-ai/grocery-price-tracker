import numpy as np
import pandas as pd

from pricetracker.analytics.anomalies import robust_outliers
from pricetracker.analytics.forecast import backtest, fit_holt
from pricetracker.db.loader import product_key


def test_robust_outlier_flags_typo_price_only():
    prices = pd.DataFrame({
        "chain_id": ["a"] * 6,
        "store_id": range(6),
        "product_key": ["milk"] * 6,
        "price": [6.9, 6.9, 7.2, 6.5, 6.9, 69.0],   # last one: decimal-point typo
    })
    out = robust_outliers(prices)
    assert list(out["store_id"]) == [5]
    assert out.iloc[0]["kind"] == "overpriced"


def test_robust_outlier_needs_enough_peers():
    prices = pd.DataFrame({"chain_id": ["a"] * 2, "store_id": range(2),
                           "product_key": ["x"] * 2, "price": [5.0, 50.0]})
    assert robust_outliers(prices).empty


def test_pricier_chain_is_not_an_anomaly():
    """A premium chain charging more everywhere is a price level, not an error."""
    prices = pd.DataFrame({
        "chain_id": ["cheap"] * 4 + ["premium"] * 4,
        "store_id": range(8),
        "product_key": ["milk"] * 8,
        "price": [6.9, 6.9, 7.0, 6.9, 9.9, 9.9, 9.9, 10.0],
    })
    assert robust_outliers(prices).empty


def test_holt_tracks_a_linear_trend():
    y = 100 + 0.2 * np.arange(40)
    fc = fit_holt(y).forecast(5)
    assert abs(fc[0] - (y[-1] + 0.2)) < 0.15
    assert np.all(np.diff(fc) > 0)


def test_backtest_beats_naive_on_trending_series():
    rng = np.random.default_rng(0)
    y = 100 + 0.3 * np.arange(60) + rng.normal(0, 0.05, 60)
    bt = backtest(y)
    assert bt["holt_damped_mae"] < bt["naive_mae"]


def test_product_key_barcode_vs_internal():
    assert product_key("729", "7290000042640", 1) == ("7290000042640", True)
    assert product_key("729", "1234", 1) == ("729:1234", False)
    assert product_key("729", "7290000042640", 0) == ("729:7290000042640", False)
