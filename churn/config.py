"""
config.py

WHAT : The one place that knows where every data file lives, plus the
       read-only database connection all readers share.
WHY  : File names used to be repeated as relative strings in ~15 modules, so
       everything silently depended on being run from the repo root. Paths
       are now anchored to the repo root (or CHURN_DATA_DIR if set), so the
       commands work from any directory.
"""
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.getenv("CHURN_DATA_DIR") or Path(__file__).resolve().parent.parent)

DB_PATH = DATA_DIR / "qcommerce.db"
TRUTH_PATH = DATA_DIR / "churn_truth.json"             # answer key: training / eval only
MODEL_PATH = DATA_DIR / "churn_model.pkl"
PREDICTIONS_PATH = DATA_DIR / "churn_predictions.json"
REVIEWED_PATH = DATA_DIR / "churn_predictions_reviewed.json"
CONTACTED_PATH = DATA_DIR / "contacted.json"
REPORT_PATH = DATA_DIR / "retention_report.md"
TRACE_PATH = DATA_DIR / "agent_trace.json"      # tool calls of the last agent run
WORKLIST_PATH = DATA_DIR / "worklist.json"      # output of the scheduled scan

# --- point-in-time prediction setup -------------------------------------------
# At a cutoff time T the model sees ONLY data from before T and predicts whether
# a currently active customer stops being active in the next HORIZON_DAYS.
# 14 days, not 28: the bad-experience signal fades after about a fortnight, so a
# month-ahead question includes churns whose trigger has not happened yet (measured:
# lift over random halves, and the model loses its edge over logistic regression).
HORIZON_DAYS = 14
ACTIVE_WINDOW_DAYS = 28            # "active at T" = any login in the 28 days before T
CUTOFF_STEP_DAYS = HORIZON_DAYS    # snapshots spaced by the horizon: no churn counted twice
# training snapshots, in days before the reference time (oldest first)
TRAIN_CUTOFFS_DAYS = tuple(range(168, 41, -CUTOFF_STEP_DAYS))
TEST_CUTOFF_DAYS = 28              # held-out snapshot: its labels start where training's end


def reference_now(conn: sqlite3.Connection) -> str:
    """The simulation's "now" (UTC, 'YYYY-MM-DD HH:MM:SS'), stored in the DB.

    Time-window queries use datetime(reference_now, '-30 days') instead of
    SQLite's wall-clock datetime('now'), so a database gives the same answers
    no matter when it is queried.
    """
    try:
        row = conn.execute(
            "SELECT value FROM sim_meta WHERE key = 'reference_now'"
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None:
        raise RuntimeError("database has no reference time - regenerate it with "
                           "`python -m churn.quick_commerce_sim init`")
    return row[0]


def cutoff_time(conn: sqlite3.Connection, days_before_reference: int) -> str:
    """A snapshot cutoff: the reference time minus N days (UTC string)."""
    ref = datetime.fromisoformat(reference_now(conn))
    return (ref - timedelta(days=days_before_reference)).isoformat(sep=" ")


def analysis_time(conn: sqlite3.Connection) -> str:
    """The point in time the pipeline looks from - scoring, tools and verifier.

    Default: the held-out test cutoff, the latest moment whose 14-day outcome is
    known, so the agent can be evaluated honestly. CHURN_AS_OF=reference scores
    "now" (production-style, no outcome to check); any other value is read as a
    UTC timestamp.
    """
    value = os.getenv("CHURN_AS_OF")
    if value == "reference":
        return reference_now(conn)
    if value:
        return datetime.fromisoformat(value).isoformat(sep=" ")
    return cutoff_time(conn, TEST_CUTOFF_DAYS)


def connect_readonly(path=None) -> sqlite3.Connection:
    """Open the database read-only: readers can look but never write.

    as_uri() gives a proper file:/// URI (drive letters, spaces) on any OS.
    """
    uri = Path(path or DB_PATH).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)
