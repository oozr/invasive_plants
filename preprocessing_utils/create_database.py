import csv
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# Ensure project root is on the path so `app` imports work when run directly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.database_base import DatabaseBase

# Paths
DATA_DIR = ROOT_DIR / "preprocessing_utils" / "data"
DB_PATH = ROOT_DIR / "weeds.db"
BACKUP_DIR = ROOT_DIR / "preprocessing_utils" / "old_databases"

CSV_PATTERN = "weed_lists_merged_*.csv"
REQUIRED_COLUMNS = {
    "GBIFusageKey",
    "country",
    "region",
    "jurisdiction",
    "jurisdiction_group",
    "prefName",
    "classification",
    "taxonLevel",
    "family",
    "englishName",
    "synonyms",
}


def find_latest_csv() -> Path:
    candidates = list(DATA_DIR.glob(CSV_PATTERN))
    geo_dir = DATA_DIR / "geographic"
    if geo_dir.exists():
        candidates += list(geo_dir.glob(CSV_PATTERN))

    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No CSV found matching {CSV_PATTERN} in {DATA_DIR}")
    latest = candidates[-1]
    print(f"Using source CSV: {latest}")
    return latest


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def coerce_usage_key(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def load_rows(csv_path: Path) -> List[Tuple]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        rows: List[Tuple] = []
        for row in reader:
            canonical_name = normalize_text(row.get("prefName"))
            country = normalize_text(row.get("country"))
            region = normalize_text(row.get("region"))
            j_group = normalize_text(row.get("jurisdiction_group"))
            jurisdiction = normalize_text(row.get("jurisdiction"))
            if jurisdiction:
                jurisdiction = jurisdiction.lower()

            if not canonical_name or not jurisdiction:
                continue  # skip malformed rows
            if not country and jurisdiction != "international":
                continue

            # Ensure region rows have a region name; ensure international rows have a group
            if jurisdiction == "region" and not region:
                continue
            if jurisdiction == "international" and not j_group:
                continue
            if jurisdiction == "international" and not country:
                country = j_group or "International"

            rows.append(
                (
                    coerce_usage_key(row.get("GBIFusageKey")),
                    canonical_name,
                    normalize_text(row.get("englishName")),
                    normalize_text(row.get("family")),
                    country,
                    region,
                    jurisdiction,
                    j_group,
                    normalize_text(row.get("classification")),
                    normalize_text(row.get("taxonLevel")),
                    normalize_text(row.get("synonyms")),
                )
            )
    print(f"Loaded {len(rows)} rows from CSV")
    return rows


def backup_existing_db(db_path: Path) -> None:
    if not db_path.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"weeds_{ts}.db"
    shutil.copy2(db_path, backup_path)
    print(f"Backed up existing database to {backup_path}")
    db_path.unlink()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS weeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usage_key INTEGER,
            canonical_name TEXT NOT NULL,
            common_name TEXT,
            family_name TEXT,
            country TEXT NOT NULL,
            region TEXT,
            jurisdiction TEXT NOT NULL,
            jurisdiction_group TEXT,
            classification TEXT,
            taxon_level TEXT,
            synonyms TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_weeds_usage_key ON weeds(usage_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_weeds_canonical_name ON weeds(canonical_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_weeds_country ON weeds(country)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_weeds_jurisdiction ON weeds(jurisdiction)")
    conn.commit()


def bulk_insert(conn: sqlite3.Connection, rows: Sequence[Tuple]) -> None:
    conn.executemany(
        """
        INSERT INTO weeds (
            usage_key,
            canonical_name,
            common_name,
            family_name,
            country,
            region,
            jurisdiction,
            jurisdiction_group,
            classification,
            taxon_level,
            synonyms
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def main() -> None:
    csv_path = find_latest_csv()
    rows = load_rows(csv_path)
    if not rows:
        print("No rows to insert; aborting.")
        return

    backup_existing_db(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        bulk_insert(conn, rows)
    finally:
        conn.close()

    # Ensure regions_country table exists and is populated from GeoJSON
    DatabaseBase(str(DB_PATH))

    print(f"Wrote {len(rows)} rows to {DB_PATH}")


if __name__ == "__main__":
    main()
