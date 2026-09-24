"""Run the whole NYC taxi CO2 pipeline with one command: python run.py"""

import logging
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("run.log"),
              logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

STAGES = ("load.py", "clean.py", "transform.py", "analysis.py")


def run_stage(script):
    """Run one pipeline stage and raise if it fails.

    Each stage runs as its own process rather than being imported, because
    logging.basicConfig only takes effect once per process -- importing all
    four here would send every stage's output to load.log instead of giving
    each one its own log file.
    """
    logger.info(f"--- {script} starting ---")
    start = time.time()

    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        raise RuntimeError(f"{script} exited with code {result.returncode}")

    logger.info(f"--- {script} finished in {time.time() - start:.1f}s ---")


def run_pipeline():
    """Run load, clean, transform and analysis in order.

    A failing stage stops the run, since each one depends on the tables the
    stage before it produced.
    """
    start = time.time()

    try:
        for script in STAGES:
            run_stage(script)
        logger.info(f"Pipeline complete in {time.time() - start:.1f}s")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    run_pipeline()
