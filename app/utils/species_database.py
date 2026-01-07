from typing import List, Dict
from app.utils.database_base import DatabaseBase


class SpeciesDatabase(DatabaseBase):
    """Class for species-related database operations (new jurisdiction model)"""
    def __init__(self, db_path: str = "weeds.db", geojson_dir: str = None):
        super().__init__(db_path=db_path, geojson_dir=geojson_dir)

    def get_all_weeds(self) -> List[Dict]:
        """
        Get all weeds from the database.

        Returns:
        List[Dict]: List of all weed records
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                '''
                SELECT *
                FROM weeds
                ORDER BY country, jurisdiction, region, canonical_name
                '''
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_weeds(self, query: str) -> List[Dict]:
        """
        Search for weeds by query string.
        Searches both common and canonical (scientific) names.
        Returns distinct canonical_name results (top 20), ordered by match quality.
        """
        conn = self.get_connection()
        try:
            exact_match = query.lower()
            starts_with = f"{query.lower()}%"
            contains = f"%{query.lower()}%"

            cursor = conn.execute(
                '''
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
                ''',
                (
                    exact_match, exact_match,
                    starts_with, starts_with,
                    contains, contains
                )
            )

            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_weeds_by_usage_key(self, usage_key: int) -> List[Dict]:
        """Get all weed rows for a GBIF usage_key."""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                '''
                SELECT *
                FROM weeds
                WHERE usage_key = ?
                ORDER BY country, jurisdiction, region
                ''',
                (usage_key,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_states_by_weed(self, weed_name: str) -> List[str]:
        """
        Legacy helper (kept only if something else still calls it).
        Returns a flat list of regions plus "National (Country)" / "International (Country)" strings.
        """
        conn = self.get_connection()
        try:
            # Try by common name, then canonical name
            cursor = conn.execute(
                '''
                SELECT DISTINCT region, country, jurisdiction
                FROM weeds
                WHERE common_name = ?
                ORDER BY country, jurisdiction, region
                ''',
                (weed_name,)
            )
            rows = cursor.fetchall()

            if not rows:
                cursor = conn.execute(
                    '''
                    SELECT DISTINCT region, country, jurisdiction
                    FROM weeds
                    WHERE canonical_name = ?
                    ORDER BY country, jurisdiction, region
                    ''',
                    (weed_name,)
                )
                rows = cursor.fetchall()

            formatted = []
            for row in rows:
                country = row['country']
                jurisdiction = row['jurisdiction']
                region = row['region']

                if jurisdiction == 'national':
                    formatted.append(f"National ({country})")
                elif jurisdiction == 'international':
                    formatted.append(f"International ({country})")
                else:
                    formatted.append(region)

            # De-dupe while preserving order
            seen = set()
            out = []
            for x in formatted:
                if x not in seen:
                    out.append(x)
                    seen.add(x)
            return out
        finally:
            conn.close()

    def get_states_by_usage_key(self, usage_key: int) -> Dict[str, List[str]]:
        """
        Get jurisdictions where a weed is regulated, grouped by country.

        NEW EXPECTED OUTPUT SHAPE (for species_search.js):
          {
            "United States": ["National Level", "California", "Hawaii", ...],
            "European Union": ["International Level"],
            "New Zealand": ["National Level"]
          }
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                '''
                SELECT DISTINCT country, jurisdiction, region
                FROM weeds
                WHERE usage_key = ?
                ORDER BY country, jurisdiction, region
                ''',
                (usage_key,)
            )
            results = cursor.fetchall()

            regulations_by_country: Dict[str, List[str]] = {}

            for row in results:
                country = row['country']
                jurisdiction = row['jurisdiction']
                region = row['region']

                if country not in regulations_by_country:
                    regulations_by_country[country] = []

                if jurisdiction == 'national':
                    if "National Level" not in regulations_by_country[country]:
                        regulations_by_country[country].append("National Level")
                elif jurisdiction == 'international':
                    if "International Level" not in regulations_by_country[country]:
                        regulations_by_country[country].append("International Level")
                else:
                    # jurisdiction == 'region'
                    if region and region not in regulations_by_country[country]:
                        regulations_by_country[country].append(region)

            return regulations_by_country
        finally:
            conn.close()
