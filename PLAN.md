# My Plan — DS3022 Data Project 1

## Stage 0 — Setup
- `pip install -r requirements.txt` (duckdb, pandas, dbt-duckdb)
- Table strategy: two trip tables (`yellow_trips`, `green_trips`) since Yellow/Green parquet schemas differ slightly (Green uses `lpep_*`, Yellow uses `tpep_*` pickup/dropoff columns), plus one `vehicle_emissions` lookup table.

## Stage 1 — load.py
- Connect to a persistent local `emissions.duckdb`.
- Programmatically build the 12 monthly URLs per color from the NYC TLC site (loop `01`-`12`, no hardcoded per-month INSERTs).
- `CREATE TABLE` once with an explicit schema (only needed columns), then loop `INSERT INTO ... SELECT ... FROM read_parquet(url)` per month.
- Load `data/vehicle_emissions.csv` into a `vehicle_emissions` table.
- Log + print raw row counts per table before cleaning.
- Wrap in try/except, log to `load.log`, use `if __name__ == "__main__":`.

## Stage 2 — clean.py
- Connect to the same `emissions.duckdb`.
- For each trip table: remove duplicates, 0-passenger trips, 0-mile trips, trips >100 miles, trips lasting >86400 seconds.
- Add verification queries afterward that assert none of these conditions remain; log results to `clean.log`.

## Stage 3 — transform.py
- Add derived columns (via `CREATE OR REPLACE TABLE ... AS SELECT` in one pass):
  - `trip_co2_kgs` (dynamic join/lookup against `vehicle_emissions`, not hardcoded)
  - `avg_mph`
  - `hour_of_day`, `day_of_week`, `week_of_year`, `month_of_year` via DuckDB `date_part`/`extract`
- Log to `transform.log`.
- Note near top of file whether DBT was used for the extra 6 points.
- (Optional, +6 pts) Mirror this logic as DBT models in `dbt/models/`, using `dbt/profiles.yml` pointing at `emissions.duckdb`.

## Stage 4 — analysis.py
Six labeled outputs, computed separately for YELLOW and GREEN:
1. Max `trip_co2_kgs` trip
2. Avg CO2 by `hour_of_day` -> highest/lowest
3. Avg CO2 by `day_of_week` -> highest/lowest
4. Avg CO2 by `week_of_year` -> highest/lowest
5. Avg CO2 by `month_of_year` -> highest/lowest
6. Matplotlib plot: month on X, total CO2 on Y, one series per color -> save PNG to repo
- Log to `analysis.log`.

## Stage 5 — Housekeeping
- `.gitignore` for `*.duckdb`, `*.duckdb.wal`, `*.log`, `*.parquet`, `__pycache__/`, `.venv` (DB/log/parquet files must not be committed).
- Test end-to-end: `load.py` -> `clean.py` -> `transform.py` -> `analysis.py`.
- Commit + push to my fork.

## Optional stretch (+5 pts)
- Extend the year loop from 2015-2024 instead of just 2024, once the 2024-only pipeline works.
