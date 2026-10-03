"""Forecast each chain's basket price index 14 days ahead.

Model: Holt's linear exponential smoothing with a *damped* trend (Gardner &
McKenzie, 1985), implemented in numpy so it runs anywhere. Parameters are
chosen by grid search on one-step-ahead error, and every model is compared
against a naive "tomorrow = today" baseline with a rolling-origin backtest —
if it can't beat naive, we say so in analytics.model_backtest.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

HORIZON = 14
MIN_POINTS = 21
GRID = np.round(np.linspace(0.05, 0.95, 10), 3)
PHIS = (0.8, 0.9, 0.98)


@dataclass
class HoltFit:
    alpha: float
    beta: float
    phi: float
    level: float
    trend: float
    sse: float
    resid_std: float

    def forecast(self, h: int) -> np.ndarray:
        steps = np.arange(1, h + 1)
        damp = np.cumsum(self.phi ** steps)
        return self.level + damp * self.trend


def _run(y: np.ndarray, alpha: float, beta: float, phi: float) -> tuple[float, float, np.ndarray]:
    level, trend = y[0], y[1] - y[0]
    errors = np.empty(len(y) - 1)
    for t in range(1, len(y)):
        pred = level + phi * trend
        errors[t - 1] = y[t] - pred
        new_level = alpha * y[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, errors


def fit_holt(y: np.ndarray) -> HoltFit:
    best: HoltFit | None = None
    for a, b, phi in itertools.product(GRID, GRID, PHIS):
        level, trend, err = _run(y, a, b, phi)
        sse = float(np.sum(err[1:] ** 2))  # skip the first, initialisation-driven error
        if best is None or sse < best.sse:
            best = HoltFit(a, b, phi, level, trend, sse, float(np.std(err[1:], ddof=1)) if len(err) > 2 else 0.0)
    assert best is not None
    return best


def backtest(y: np.ndarray, horizon: int = 7, min_train: int = 14) -> dict[str, float]:
    """Rolling-origin evaluation, horizon-step ahead, vs the naive forecast."""
    errs_model, errs_naive, apes = [], [], []
    for origin in range(min_train, len(y) - horizon + 1):
        train, actual = y[:origin], y[origin + horizon - 1]
        pred = fit_holt(train).forecast(horizon)[-1]
        errs_model.append(abs(actual - pred))
        errs_naive.append(abs(actual - train[-1]))
        apes.append(abs(actual - pred) / abs(actual) if actual else np.nan)
    if not errs_model:
        return {}
    return {
        "holt_damped_mae": float(np.mean(errs_model)),
        "naive_mae": float(np.mean(errs_naive)),
        "holt_damped_mape": float(np.nanmean(apes) * 100),
        "n": len(errs_model),
    }


def run(db) -> int:
    rows = db.query("SELECT chain_id, day, price_index FROM marts.mart_basket_index_daily ORDER BY chain_id, day")
    df = pd.DataFrame(rows, columns=["chain_id", "day", "price_index"])
    if df.empty:
        log.info("forecast: no index data yet")
        return 0
    df["price_index"] = df["price_index"].astype(float)
    df["day"] = pd.to_datetime(df["day"])

    forecasts, metrics = [], []
    for chain_id, g in df.groupby("chain_id"):
        series = g.set_index("day")["price_index"].asfreq("D").ffill()
        y = series.to_numpy()
        if len(y) < MIN_POINTS:
            log.info("forecast: %s has %d days (< %d) — skipping until more history accumulates",
                     chain_id, len(y), MIN_POINTS)
            continue
        fit = fit_holt(y)
        yhat = fit.forecast(HORIZON)
        last_day = series.index[-1].date()
        for h, v in enumerate(yhat, start=1):
            band = 1.96 * fit.resid_std * np.sqrt(h)
            forecasts.append((chain_id, last_day + timedelta(days=h), h, round(float(v), 3),
                              round(float(v - band), 3), round(float(v + band), 3), "holt_damped"))
        bt = backtest(y)
        if bt:
            metrics.append((chain_id, "holt_damped", round(bt["holt_damped_mae"], 4), round(bt["holt_damped_mape"], 4), bt["n"]))
            metrics.append((chain_id, "naive", round(bt["naive_mae"], 4), None, bt["n"]))
            log.info("forecast %s: α=%.2f β=%.2f φ=%.2f  backtest MAE %.3f vs naive %.3f",
                     chain_id, fit.alpha, fit.beta, fit.phi, bt["holt_damped_mae"], bt["naive_mae"])

    with db.transaction():
        db.execute("DELETE FROM analytics.index_forecast")
        db.copy_rows("analytics.index_forecast",
                     ["chain_id", "target_date", "horizon_days", "yhat", "yhat_lower", "yhat_upper", "model"],
                     forecasts)
        db.execute("DELETE FROM analytics.model_backtest")
        db.copy_rows("analytics.model_backtest", ["chain_id", "model", "mae", "mape", "n_points"], metrics)
    return len(forecasts)
