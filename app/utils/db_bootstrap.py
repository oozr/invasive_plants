import os
import sqlite3
from preprocessing_utils.create_database import create_database

REQUIRED_COLUMNS = {"country", "region", "jurisdiction"}  # new schema

def db_has_new_schema(db_path: str) -> bool:
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute("PRAGMA table_info(weeds)")
        cols = {row[1] for row in cur.fetchall()}  # row[1] is column name
        return REQUIRED_COLUMNS.issubset(cols)
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass

def ensure_db(db_path: str, csv_folder: str):
    if not db_has_new_schema(db_path):
        # remove old incompatible db to avoid confusing partial state
        if os.path.exists(db_path):
            os.remove(db_path)
        create_database(csv_folder)
