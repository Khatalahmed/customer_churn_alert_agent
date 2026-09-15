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
from pathlib import Path

DATA_DIR = Path(os.getenv("CHURN_DATA_DIR") or Path(__file__).resolve().parent.parent)

DB_PATH = DATA_DIR / "qcommerce.db"
TRUTH_PATH = DATA_DIR / "churn_truth.json"             # answer key: training / eval only
MODEL_PATH = DATA_DIR / "churn_model.pkl"
PREDICTIONS_PATH = DATA_DIR / "churn_predictions.json"
REVIEWED_PATH = DATA_DIR / "churn_predictions_reviewed.json"
CONTACTED_PATH = DATA_DIR / "contacted.json"
REPORT_PATH = DATA_DIR / "retention_report.md"


def connect_readonly(path=None) -> sqlite3.Connection:
    """Open the database read-only: readers can look but never write.

    as_uri() gives a proper file:/// URI (drive letters, spaces) on any OS.
    """
    uri = Path(path or DB_PATH).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)
