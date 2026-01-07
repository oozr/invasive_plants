import sqlite3
import json
import os
from typing import Optional


class DatabaseBase:
    """
    New-schema only.

    Provides:
      - DB connection
      - regions_country table (country, region) synced from GeoJSON
    """

    def __init__(self, db_path: str = "weeds.db", geojson_dir: Optional[str] = None):
        self.db_path = db_path
        self.geojson_dir = geojson_dir or os.path.join("app", "static", "data", "geographic")
        self._ensure_regions_country_table()
        self._sync_regions_from_geojson()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_regions_country_table(self):
        conn = self.get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS regions_country (
                    country TEXT NOT NULL,
                    region  TEXT NOT NULL,
                    PRIMARY KEY (country, region)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_regions_country_country ON regions_country(country)"
            )
            conn.commit()
        finally:
            conn.close()

    def _infer_country_from_filename(self, filename: str) -> str:
        base = filename
        if base.lower().endswith(".geojson"):
            base = base[:-8]
        base = base.replace("_", " ").replace("-", " ").strip()
        return " ".join(w.capitalize() for w in base.split())

    def _extract_region_name(self, props: dict) -> Optional[str]:
        for key in ("name", "NAME", "STATE_NAME", "state", "STATE", "region", "REGION"):
            v = props.get(key)
            if v is None:
                continue
            v = str(v).strip()
            if v:
                return v
        return None

    def _sync_regions_from_geojson(self):
        geo_dir = self.geojson_dir
        if not geo_dir or not os.path.isdir(geo_dir):
            print(f"Warning: GeoJSON directory not found at {geo_dir}")
            return

        inserts = []

        for filename in os.listdir(geo_dir):
            if not filename.lower().endswith(".geojson"):
                continue

            inferred_country = self._infer_country_from_filename(filename)
            full_path = os.path.join(geo_dir, filename)

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for feature in data.get("features", []):
                    props = feature.get("properties", {}) or {}

                    country = (
                        str(props.get("country")).strip()
                        if props.get("country")
                        else inferred_country
                    )
                    region = self._extract_region_name(props)

                    if country and region:
                        inserts.append((country, region))

            except Exception as e:
                print(f"Error loading GeoJSON {full_path}: {e}")

        if not inserts:
            return

        conn = self.get_connection()
        try:
            conn.executemany(
                """
                INSERT OR IGNORE INTO regions_country (country, region)
                VALUES (?, ?)
                """,
                inserts,
            )
            conn.commit()
            print(f"Synced {len(inserts)} (country, region) rows into regions_country")
        finally:
            conn.close()
