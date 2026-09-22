import duckdb
import logging
import os
import shutil
import urllib.request

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
    filename='load.log'
)
logger = logging.getLogger(__name__)

DB_PATH = "emissions.duckdb"
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
PARQUET_DIR = os.path.join("data", "parquet")
VEHICLE_EMISSIONS_CSV = os.path.join("data", "vehicle_emissions.csv")
YEAR = 2024

# Yellow/Green parquet files use different pickup/dropoff column names,
# so each taxi type is normalized into a common trip table schema.
TAXI_CONFIG = {
    "yellow": {
        "table": "yellow_trips",
        "pickup_col": "tpep_pickup_datetime",
        "dropoff_col": "tpep_dropoff_datetime",
    },
    "green": {
        "table": "green_trips",
        "pickup_col": "lpep_pickup_datetime",
        "dropoff_col": "lpep_dropoff_datetime",
    },
}


def download_parquet(taxi_type, month):
    filename = f"{taxi_type}_tripdata_{YEAR}-{month:02d}.parquet"
    destination = os.path.join(PARQUET_DIR, filename)

    if os.path.exists(destination) and os.path.getsize(destination) > 0:
        return destination

    # Download to .part first so an interrupted run never leaves a truncated
    # file that the check above would treat as a complete download.
    partial = destination + ".part"
    try:
        with urllib.request.urlopen(f"{BASE_URL}/{filename}", timeout=120) as response:
            with open(partial, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
        os.replace(partial, destination)
    except Exception:
        if os.path.exists(partial):
            os.remove(partial)
        raise

    logger.info(f"Downloaded {filename}")
    return destination


def load_vehicle_emissions(con):
    con.execute(f"""
        CREATE OR REPLACE TABLE vehicle_emissions AS
        SELECT * FROM read_csv_auto('{VEHICLE_EMISSIONS_CSV}')
    """)
    row_count = con.execute("SELECT COUNT(*) FROM vehicle_emissions").fetchone()[0]
    logger.info(f"vehicle_emissions: {row_count} rows loaded")
    print(f"vehicle_emissions: {row_count} rows loaded")


def load_taxi_data(con, taxi_type, config):
    os.makedirs(PARQUET_DIR, exist_ok=True)

    # All 12 files are fetched before the table is replaced, so a failed
    # download cannot leave the table holding only part of the year.
    files = [download_parquet(taxi_type, month) for month in range(1, 13)]

    con.execute(f"""
        CREATE OR REPLACE TABLE {config['table']} (
            VendorID INTEGER,
            pickup_time TIMESTAMP,
            dropoff_time TIMESTAMP,
            passenger_count BIGINT,
            trip_distance DOUBLE
        )
    """)

    for month, path in enumerate(files, start=1):
        added = con.execute(f"""
            INSERT INTO {config['table']}
            SELECT
                VendorID,
                {config['pickup_col']} AS pickup_time,
                {config['dropoff_col']} AS dropoff_time,
                passenger_count,
                trip_distance
            FROM read_parquet('{path}')
        """).fetchone()[0]

        if added == 0:
            raise ValueError(f"{path} added 0 rows; check the URL or month index")

        logger.info(f"{config['table']}: loaded month {month:02d}/{YEAR}")

    row_count = con.execute(f"SELECT COUNT(*) FROM {config['table']}").fetchone()[0]
    logger.info(f"{config['table']}: {row_count} rows loaded (raw)")
    print(f"{config['table']}: {row_count} rows loaded (raw)")


def load_parquet_files():
    con = None

    try:
        con = duckdb.connect(database=DB_PATH, read_only=False)
        logger.info("Connected to DuckDB instance")

        load_vehicle_emissions(con)

        for taxi_type, config in TAXI_CONFIG.items():
            load_taxi_data(con, taxi_type, config)

    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        if con is not None:
            con.close()
            logger.info("Closed DuckDB connection")


if __name__ == "__main__":
    load_parquet_files()
