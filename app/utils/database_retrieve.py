import sqlite3
from typing import List, Dict, Optional

class WeedDatabase:
    def __init__(self, db_path: str = 'weeds.db'):
        self.db_path = db_path

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_weeds(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT * FROM weeds ORDER BY state, canonical_name')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_weeds_by_state(self, state: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            # First determine the country for this state/province
            cursor = conn.execute('''
                SELECT DISTINCT country FROM weeds WHERE state = ?
            ''', (state,))
            result = cursor.fetchone()
            
            # If no matching state is found, return empty list
            if not result:
                return []
                
            country = result['country']
            
            # Get regulations with no duplicates by canonical_name
            cursor = conn.execute('''
                WITH ranked_weeds AS (
                    SELECT 
                        canonical_name,
                        common_name, 
                        family_name, 
                        usage_key,
                        state,
                        CASE WHEN state = ? THEN 'State/Province' ELSE 'Federal' END as level,
                        -- Rank by state first, then by classification if there are multiple entries
                        ROW_NUMBER() OVER (
                            PARTITION BY canonical_name 
                            ORDER BY 
                                CASE WHEN state = ? THEN 0 ELSE 1 END,
                                classification
                        ) as rank
                    FROM weeds 
                    WHERE (state = ? OR (state = 'federal' AND country = ?))
                )
                SELECT canonical_name, common_name, family_name, usage_key, level
                FROM ranked_weeds
                WHERE rank = 1
                ORDER BY level, canonical_name
            ''', (state, state, state, country))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_state_weed_counts(self) -> Dict[str, int]:
        conn = self.get_connection()
        try:
            # Get unique species counts per state (excluding federal)
            cursor = conn.execute('''
                SELECT state, country, COUNT(DISTINCT canonical_name) as count 
                FROM weeds 
                WHERE state != 'federal'
                GROUP BY state, country
            ''')
            basic_counts = {row['state']: {'count': row['count'], 'country': row['country']} 
                            for row in cursor.fetchall()}
            
            # Get unique species counts for federal regulations per country
            cursor = conn.execute('''
                SELECT country, COUNT(DISTINCT canonical_name) as count 
                FROM weeds 
                WHERE state = 'federal'
                GROUP BY country
            ''')
            federal_counts = {row['country']: row['count'] for row in cursor.fetchall()}
            
            # Get all states and provinces from the database
            cursor = conn.execute('''
                SELECT DISTINCT state, country 
                FROM weeds 
                WHERE state != 'federal'
            ''')
            all_regions = {row['state']: row['country'] for row in cursor.fetchall()}
            
            # For each state/province, count unique species from both state and federal regulations
            combined_counts = {}
            
            for state, country in all_regions.items():
                # Count unique species names for this state/province including federal
                cursor = conn.execute('''
                    SELECT COUNT(DISTINCT canonical_name) as count
                    FROM weeds
                    WHERE (state = ? OR (state = 'federal' AND country = ?))
                ''', (state, country))
                
                combined_counts[state] = cursor.fetchone()['count']
            
            return combined_counts
        finally:
            conn.close()

    def search_weeds(self, query: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            # We'll use multiple search patterns for different priority levels
            exact_match = query.lower()
            starts_with = f"{query.lower()}%"
            contains = f"%{query.lower()}%"
            
            cursor = conn.execute('''
                SELECT DISTINCT 
                    COALESCE(common_name, canonical_name) as common_name,
                    canonical_name,
                    family_name,
                    usage_key,
                    -- Create a priority score for each result
                    CASE 
                        -- Exact matches get highest priority (3)
                        WHEN LOWER(common_name) = ? OR LOWER(canonical_name) = ? THEN 3
                        -- Names that start with the query get medium priority (2)
                        WHEN LOWER(common_name) LIKE ? OR LOWER(canonical_name) LIKE ? THEN 2
                        -- Names that contain the query get lowest priority (1)
                        ELSE 1
                    END as search_priority
                FROM weeds 
                WHERE LOWER(common_name) LIKE ? 
                    OR LOWER(canonical_name) LIKE ?
                GROUP BY canonical_name, family_name, usage_key
                -- Order by priority first, then alphabetically by name
                ORDER BY search_priority DESC, common_name
                LIMIT 20
            ''', (
                exact_match, exact_match,           # For exact matches
                starts_with, starts_with,           # For starts-with matches
                contains, contains                  # For contains matches
            ))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_weeds_by_state(self, state: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            # Determine which country this state/province belongs to
            canadian_regions = ['Alberta', 'British Columbia', 'Manitoba', 'New Brunswick', 
                            'Newfoundland & Labrador', 'Nova Scotia', 'Northwest Territories', 
                            'Nunavut', 'Ontario', 'Prince Edward Island', 'Quebec', 
                            'Saskatchewan', 'Yukon Territory']
            
            country = 'Canada' if state in canadian_regions else 'US'
            
            # Get both state-specific and federal regulations for this country
            cursor = conn.execute('''
                SELECT common_name, family_name, usage_key,
                    CASE WHEN state = ? THEN 'State/Province' ELSE 'Federal' END as level
                FROM weeds 
                WHERE (state = ? OR (state = 'federal' AND country = ?))
                ORDER BY level, common_name
            ''', (state, state, country))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_weeds_by_usage_key(self, usage_key: int) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT * FROM weeds 
                WHERE usage_key = ? 
                ORDER BY state
            ''', (usage_key,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()