"""Run all analytics jobs. Needs the dbt marts, so run `dbt build` first."""

from __future__ import annotations

import logging

from ..config import Settings
from ..db.connection import Database
from . import anomalies, forecast

log = logging.getLogger(__name__)


def run_all(settings: Settings) -> None:
    with Database(settings.database_url or "") as db:
        n_anom = anomalies.detect(db)
        n_fc = forecast.run(db)
    log.info("analytics done: %d anomalies, %d forecast points", n_anom, n_fc)
