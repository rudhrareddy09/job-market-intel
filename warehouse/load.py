"""Phase 2: Load raw Adzuna JSON into the Postgres warehouse."""
import os
import json
import glob
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SCHEMA_PATH = ROOT / "warehouse" / "schema.sql"

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "jobmarket"),
    user=os.getenv("DB_USER", "jobmarket"),
    password=os.getenv("DB_PASSWORD", "jobmarket"),
)


def latest_raw_file():
    files = sorted(glob.glob(str(RAW_DIR / "adzuna_*.json")))
    if not files:
        raise SystemExit("No raw files found - run ingestion/fetch_jobs.py first.")
    return files[-1]


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def to_bool(value):
    return str(value) == "1"


def main():
    raw_path = latest_raw_file()
    with open(raw_path, encoding="utf-8") as f:
        postings = json.load(f)
    print(f"Loaded {len(postings)} postings from {Path(raw_path).name}")

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(SCHEMA_PATH.read_text())

    companies = set()
    locations = {}
    categories = {}

    for p in postings:
        comp = (p.get("company") or {}).get("display_name")
        if comp:
            companies.add(comp)
        loc = p.get("location") or {}
        loc_name = loc.get("display_name")
        if loc_name:
            area = loc.get("area") or []
            locations[loc_name] = area[1] if len(area) > 1 else None
        cat = p.get("category") or {}
        tag = cat.get("tag")
        if tag:
            categories[tag] = cat.get("label")

    execute_values(
        cur,
        "INSERT INTO dim_company (name) VALUES %s ON CONFLICT (name) DO NOTHING",
        [(c,) for c in companies],
    )
    execute_values(
        cur,
        "INSERT INTO dim_location (display_name, region) VALUES %s "
        "ON CONFLICT (display_name) DO NOTHING",
        [(name, region) for name, region in locations.items()],
    )
    execute_values(
        cur,
        "INSERT INTO dim_category (tag, label) VALUES %s ON CONFLICT (tag) DO NOTHING",
        [(tag, label) for tag, label in categories.items()],
    )

    cur.execute("SELECT company_id, name FROM dim_company")
    company_map = {name: cid for cid, name in cur.fetchall()}
    cur.execute("SELECT location_id, display_name FROM dim_location")
    location_map = {name: lid for lid, name in cur.fetchall()}
    cur.execute("SELECT category_id, tag FROM dim_category")
    category_map = {tag: cid for cid, tag in cur.fetchall()}

    fact_rows = []
    for p in postings:
        comp = (p.get("company") or {}).get("display_name")
        loc_name = (p.get("location") or {}).get("display_name")
        tag = (p.get("category") or {}).get("tag")
        fact_rows.append((
            str(p.get("id")),
            p.get("title"),
            p.get("description"),
            company_map.get(comp),
            location_map.get(loc_name),
            category_map.get(tag),
            p.get("salary_min"),
            p.get("salary_max"),
            to_bool(p.get("salary_is_predicted")),
            p.get("contract_type"),
            p.get("contract_time"),
            p.get("_search_term"),
            parse_date(p.get("created")),
            p.get("latitude"),
            p.get("longitude"),
            p.get("redirect_url"),
        ))

    execute_values(
        cur,
        """
        INSERT INTO fact_posting (
            posting_id, title, description, company_id, location_id, category_id,
            salary_min, salary_max, salary_is_predicted, contract_type,
            contract_time, search_term, created_date, latitude, longitude, redirect_url
        ) VALUES %s
        ON CONFLICT (posting_id) DO NOTHING
        """,
        fact_rows,
    )

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM fact_posting")
    print(f"fact_posting: {cur.fetchone()[0]} rows")
    cur.execute("SELECT COUNT(*) FROM dim_company")
    print(f"dim_company:  {cur.fetchone()[0]} rows")
    cur.execute("SELECT COUNT(*) FROM dim_location")
    print(f"dim_location: {cur.fetchone()[0]} rows")
    cur.execute("SELECT COUNT(*) FROM dim_category")
    print(f"dim_category: {cur.fetchone()[0]} rows")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
