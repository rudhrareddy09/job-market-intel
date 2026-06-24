DROP TABLE IF EXISTS fact_posting CASCADE;
DROP TABLE IF EXISTS dim_company CASCADE;
DROP TABLE IF EXISTS dim_location CASCADE;
DROP TABLE IF EXISTS dim_category CASCADE;

CREATE TABLE dim_company (
    company_id   SERIAL PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_location (
    location_id  SERIAL PRIMARY KEY,
    display_name TEXT UNIQUE NOT NULL,
    region       TEXT
);

CREATE TABLE dim_category (
    category_id  SERIAL PRIMARY KEY,
    tag          TEXT UNIQUE NOT NULL,
    label        TEXT
);

CREATE TABLE fact_posting (
    posting_id          TEXT PRIMARY KEY,
    title               TEXT,
    description         TEXT,
    company_id          INTEGER REFERENCES dim_company(company_id),
    location_id         INTEGER REFERENCES dim_location(location_id),
    category_id         INTEGER REFERENCES dim_category(category_id),
    salary_min          NUMERIC,
    salary_max          NUMERIC,
    salary_is_predicted BOOLEAN,
    contract_type       TEXT,
    contract_time       TEXT,
    search_term         TEXT,
    created_date        DATE,
    latitude            NUMERIC,
    longitude           NUMERIC,
    redirect_url        TEXT,
    ingested_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_fact_company  ON fact_posting(company_id);
CREATE INDEX idx_fact_location ON fact_posting(location_id);
CREATE INDEX idx_fact_category ON fact_posting(category_id);
CREATE INDEX idx_fact_created  ON fact_posting(created_date);
CREATE INDEX idx_fact_term     ON fact_posting(search_term);
