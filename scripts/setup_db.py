"""Create the database and load schema.sql + routines.sql (+ seed.sql).

    python scripts/setup_db.py            # create the database if missing, load schema/routines if empty
    python scripts/setup_db.py --seed     # also load the demo data
    python scripts/setup_db.py --reset    # DROP everything in the database first, then load again

Uses DATABASE_URL (or .env), the same as the API.
"""
import argparse
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


def connect(url, dbname):
    return psycopg2.connect(host=url.host, port=url.port or 5432, user=url.username,
                            password=url.password, dbname=dbname)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="load seed.sql demo data")
    ap.add_argument("--reset", action="store_true", help="wipe the database first (destructive)")
    args = ap.parse_args()

    url = make_url(settings.database_url)
    dbname = url.database

    admin = connect(url, "postgres")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
            print(f"created database {dbname}")
    admin.close()

    conn = connect(url, dbname)
    with conn, conn.cursor() as cur:
        if args.reset:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            print("database wiped")
        cur.execute("SELECT to_regclass('public.booking') IS NOT NULL")
        if cur.fetchone()[0]:
            print("tables already exist, leaving schema alone (use --reset to rebuild)")
        else:
            cur.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))
            print("loaded schema.sql")
        # routines.sql has plain CREATE TRIGGER, which fails if it already ran: load it only once
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'book_flight')")
        if cur.fetchone()[0]:
            print("routines already installed, leaving them alone (use --reset to rebuild)")
        else:
            cur.execute((ROOT / "routines.sql").read_text(encoding="utf-8"))
            print("loaded routines.sql")
        # CREATE ... IF NOT EXISTS, safe to run every time
        cur.execute((ROOT / "auth.sql").read_text(encoding="utf-8"))
        print("loaded auth.sql (login accounts)")
        if args.seed:
            cur.execute("SELECT count(*) FROM operator")
            if cur.fetchone()[0]:
                print("seed skipped: operator table is not empty")
            else:
                cur.execute((ROOT / "seed.sql").read_text(encoding="utf-8"))
                print("loaded seed.sql")
    conn.close()


if __name__ == "__main__":
    main()
