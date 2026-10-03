"""Command line entry point:  python -m pricetracker <command>

  migrate            create / upgrade the database schema
  run                daily ingestion for all enabled chains (or --chain X)
  load FILE...       load transparency files already on disk
  analytics          anomaly detection + basket-index forecast (after dbt run)
  dbt ARGS...        run dbt with credentials taken from DATABASE_URL
  daily              run + dbt build + analytics + cleanup (what the scheduler calls)
  cleanup            delete raw files older than the retention window
  chains             list supported chains
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import PROJECT_ROOT, Settings


def _setup_logging(verbose: bool) -> None:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "pricetracker.log", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
    )
    for noisy in ("urllib3", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def dbt_env(database_url: str) -> dict[str, str]:
    """Translate DATABASE_URL into the DBT_* variables profiles.yml reads."""
    u = urlparse(database_url)
    env = dict(os.environ)
    env.update({
        "DBT_HOST": u.hostname or "localhost",
        "DBT_PORT": str(u.port or 5432),
        "DBT_USER": unquote(u.username or ""),
        "DBT_PASSWORD": unquote(u.password or ""),
        "DBT_DBNAME": (u.path or "/postgres").lstrip("/") or "postgres",
        # hosted Postgres (Neon, Supabase, ...) needs TLS; a local database usually doesn't
        "DBT_SSLMODE": "prefer" if (u.hostname or "localhost") in ("localhost", "127.0.0.1") else "require",
    })
    return env


def run_dbt(settings: Settings, args: list[str]) -> int:
    # prefer the dbt that sits next to this Python (the venv), even if not activated
    here = Path(sys.executable).parent
    local = [here / "dbt.exe", here / "dbt", here / "Scripts" / "dbt.exe"]
    exe = next((str(p) for p in local if p.exists()), None) or shutil.which("dbt")
    if exe is None:
        print("dbt is not installed — run: pip install -r requirements.txt", file=sys.stderr)
        return 1
    project = PROJECT_ROOT / "dbt"
    cmd = [exe, *args, "--project-dir", str(project), "--profiles-dir", str(project)]
    logging.getLogger("pricetracker.dbt").info("running: dbt %s", " ".join(args))
    return subprocess.call(cmd, env=dbt_env(settings.database_url or ""), cwd=project)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Hebrew in Windows terminals
    ap = argparse.ArgumentParser(prog="pricetracker", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--config", help="path to settings.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    r = sub.add_parser("run")
    r.add_argument("--chain", action="append", help="only this chain (repeatable)")
    ld = sub.add_parser("load")
    ld.add_argument("files", nargs="+", type=Path)
    ld.add_argument("--force", action="store_true", help="reprocess files already loaded")
    ld.add_argument("--type", choices=["PriceFull", "PromoFull", "Price", "Promo", "Stores"],
                    help="only files of this type")
    sub.add_parser("analytics")
    d = sub.add_parser("dbt")
    d.add_argument("dbt_args", nargs=argparse.REMAINDER)
    sub.add_parser("daily")
    sub.add_parser("cleanup")
    sub.add_parser("chains")
    args = ap.parse_args(argv)

    _setup_logging(args.verbose)
    settings = Settings.load(args.config)

    if args.cmd == "chains":
        from .sources import CHAINS
        for c in CHAINS.values():
            flag = "on " if c.key in settings.enabled_chains else "off"
            print(f"[{flag}] {c.key:<10} {c.chain_id}  {c.name_en} / {c.name_he}")
        return 0

    if args.cmd == "migrate":
        from .db.connection import Database
        from .db.migrate import migrate
        with Database(settings.database_url or "") as db:
            applied = migrate(db)
        print("applied:", ", ".join(applied) if applied else "nothing (up to date)")
        return 0

    if args.cmd == "run":
        from .pipeline import run
        stats = run(settings, args.chain)
        return 0 if stats.status != "failed" else 1

    if args.cmd == "load":
        from .pipeline import load_local
        files = []
        for p in args.files:
            files += sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
        if args.type:
            files = [f for f in files if f.name.lower().startswith(args.type.lower())
                     and not (args.type in ("Price", "Promo") and f.name.lower().startswith(args.type.lower() + "full"))]
        stats = load_local(settings, files, force=args.force)
        print(f"loaded {stats.loaded}, skipped {stats.skipped}, failed {stats.failed}, rows {stats.rows}")
        return 0 if stats.failed == 0 else 1

    if args.cmd == "analytics":
        from .analytics.run import run_all
        run_all(settings)
        return 0

    if args.cmd == "dbt":
        return run_dbt(settings, args.dbt_args or ["build"])

    if args.cmd == "daily":
        from .analytics.run import run_all
        from .pipeline import cleanup_raw, run
        log = logging.getLogger("pricetracker.daily")
        stats = run(settings)
        if stats.loaded == 0 and stats.failed:
            log.error("nothing loaded — skipping dbt and analytics")
            return 1
        if run_dbt(settings, ["seed"]) != 0 or run_dbt(settings, ["build"]) != 0:
            log.error("dbt failed — see logs/ and dbt/target/run_results.json")
            return 1
        run_all(settings)
        log.info("cleanup: removed %d old raw files", cleanup_raw(settings))
        return 0 if stats.status == "success" else 1

    if args.cmd == "cleanup":
        from .pipeline import cleanup_raw
        print(f"removed {cleanup_raw(settings)} raw files")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
