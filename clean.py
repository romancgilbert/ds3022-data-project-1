import duckdb
import logging

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
    filename='clean.log'
)
logger = logging.getLogger(__name__)

DB_PATH = "emissions.duckdb"
TRIP_TABLES = ["yellow_trips", "green_trips"]

# Each rule pairs a label with the WHERE clause that matches offending rows,
# so the same code can delete them and then verify they are gone.
CLEANING_RULES = [
    ("trips with 0 passengers", "passenger_count = 0"),
    ("trips 0 miles in length", "trip_distance = 0"),
    ("trips longer than 100 miles", "trip_distance > 100"),
    ("trips lasting more than 1 day",
     "date_diff('second', pickup_time, dropoff_time) > 86400"),
]

# A trip is a duplicate only when every column matches; this data has no trip ID.
TRIP_COLUMNS = "VendorID, pickup_time, dropoff_time, passenger_count, trip_distance"


def report(message):
    print(message)
    logger.info(message)


def count_duplicates(con, table):
    total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    unique = con.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {table})").fetchone()[0]
    return total - unique


def count_matching(con, table, condition):
    return con.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}").fetchone()[0]


def remove_matching(con, table, label, condition):
    report(f"Before cleaning, {table} has {count_matching(con, table, condition)} {label}")
    con.execute(f"DELETE FROM {table} WHERE {condition}")
    report(f"After delete (verify): {count_matching(con, table, condition)}")


def remove_duplicates(con, table):
    report(f"Before cleaning, {table} has {count_duplicates(con, table)} duplicate trips")

    # ROW_NUMBER numbers each copy of a trip within its partition; keeping only
    # copy_number = 1 keeps one of each and drops the rest.
    con.execute(f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT * EXCLUDE (copy_number) FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY {TRIP_COLUMNS}
                ORDER BY pickup_time
            ) AS copy_number
            FROM {table}
        ) WHERE copy_number = 1
    """)

    report(f"After delete (verify): {count_duplicates(con, table)}")


def verify_table(con, table):
    remaining = [("duplicate trips", count_duplicates(con, table))]
    remaining += [
        (label, count_matching(con, table, condition))
        for label, condition in CLEANING_RULES
    ]

    for label, count in remaining:
        report(f"VERIFY {table}: {count} {label} remaining")

    if any(count > 0 for _, count in remaining):
        raise ValueError(f"{table} still contains rows that should have been cleaned")

    report(f"VERIFY {table}: all conditions cleared, {count_matching(con, table, 'TRUE')} rows remain")


def clean_trips():
    con = None

    try:
        con = duckdb.connect(database=DB_PATH, read_only=False)
        logger.info("Connected to DuckDB instance")

        for table in TRIP_TABLES:
            # Cheap filters run first so the expensive dedupe scans fewer rows.
            for label, condition in CLEANING_RULES:
                remove_matching(con, table, label, condition)
            remove_duplicates(con, table)

        for table in TRIP_TABLES:
            verify_table(con, table)

    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        if con is not None:
            con.close()
            logger.info("Closed DuckDB connection")


if __name__ == "__main__":
    clean_trips()
