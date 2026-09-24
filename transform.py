import duckdb
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("transform.log"),
              logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

DB_PATH = "emissions.duckdb"

# vehicle_type is not a column in either trip table -- it is determined by
# which table you are in, so each table carries its lookup key as a literal.
TABLES = {
    "yellow_trips": "yellow_taxi",
    "green_trips": "green_taxi",
}

NEW_COLUMNS = {
    "trip_co2_kgs": "DOUBLE",
    "avg_mph": "DOUBLE",
    "hour_of_day": "INTEGER",
    "day_of_week": "INTEGER",
    "week_of_year": "INTEGER",
    "month_of_year": "INTEGER",
}


def add_columns(con, table):
    for column, dtype in NEW_COLUMNS.items():
        con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {dtype}")
    logger.info(f"{table}: ensured columns {list(NEW_COLUMNS)} exist")


def update_trip_co2(con, table, vehicle_type):
    # Rate is looked up from vehicle_emissions at run time, never hard-coded.
    con.execute(f"""
        UPDATE {table}
        SET trip_co2_kgs = (
            SELECT ({table}.trip_distance * ve.co2_grams_per_mile) / 1000.0
            FROM vehicle_emissions ve
            WHERE ve.vehicle_type = '{vehicle_type}'
        )
    """)
    logger.info(f"{table}: trip_co2_kgs calculated from vehicle_emissions ('{vehicle_type}')")


def update_avg_mph(con, table):
    con.execute(f"""
        UPDATE {table}
        SET avg_mph = trip_distance /
            (date_diff('second', pickup_time, dropoff_time) / 3600.0)
    """)
    logger.info(f"{table}: avg_mph calculated")


def update_date_parts(con, table):
    con.execute(f"""
        UPDATE {table} SET
            hour_of_day   = date_part('hour', pickup_time),
            day_of_week   = date_part('dow', pickup_time),
            week_of_year  = date_part('week', pickup_time),
            month_of_year = date_part('month', pickup_time)
    """)
    logger.info(f"{table}: hour_of_day, day_of_week, week_of_year, month_of_year extracted")


def verify_table(con, table):
    rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    logger.info(f"{table}: {rows} rows transformed")

    for column in NEW_COLUMNS:
        nulls = con.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL").fetchone()[0]
        logger.info(f"VERIFY {table}: {column} has {nulls} NULLs")

        # An all-NULL column means the UPDATE never reached the rows.
        if rows > 0 and nulls == rows:
            raise ValueError(f"{table}.{column} is entirely NULL after transform")


def transform_table(con, table, vehicle_type):
    add_columns(con, table)
    update_trip_co2(con, table, vehicle_type)
    update_avg_mph(con, table)
    update_date_parts(con, table)
    verify_table(con, table)


def transform_trips():
    con = None

    try:
        con = duckdb.connect(database=DB_PATH, read_only=False)
        logger.info("Connected to DuckDB instance")

        for table, vehicle_type in TABLES.items():
            transform_table(con, table, vehicle_type)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        if con is not None:
            con.close()
            logger.info("Closed DuckDB connection")


if __name__ == "__main__":
    transform_trips()
