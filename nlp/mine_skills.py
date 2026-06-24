"""Phase 3a: Mine candidate skill terms from job descriptions via TF-IDF.

Reads descriptions from the warehouse, cleans them, ranks unigram/bigram
candidates by TF-IDF mass, and writes the top terms to nlp/skills.txt for
manual curation. Edit that file in place afterward: delete non-skills, keep
the real ones. Do not re-run after curating (it overwrites the file).
"""
import os
import re
import html
from pathlib import Path

import numpy as np
import psycopg2
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "nlp" / "skills.txt"

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "jobmarket"),
    user=os.getenv("DB_USER", "jobmarket"),
    password=os.getenv("DB_PASSWORD", "jobmarket"),
)

TAG_RE = re.compile(r"<[^>]+>")

# Obvious generic phrases to pre-filter so the candidate list is cleaner.
# Not exhaustive on purpose - you curate the rest by hand.
GENERIC = {
    "years experience", "year experience", "fast paced", "team member",
    "equal opportunity", "full time", "part time", "strong understanding",
    "work environment", "ability work", "communication skills", "team members",
    "problem solving", "best practices", "cross functional", "high quality",
    "experience working", "looking for", "join team", "click apply",
    "san francisco", "new york", "united states", "highly motivated",
    "detail oriented", "fast growing", "remote work", "health insurance",
    "paid time", "time off", "competitive salary", "professional development",
    "bachelor degree", "related field", "minimum years", "preferred qualifications",
}


def clean(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = TAG_RE.sub(" ", text)
    return text.lower()


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT description FROM fact_posting WHERE description IS NOT NULL AND is_duplicate = FALSE")
    docs = [clean(r[0]) for r in cur.fetchall()]
    cur.close()
    conn.close()

    lengths = [len(d) for d in docs if d]
    print(f"{len(docs)} descriptions")
    print(
        f"description length (chars): mean={np.mean(lengths):.0f}  "
        f"median={np.median(lengths):.0f}  max={max(lengths)}"
    )
    if np.median(lengths) < 300:
        print("  ! descriptions look truncated - skill signal will be sparse but usable")

    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
        min_df=10,
        max_df=0.6,
        token_pattern=r"[a-zA-Z][a-zA-Z0-9+.#/-]+",
    )
    X = vec.fit_transform(docs)
    terms = np.array(vec.get_feature_names_out())
    doc_freq = np.asarray((X > 0).sum(axis=0)).ravel()
    mass = np.asarray(X.sum(axis=0)).ravel()
    order = mass.argsort()[::-1]

    candidates = []
    for i in order:
        t = terms[i]
        if t in GENERIC:
            continue
        candidates.append((t, int(doc_freq[i])))
        if len(candidates) >= 150:
            break

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        for t, _ in candidates:
            f.write(t + "\n")

    print("\nTop 60 candidate terms (term | #postings containing it):")
    for t, dfc in candidates[:60]:
        print(f"  {t:<30} {dfc}")
    print(f"\nWrote {len(candidates)} candidates to {OUT_PATH}")
    print("Now open nlp/skills.txt, delete the non-skills, keep the real ones, save.")


if __name__ == "__main__":
    main()