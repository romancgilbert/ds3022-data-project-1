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
    """Send one labelled result line to both the screen and analysis.log.

    The rubric asks for every answer to be printed and logged, so each result
    goes through here rather than calling print or logger directly.
    """
    print(message)        # screen
    logger.info(message)  # + log


def largest_trip(con, label, table):
    """Report the single highest-CO2 trip of the year for one cab type."""
    row = con.execute(f"""
        SELECT trip_co2_kgs, trip_distance, pickup_time
        FROM {table}
        ORDER BY trip_co2_kgs DESC LIMIT 1
    """).fetchone()
    report(f"[{label}] Largest single-trip CO2 of 2024: "
           f"{row[0]:.2f} kg ({row[1]:.2f} mi, picked up {row[2]})")


def heaviest_lightest(con, label, table, column, description, names=None):
    """Report the highest and lowest average-CO2 value of a grouping column.

    Used for all four groupings (hour, day, week, month). Pass `names` to
    print a label such as 'Sunday' instead of the raw number.
    """
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
    """Plot monthly CO2 totals for both cab types and save it as a PNG.

    Green output is only about 1.2% of yellow's, so the two series get their
    own stacked panels rather than a shared axis, where green would flatten
    against zero. Stacking them keeps each scale readable while sharing one
    x-axis; a second y-axis on a single panel was avoided because the
    distance between two differently-scaled lines carries no real meaning.

    Totals are divided by 1000 so the axes read in tonnes rather than
    millions of kilograms.
    """
    colours = {"YELLOW": "#D4A017", "GREEN": "#2E7D5B"}

    fig, axes = plt.subplots(
        len(TABLES), 1, figsize=(10, 7), sharex=True
    )

    for ax, (label, table) in zip(axes, TABLES.items()):
        rows = con.execute(f"""
            SELECT month_of_year, SUM(trip_co2_kgs) AS total_co2
            FROM {table} GROUP BY month_of_year ORDER BY 1
        """).fetchall()
        months = [r[0] for r in rows]
        totals = [r[1] / 1000.0 for r in rows]   # kg -> tonnes

        ax.plot(months, totals, marker="o", color=colours[label],
                linewidth=2, markersize=8)
        # One series per panel, so the panel title names it instead of a
        # legend box, which otherwise sits on top of the data.
        ax.set_title(f"{label} taxis", loc="left", fontsize=11)
        ax.set_ylabel("Total CO2 (tonnes)")
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle("NYC Taxi CO2 Output by Month, 2024", fontsize=13)
    axes[-1].set_xlabel("Month")
    axes[-1].set_xticks(range(1, 13))

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(filename, dpi=150)
    report(f"Plot written to {filename}")


def main():
    """Run all five analyses for each cab type, then render the plot.

    Opens the database read-only, since this stage only reports on what
    transform.py already calculated.
    """
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
