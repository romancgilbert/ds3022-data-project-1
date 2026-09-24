import duckdb, logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="analysis.log")
logger = logging.getLogger(__name__)

DB_PATH = "emissions.duckdb"
TABLES  = {"YELLOW": "yellow_trips", "GREEN": "green_trips"}

# date_part('dow') returns 0=Sunday through 6=Saturday.
DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday",
             "Thursday", "Friday", "Saturday"]

# month_of_year is 1-12, so index 0 is a placeholder that keeps the
# list aligned with the month number used to index it.
MONTH_NAMES = [None, "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def report(message):
    print(message)        # screen
    logger.info(message)  # + log


def largest_trip(con, label, table):
    row = con.execute(f"""
        SELECT trip_co2_kgs, trip_distance, pickup_time
        FROM {table}
        ORDER BY trip_co2_kgs DESC LIMIT 1
    """).fetchone()
    report(f"[{label}] Largest single-trip CO2 of 2024: "
           f"{row[0]:.2f} kg ({row[1]:.2f} mi, picked up {row[2]})")


def heaviest_lightest(con, label, table, column, description, names=None):
    rows = con.execute(f"""
        SELECT {column}, AVG(trip_co2_kgs) AS avg_co2
        FROM {table} GROUP BY {column} ORDER BY avg_co2 DESC
    """).fetchall()
    pretty = lambda v: names[int(v)] if names else v
    high, low = rows[0], rows[-1]
    report(f"[{label}] Most carbon-heavy {description}: "
           f"{pretty(high[0])} ({high[1]:.3f} kg avg/trip)")
    report(f"[{label}] Most carbon-light {description}: "
           f"{pretty(low[0])} ({low[1]:.3f} kg avg/trip)")


def monthly_plot(con, filename="co2_by_month_2024.png"):
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, table in TABLES.items():
        rows = con.execute(f"""
            SELECT month_of_year, SUM(trip_co2_kgs) AS total_co2
            FROM {table} GROUP BY month_of_year ORDER BY 1
        """).fetchall()
        months = [r[0] for r in rows]
        totals = [r[1] / 1000.0 for r in rows]   # kg -> tonnes
        ax.plot(months, totals, marker="o", label=f"{label} taxis")
    ax.set_xlabel("Month"); ax.set_ylabel("Total CO2 (tonnes)")
    ax.set_title("NYC Taxi CO2 Output by Month, 2024")
    ax.set_xticks(range(1, 13))
    ax.legend(); fig.savefig(filename, dpi=150)
    report(f"Plot written to {filename}")


def main():
    con = None
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        logger.info("Connected to DuckDB instance")

        for label, table in TABLES.items():
            largest_trip(con, label, table)
            heaviest_lightest(con, label, table, "hour_of_day",   "hour of day")
            heaviest_lightest(con, label, table, "day_of_week",   "day of week", DAY_NAMES)
            heaviest_lightest(con, label, table, "week_of_year",  "week of year")
            heaviest_lightest(con, label, table, "month_of_year", "month of year", MONTH_NAMES)
        monthly_plot(con)

    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"An error occurred: {e}")
        raise
    finally:
        if con is not None:
            con.close()
            logger.info("Closed DuckDB connection")


if __name__ == "__main__":
    main()
