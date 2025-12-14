from typing import List, Dict
from app.utils.database_base import DatabaseBase


class SpeciesDatabase(DatabaseBase):
    """Species-related database operations (region/national/international schema)."""

    def get_all_weeds(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT *
                FROM weeds
                ORDER BY
                    COALESCE(country, jurisdiction_group, ''),
                    jurisdiction,
                    COALESCE(region, ''),
                    canonical_name
                """
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_weeds(self, query: str) -> List[Dict]:
        """
        Search by common or canonical name.
        Returns distinct canonical_name (top 20), ordered by match quality.
        """
        conn = self.get_connection()
        try:
            exact_match = query.lower()
            starts_with = f"{query.lower()}%"
            contains = f"%{query.lower()}%"

            cursor = conn.execute(
                """
                SELECT DISTINCT
                    COALESCE(common_name, canonical_name) as common_name,
                    canonical_name,
                    family_name,
                    synonyms,
                    usage_key,
                    CASE
                        WHEN LOWER(common_name) = ? OR LOWER(canonical_name) = ? THEN 3
                        WHEN LOWER(common_name) LIKE ? OR LOWER(canonical_name) LIKE ? THEN 2
                        ELSE 1
                    END as search_priority
                FROM weeds
                WHERE LOWER(common_name) LIKE ?
                   OR LOWER(canonical_name) LIKE ?
                GROUP BY canonical_name, family_name, usage_key
                ORDER BY search_priority DESC, common_name
                LIMIT 20
                """,
                (exact_match, exact_match, starts_with, starts_with, contains, contains),
            )

            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_weeds_by_usage_key(self, usage_key: int) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT *
                FROM weeds
                WHERE usage_key = ?
                ORDER BY
                    COALESCE(country, jurisdiction_group, ''),
                    jurisdiction,
                    COALESCE(region, '')
                """,
                (usage_key,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_states_by_usage_key(self, usage_key: int) -> Dict[str, List[str]]:
        """
        Returns jurisdictions grouped for the species page.

        Output matches species_search.js expectations:
          {
            "United States": ["National Level", "California", "Hawaii"],
            "New Zealand": ["National Level"],
            "European Union": ["International Level"]
          }

        Notes:
        - region rows group by `country`
        - national rows group by `country`
        - international rows group by `jurisdiction_group`
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT DISTINCT
                    country,
                    region,
                    jurisdiction,
                    jurisdiction_group
                FROM weeds
                WHERE usage_key = ?
                ORDER BY
                    COALESCE(country, jurisdiction_group, ''),
                    jurisdiction,
                    COALESCE(region, '')
                """,
                (usage_key,),
            )
            rows = cursor.fetchall()

            grouped: Dict[str, List[str]] = {}

            for row in rows:
                jurisdiction = row["jurisdiction"]
                country = row["country"]
                region = row["region"]
                j_group = row["jurisdiction_group"]

                # Decide the display grouping key
                if jurisdiction == "international":
                    key = j_group  # required by schema
                    if not key:
                        # should never happen because you enforce it on insert
                        continue
                else:
                    key = country
                    if not key:
                        # should never happen for region/national due to insert validation
                        continue

                if key not in grouped:
                    grouped[key] = []

                if jurisdiction == "national":
                    if "National Level" not in grouped[key]:
                        grouped[key].append("National Level")

                elif jurisdiction == "international":
                    if "International Level" not in grouped[key]:
                        grouped[key].append("International Level")

                else:
                    # jurisdiction == "region"
                    if region and region not in grouped[key]:
                        grouped[key].append(region)

            return grouped
        finally:
            conn.close()
