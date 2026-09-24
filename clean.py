import duckdb
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("clean.log"),
              logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

DB_PATH = "emissions.duckdb"
TABLES = ("yellow_trips", "green_trips")


def remove_duplicates(con, table):
    before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    logger.info(f"{table} raw row count: {before}")

    con.execute(f"""
        CREATE TABLE {table}_clean AS
        SELECT DISTINCT * FROM {table};
        DROP TABLE {table};
        ALTER TABLE {table}_clean RENAME TO {table};
    """)

    after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    distinct = con.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {table})").fetchone()[0]
    logger.info(f"{table} after dedupe: {after} (verify: distinct count = {distinct})")


def remove_zero_passengers(con, table):
    before = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE passenger_count = 0
    """).fetchone()[0]
    logger.info(f"{table} before delete (0 passengers): {before}")

    con.execute(f"DELETE FROM {table} WHERE passenger_count = 0")

    after = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE passenger_count = 0
    """).fetchone()[0]
    logger.info(f"{table} after delete (verify): {after}")


def remove_zero_mile_trips(con, table):
    before = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE trip_distance = 0
    """).fetchone()[0]
    logger.info(f"{table} before delete (0 miles): {before}")

    con.execute(f"DELETE FROM {table} WHERE trip_distance = 0")

    after = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE trip_distance = 0
    """).fetchone()[0]
    logger.info(f"{table} after delete (verify): {after}")


def remove_long_distance_trips(con, table):
    before = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE trip_distance > 100
    """).fetchone()[0]
    logger.info(f"{table} before delete (>100 miles): {before}")

    con.execute(f"DELETE FROM {table} WHERE trip_distance > 100")

    after = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE trip_distance > 100
    """).fetchone()[0]
    logger.info(f"{table} after delete (verify): {after}")


def remove_long_duration_trips(con, table):
    before = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE date_diff('second', pickup_time, dropoff_time) > 86400
    """).fetchone()[0]
    logger.info(f"{table} before delete (>1 day): {before}")

    con.execute(f"""
        DELETE FROM {table}
        WHERE date_diff('second', pickup_time, dropoff_time) > 86400
    """)

    after = con.execute(f"""
        SELECT COUNT(*) FROM {table}
        WHERE date_diff('second', pickup_time, dropoff_time) > 86400
    """).fetchone()[0]
    logger.info(f"{table} after delete (verify): {after}")


def clean_table(con, table):
    remove_duplicates(con, table)
    remove_zero_passengers(con, table)
    remove_zero_mile_trips(con, table)
    remove_long_distance_trips(con, table)
    remove_long_duration_trips(con, table)

    final = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    logger.info(f"{table} final row count: {final}")


def clean_trips():
    con = None

    try:
        con = duckdb.connect(database=DB_PATH, read_only=False)
        logger.info("Connected to DuckDB instance")

        for table in TABLES:
            clean_table(con, table)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        if con is not None:
            con.close()
            logger.info("Closed DuckDB connection")


if __name__ == "__main__":
    clean_trips()
