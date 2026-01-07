from typing import List, Dict
from app.utils.database_base import DatabaseBase

EU_MEMBERS = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
    "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
    "Slovenia", "Spain", "Sweden"
}

class StateDatabase(DatabaseBase):
    """Region-level map + table queries (new schema only)."""
    def __init__(self, db_path: str = "weeds.db", geojson_dir: str = None):
        super().__init__(db_path=db_path, geojson_dir=geojson_dir)

    def get_highlight_metrics(self) -> Dict:
        conn = self.get_connection()
        try:
            species_count = conn.execute(
                "SELECT COUNT(DISTINCT canonical_name) AS count FROM weeds"
            ).fetchone()["count"] or 0

            # Jurisdictions = region units + national countries + international groups
            region_j = conn.execute(
                """
                SELECT COUNT(DISTINCT country || '::' || region) AS count
                FROM weeds
                WHERE jurisdiction='region' AND country IS NOT NULL AND region IS NOT NULL
                """
            ).fetchone()["count"] or 0

            national_j = conn.execute(
                """
                SELECT COUNT(DISTINCT country) AS count
                FROM weeds
                WHERE jurisdiction='national' AND country IS NOT NULL
                """
            ).fetchone()["count"] or 0

            international_j = conn.execute(
                """
                SELECT COUNT(DISTINCT jurisdiction_group) AS count
                FROM weeds
                WHERE jurisdiction='international' AND jurisdiction_group IS NOT NULL
                """
            ).fetchone()["count"] or 0

            jurisdiction_count = region_j + national_j + international_j

            latest_country_row = conn.execute(
                """
                SELECT country
                FROM weeds
                WHERE country IS NOT NULL AND TRIM(country) != ''
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            latest_country = latest_country_row["country"] if latest_country_row else None

            latest_country_regions = 0
            latest_country_region = None
            if latest_country:
                latest_country_regions = conn.execute(
                    """
                    SELECT COUNT(DISTINCT region) AS count
                    FROM weeds
                    WHERE jurisdiction='region' AND country=? AND region IS NOT NULL AND TRIM(region) != ''
                    """,
                    (latest_country,)
                ).fetchone()["count"] or 0

                row = conn.execute(
                    """
                    SELECT region
                    FROM weeds
                    WHERE jurisdiction='region' AND country=? AND region IS NOT NULL AND TRIM(region) != ''
                    ORDER BY region ASC
                    LIMIT 1
                    """,
                    (latest_country,)
                ).fetchone()
                latest_country_region = row["region"] if row else None

            top_species_row = conn.execute(
                """
                SELECT canonical_name, COUNT(DISTINCT country || '::' || region) AS jurisdiction_count
                FROM weeds
                WHERE jurisdiction='region' AND country IS NOT NULL AND region IS NOT NULL
                GROUP BY canonical_name
                ORDER BY jurisdiction_count DESC, canonical_name ASC
                LIMIT 1
                """
            ).fetchone()

            top_species = None
            if top_species_row:
                common_name_row = conn.execute(
                    """
                    SELECT common_name
                    FROM weeds
                    WHERE canonical_name=? AND common_name IS NOT NULL AND TRIM(common_name)!=''
                    LIMIT 1
                    """,
                    (top_species_row["canonical_name"],)
                ).fetchone()

                common_name = None
                if common_name_row and common_name_row["common_name"]:
                    common_name = common_name_row["common_name"].split(",")[0].strip()

                top_species = {
                    "name": top_species_row["canonical_name"],
                    "common_name": common_name,
                    "jurisdiction_count": top_species_row["jurisdiction_count"],
                }

            top_j_row = conn.execute(
                """
                SELECT country, region, COUNT(DISTINCT canonical_name) AS species_count
                FROM weeds
                WHERE jurisdiction='region' AND country IS NOT NULL AND region IS NOT NULL
                GROUP BY country, region
                ORDER BY species_count DESC, region ASC
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
        include_international: bool = True
    ) -> List[Dict]:
        conn = self.get_connection()
        try:
            clauses = []
            params = []

            if include_region:
                clauses.append("(jurisdiction='region' AND country=? AND region=?)")
                params.extend([country, region])

            if include_national:
                clauses.append("(jurisdiction='national' AND country=?)")
                params.append(country)

            if include_international and country in EU_MEMBERS:
                clauses.append("(jurisdiction='international' AND jurisdiction_group='EU')")

            if not clauses:
                return []

            rows = conn.execute(
                f"""
                SELECT canonical_name, common_name, family_name, usage_key,
                       jurisdiction, jurisdiction_group
                FROM weeds
                WHERE {" OR ".join(clauses)}
                """,
                params
            ).fetchall()

            # Dedup by canonical_name with priority: region > national > international
            priority = {"region": 3, "national": 2, "international": 1}
            chosen = {}

            for r in rows:
                d = dict(r)
                name = d["canonical_name"]
                p = priority.get(d["jurisdiction"], 0)
                if name not in chosen or p > priority.get(chosen[name]["jurisdiction"], 0):
                    chosen[name] = d

            # Optional flags (useful for UI badges)
            names = list(chosen.keys())
            national_set = set()
            international_set = set()

            if include_national and names:
                q = f"""
                    SELECT DISTINCT canonical_name
                    FROM weeds
                    WHERE jurisdiction='national' AND country=?
                      AND canonical_name IN ({",".join(["?"] * len(names))})
                """
                national_set = {x["canonical_name"] for x in conn.execute(q, [country] + names).fetchall()}

            if include_international and country in EU_MEMBERS and names:
                q = f"""
                    SELECT DISTINCT canonical_name
                    FROM weeds
                    WHERE jurisdiction='international' AND jurisdiction_group='EU'
                      AND canonical_name IN ({",".join(["?"] * len(names))})
                """
                international_set = {x["canonical_name"] for x in conn.execute(q, names).fetchall()}

            level_map = {"region": "Regional", "national": "National", "international": "International"}

            results = []
            for sp in chosen.values():
                combined_common = None
                if sp.get("common_name"):
                    parts = [p.strip() for p in sp["common_name"].split(",")]
                    combined_common = ", ".join(parts[:2]) if parts else None

                results.append({
                    "canonical_name": sp["canonical_name"],
                    "common_name": combined_common,
                    "family_name": sp.get("family_name"),
                    "usage_key": sp.get("usage_key"),
                    "level": level_map.get(sp["jurisdiction"], "Unknown"),
                    "has_national_regulation": sp["canonical_name"] in national_set,
                    "has_international_regulation": sp["canonical_name"] in international_set,
                })

            return sorted(results, key=lambda x: x["canonical_name"] or "")
        finally:
            conn.close()

    def country_has_data(self, country: str) -> bool:
        """
        Returns True if any regulations exist for the given country (any level).
        EU countries treat EU-level international rows as data.
        """
        if not country:
            return False

        is_eu = country in EU_MEMBERS

        conn = self.get_connection()
        try:
            if is_eu:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM weeds
                    WHERE country=?
                       OR (jurisdiction='international' AND jurisdiction_group='EU')
                    LIMIT 1
                    """,
                    (country,),
                ).fetchone()
                return bool(row)

            row = conn.execute(
                """
                SELECT 1
                FROM weeds
                WHERE country=?
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
        include_international: bool = True
    ) -> List[Dict]:
        """
        Returns a list of:
        { country, region, count }
        for every (country, region) present on the map (regions_country),
        even if that region has only national/international regulations.
        """
        conn = self.get_connection()
        try:
            eu_list = sorted(EU_MEMBERS)
            eu_placeholders = ",".join(["?"] * len(eu_list)) if eu_list else "''"

            ir = 1 if include_region else 0
            inn = 1 if include_national else 0
            ii = 1 if include_international else 0

            query = f"""
            WITH regions AS (
                SELECT country, region
                FROM regions_country
                WHERE country IS NOT NULL AND TRIM(country) != ''
                AND region  IS NOT NULL AND TRIM(region)  != ''
            ),
            applicable AS (
                SELECT r.country, r.region, w.canonical_name
                FROM regions r
                JOIN weeds w
                ON (
                        ({ir}=1 AND w.jurisdiction='region' AND w.country=r.country AND w.region=r.region)
                    OR ({inn}=1 AND w.jurisdiction='national' AND w.country=r.country)
                    OR ({ii}=1 AND w.jurisdiction='international'
                            AND w.jurisdiction_group='EU'
                            AND r.country IN ({eu_placeholders})
                        )
                    )
            )
            SELECT r.country,
                r.region,
                COALESCE(COUNT(DISTINCT a.canonical_name), 0) AS count
            FROM regions r
            LEFT JOIN applicable a
                ON a.country=r.country AND a.region=r.region
            GROUP BY r.country, r.region
            """

            params = eu_list if (include_international and eu_list) else eu_list
            rows = conn.execute(query, params).fetchall()

            return [
                {"country": r["country"], "region": r["region"], "count": r["count"] or 0}
                for r in rows
            ]
        finally:
            conn.close()
