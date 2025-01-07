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
            cursor = conn.execute('SELECT * FROM weeds ORDER BY state, common_name')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_weeds_by_state(self, state: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT common_name, family_name, usage_key 
                FROM weeds 
                WHERE state = ? 
                ORDER BY common_name
            ''', (state,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_state_weed_counts(self) -> Dict[str, int]:
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT state, COUNT(*) as count 
                FROM weeds 
                GROUP BY state
            ''')
            return {row['state']: row['count'] for row in cursor.fetchall()}
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
                    common_name,
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
                GROUP BY common_name, canonical_name, family_name, usage_key
                -- Order by priority first, then alphabetically by common name
                ORDER BY search_priority DESC, common_name
                LIMIT 10
            ''', (
                exact_match, exact_match,           # For exact matches
                starts_with, starts_with,           # For starts-with matches
                contains, contains                  # For contains matches
            ))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_states_by_weed(self, weed_name: str) -> List[str]:
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT DISTINCT state 
                FROM weeds 
                WHERE common_name = ?
                ORDER BY state
            ''', (weed_name,))
            return [row['state'] for row in cursor.fetchall()]
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