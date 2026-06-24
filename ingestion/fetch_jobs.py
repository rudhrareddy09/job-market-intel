"""Phase 1: Ingest job postings from the Adzuna API into raw JSON."""
import os
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

COUNTRY = "us"
BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# Roles to track. Each term becomes a separate search.
SEARCH_TERMS = [
    "data engineer",
    "data analyst",
    "data scientist",
    "machine learning engineer",
    "analytics engineer",
]

WHERE = ""              # e.g. "California"; empty = whole country
RESULTS_PER_PAGE = 50   # Adzuna max per page
PAGES_PER_TERM = 5      # bump up later for a bigger corpus
SLEEP_SECONDS = 1.5     # be polite to the free-tier rate limit

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_page(term, page):
    url = BASE_URL.format(country=COUNTRY, page=page)
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "what": term,
        "results_per_page": RESULTS_PER_PAGE,
    }
    if WHERE:
        params["where"] = WHERE
    resp = requests.get(
        url, params=params, headers={"Accept": "application/json"}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def main():
    if not APP_ID or not APP_KEY:
        raise SystemExit("Missing ADZUNA_APP_ID / ADZUNA_APP_KEY — check your .env file.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    seen_ids = set()
    all_postings = []

    for term in SEARCH_TERMS:
        print(f"Fetching: {term}")
        term_count = 0
        for page in range(1, PAGES_PER_TERM + 1):
            try:
                data = fetch_page(term, page)
            except requests.HTTPError as e:
                print(f"  ! page {page} failed: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for r in results:
                job_id = r.get("id")
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                r["_search_term"] = term
                all_postings.append(r)
                term_count += 1

            time.sleep(SLEEP_SECONDS)
        print(f"  -> {term_count} new postings")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RAW_DIR / f"adzuna_{stamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_postings, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(all_postings)} unique postings to {out_path}")


if __name__ == "__main__":
    main()