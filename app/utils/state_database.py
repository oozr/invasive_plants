import sqlite3
from typing import Dict, List
from app.utils.database_base import DatabaseBase

EU_MEMBERS = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
    "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
    "Slovenia", "Spain", "Sweden"
}


class StateDatabase(DatabaseBase):
    """Region-level map + table queries using normalized schema."""

    def __init__(self, db_path: str = "weeds.db", geojson_dir: str = None):
        super().__init__(db_path=db_path, geojson_dir=geojson_dir)

    def get_highlight_metrics(self) -> Dict:
        conn = self.get_connection()
        try:
            species_count = conn.execute(
                "SELECT COUNT(*) AS count FROM plants WHERE has_current_regulation = 1"
            ).fetchone()["count"] or 0

            region_j = conn.execute(
                """
                SELECT COUNT(DISTINCT j.country || '::' || j.region) AS count
                FROM jurisdictions j
                WHERE j.jurisdiction_type = 'region'
                  AND j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND j.region IS NOT NULL AND TRIM(j.region) != ''
                  AND EXISTS (
                      SELECT 1
                      FROM regulations r
                      WHERE r.jurisdiction_id = j.id
                        AND r.is_webapp_scoped = 1
                  )
                """
            ).fetchone()["count"] or 0

            national_j = conn.execute(
                """
                SELECT COUNT(DISTINCT j.country) AS count
                FROM jurisdictions j
                WHERE j.jurisdiction_type = 'national'
                  AND j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND EXISTS (
                      SELECT 1
                      FROM regulations r
                      WHERE r.jurisdiction_id = j.id
                        AND r.is_webapp_scoped = 1
                  )
                """
            ).fetchone()["count"] or 0

            international_j = conn.execute(
                """
                SELECT COUNT(
                    DISTINCT COALESCE(NULLIF(TRIM(j.jurisdiction_group), ''), NULLIF(TRIM(j.country), ''), 'International')
                ) AS count
                FROM jurisdictions j
                WHERE j.jurisdiction_type = 'international'
                  AND EXISTS (
                      SELECT 1
                      FROM regulations r
                      WHERE r.jurisdiction_id = j.id
                        AND r.is_webapp_scoped = 1
                  )
                """
            ).fetchone()["count"] or 0

            jurisdiction_count = region_j + national_j + international_j

            latest_country_row = conn.execute(
                """
                SELECT j.country
                FROM jurisdictions j
                WHERE j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND EXISTS (
                      SELECT 1
                      FROM regulations r
                      WHERE r.jurisdiction_id = j.id
                        AND r.is_webapp_scoped = 1
                  )
                ORDER BY j.id DESC
                LIMIT 1
                """
            ).fetchone()
            latest_country = latest_country_row["country"] if latest_country_row else None

            latest_country_regions = 0
            latest_country_region = None
            if latest_country:
                latest_country_regions = conn.execute(
                    """
                    SELECT COUNT(DISTINCT j.region) AS count
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'region'
                      AND j.country = ?
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                      AND EXISTS (
                          SELECT 1
                          FROM regulations r
                          WHERE r.jurisdiction_id = j.id
                            AND r.is_webapp_scoped = 1
                      )
                    """,
                    (latest_country,),
                ).fetchone()["count"] or 0

                row = conn.execute(
                    """
                    SELECT j.region
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'region'
                      AND j.country = ?
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                      AND EXISTS (
                          SELECT 1
                          FROM regulations r
                          WHERE r.jurisdiction_id = j.id
                            AND r.is_webapp_scoped = 1
                      )
                    ORDER BY j.region ASC
                    LIMIT 1
                    """,
                    (latest_country,),
                ).fetchone()
                latest_country_region = row["region"] if row else None

            top_species_row = conn.execute(
                """
                SELECT
                    p.canonical_name,
                    COUNT(DISTINCT j.country || '::' || j.region) AS jurisdiction_count
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.jurisdiction_type = 'region'
                  AND j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND j.region IS NOT NULL AND TRIM(j.region) != ''
                GROUP BY p.canonical_name
                ORDER BY jurisdiction_count DESC, p.canonical_name ASC
                LIMIT 1
                """
            ).fetchone()

            top_species = None
            if top_species_row:
                common_name_row = conn.execute(
                    """
                    SELECT english_name
                    FROM plants
                    WHERE canonical_name = ?
                      AND english_name IS NOT NULL
                      AND TRIM(english_name) != ''
                    LIMIT 1
                    """,
                    (top_species_row["canonical_name"],),
                ).fetchone()
                common_name = None
                if common_name_row and common_name_row["english_name"]:
                    common_name = common_name_row["english_name"].split(",")[0].strip()

                top_species = {
                    "name": top_species_row["canonical_name"],
                    "common_name": common_name,
                    "jurisdiction_count": top_species_row["jurisdiction_count"],
                }

            top_j_row = conn.execute(
                """
                SELECT
                    j.country,
                    j.region,
                    COUNT(DISTINCT p.id) AS species_count
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.jurisdiction_type = 'region'
                  AND j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND j.region IS NOT NULL AND TRIM(j.region) != ''
                GROUP BY j.country, j.region
                ORDER BY species_count DESC, j.region ASC
                LIMIT 1
                """
            ).fetchone()

            top_jurisdiction = None
            if top_j_row:
                top_jurisdiction = {
                    "name": top_j_row["region"],
                    "country": top_j_row["country"],
                    "species_count": top_j_row["species_count"],
                }

            return {
                "species_count": species_count,
                "jurisdiction_count": jurisdiction_count,
                "latest_country": latest_country,
                "latest_country_regions": latest_country_regions,
                "latest_country_region": latest_country_region,
                "top_species": top_species,
                "top_jurisdiction": top_jurisdiction,
            }
        finally:
            conn.close()

    def get_weeds_for_region(
        self,
        country: str,
        region: str,
        include_region: bool = True,
        include_national: bool = True,
        include_international: bool = True,
    ) -> List[Dict]:
        conn = self.get_connection()
        try:
            clauses = []
            params = []

            if include_region:
                clauses.append(
                    """
                    SELECT
                        p.canonical_name,
                        p.english_name AS common_name,
                        p.family_name,
                        p.gbif_usage_key AS usage_key,
                        'region' AS jurisdiction
                    FROM regulations r
                    JOIN plants p ON p.id = r.plant_id
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND j.jurisdiction_type = 'region'
                      AND j.country = ?
                      AND j.region = ?
                    """
                )
                params.extend([country, region])

            if include_national:
                clauses.append(
                    """
                    SELECT
                        p.canonical_name,
                        p.english_name AS common_name,
                        p.family_name,
                        p.gbif_usage_key AS usage_key,
                        'national' AS jurisdiction
                    FROM regulations r
                    JOIN plants p ON p.id = r.plant_id
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND j.jurisdiction_type = 'national'
                      AND j.country = ?
                    """
                )
                params.append(country)

            if include_international and country in EU_MEMBERS:
                clauses.append(
                    """
                    SELECT
                        p.canonical_name,
                        p.english_name AS common_name,
                        p.family_name,
                        p.gbif_usage_key AS usage_key,
                        'international' AS jurisdiction
                    FROM regulations r
                    JOIN plants p ON p.id = r.plant_id
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND j.jurisdiction_type = 'international'
                      AND j.jurisdiction_group = 'EU'
                    """
                )

            if not clauses:
                return []

            rows = conn.execute(f"{' UNION ALL '.join(clauses)}", params).fetchall()

            priority = {"region": 3, "national": 2, "international": 1}
            chosen = {}
            scopes = {}

            for row in rows:
                data = dict(row)
                canonical_name = data["canonical_name"]
                jurisdiction = data["jurisdiction"]

                if canonical_name not in scopes:
                    scopes[canonical_name] = set()
                scopes[canonical_name].add(jurisdiction)

                existing = chosen.get(canonical_name)
                if not existing:
                    chosen[canonical_name] = data
                    continue

                existing_priority = priority.get(existing["jurisdiction"], 0)
                new_priority = priority.get(jurisdiction, 0)
                if new_priority > existing_priority:
                    chosen[canonical_name] = data

            level_map = {"region": "Regional", "national": "National", "international": "International"}

            results = []
            for species in chosen.values():
                common_name = None
                if species.get("common_name"):
                    parts = [part.strip() for part in species["common_name"].split(",") if part.strip()]
                    common_name = ", ".join(parts[:2]) if parts else None

                canonical_name = species["canonical_name"]
                species_scopes = scopes.get(canonical_name, set())
                results.append(
                    {
                        "canonical_name": canonical_name,
                        "common_name": common_name,
                        "family_name": species.get("family_name"),
                        "usage_key": species.get("usage_key"),
                        "level": level_map.get(species["jurisdiction"], "Unknown"),
                        "has_national_regulation": "national" in species_scopes,
                        "has_international_regulation": "international" in species_scopes,
                    }
                )

            return sorted(results, key=lambda x: x["canonical_name"] or "")
        finally:
            conn.close()

    def country_has_data(self, country: str) -> bool:
        if not country:
            return False

        conn = self.get_connection()
        try:
            if country in EU_MEMBERS:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM regulations r
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND (
                          j.country = ?
                          OR (j.jurisdiction_type = 'international' AND j.jurisdiction_group = 'EU')
                      )
                    LIMIT 1
                    """,
                    (country,),
                ).fetchone()
                return bool(row)

            row = conn.execute(
                """
                SELECT 1
                FROM regulations r
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.country = ?
                LIMIT 1
                """,
                (country,),
            ).fetchone()
            return bool(row)
        finally:
            conn.close()

    def get_region_weed_counts(
        self,
        include_region: bool = True,
        include_national: bool = True,
        include_international: bool = True,
    ) -> List[Dict]:
        conn = self.get_connection()
        try:
            regions_sql = """
                SELECT country, region
                FROM regions_country
                WHERE country IS NOT NULL AND TRIM(country) != ''
                  AND region IS NOT NULL AND TRIM(region) != ''
            """
            try:
                conn.execute("SELECT 1 FROM regions_country LIMIT 1").fetchone()
            except sqlite3.Error:
                # Fallback when regions_country is unavailable (e.g. read-only init failure).
                regions_sql = """
                    SELECT DISTINCT j.country AS country, j.region AS region
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'region'
                      AND j.country IS NOT NULL AND TRIM(j.country) != ''
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                """

            if not include_region and not include_national and not include_international:
                rows = conn.execute(
                    regions_sql
                ).fetchall()
                return [{"country": row["country"], "region": row["region"], "count": 0} for row in rows]

            applicable_clauses = []
            params = []

            if include_region:
                applicable_clauses.append(
                    """
                    SELECT r.country, r.region, rg.plant_id
                    FROM regions r
                    JOIN jurisdictions j
                      ON j.jurisdiction_type = 'region'
                     AND j.country = r.country
                     AND j.region = r.region
                    JOIN regulations rg
                      ON rg.jurisdiction_id = j.id
                     AND rg.is_webapp_scoped = 1
                    """
                )

            if include_national:
                applicable_clauses.append(
                    """
                    SELECT r.country, r.region, rg.plant_id
                    FROM regions r
                    JOIN jurisdictions j
                      ON j.jurisdiction_type = 'national'
                     AND j.country = r.country
                    JOIN regulations rg
                      ON rg.jurisdiction_id = j.id
                     AND rg.is_webapp_scoped = 1
                    """
                )

            if include_international and EU_MEMBERS:
                placeholders = ",".join(["?"] * len(EU_MEMBERS))
                applicable_clauses.append(
                    f"""
                    SELECT r.country, r.region, rg.plant_id
                    FROM regions r
                    JOIN jurisdictions j
                      ON j.jurisdiction_type = 'international'
                     AND j.jurisdiction_group = 'EU'
                    JOIN regulations rg
                      ON rg.jurisdiction_id = j.id
                     AND rg.is_webapp_scoped = 1
                    WHERE r.country IN ({placeholders})
                    """
                )
                params.extend(sorted(EU_MEMBERS))

            if not applicable_clauses:
                return []

            query = f"""
            WITH regions AS (
                {regions_sql}
            ),
            applicable AS (
                {' UNION ALL '.join(applicable_clauses)}
            )
            SELECT
                r.country,
                r.region,
                COALESCE(COUNT(DISTINCT a.plant_id), 0) AS count
            FROM regions r
            LEFT JOIN applicable a
              ON a.country = r.country
             AND a.region = r.region
            GROUP BY r.country, r.region
            """
            rows = conn.execute(query, params).fetchall()
            return [{"country": row["country"], "region": row["region"], "count": row["count"] or 0} for row in rows]
        finally:
            conn.close()

    def get_method_sources(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                """
                SELECT
                    CASE
                        WHEN j.jurisdiction_type = 'international'
                             AND TRIM(COALESCE(j.jurisdiction_group, '')) != ''
                        THEN j.jurisdiction_group
                        ELSE j.country
                    END AS country,
                    CASE
                        WHEN j.jurisdiction_type = 'national' THEN 'National'
                        WHEN j.jurisdiction_type = 'international'
                        THEN COALESCE(NULLIF(TRIM(j.jurisdiction_group), ''), 'International')
                        WHEN j.jurisdiction_type = 'region' THEN j.region
                        WHEN j.jurisdiction_type = 'habitat' THEN j.region
                        ELSE COALESCE(NULLIF(TRIM(j.region), ''), j.country)
                    END AS name,
                    COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS authority,
                    j.source_url,
                    COALESCE(
                        NULLIF(TRIM(CAST(j.last_updated_year AS TEXT)), ''),
                        NULLIF(TRIM(j.last_updated), ''),
                        'Unknown'
                    ) AS updated,
                    COALESCE(j.methodology_notes, '') AS methodology_notes,
                    COALESCE(j.source_notes, '') AS source_notes
                FROM jurisdictions j
                WHERE EXISTS (
                    SELECT 1
                    FROM regulations r
                    WHERE r.jurisdiction_id = j.id
                )
                ORDER BY country ASC, j.jurisdiction_type ASC, name ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
