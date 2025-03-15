import sqlite3
from typing import List, Dict, Optional

class WeedDatabase:
    def __init__(self, db_path: str = 'weeds.db'):
        self.db_path = db_path
        self._ensure_states_country_table()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def _ensure_states_country_table(self):
        """
        Creates and populates the states_country mapping table if it doesn't exist.
        This table maps states/provinces to their respective countries.
        """
        conn = self.get_connection()
        try:
            # Check if table exists
            cursor = conn.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='states_country'
            ''')
            
            if not cursor.fetchone():
                # Create table
                conn.execute('''
                    CREATE TABLE states_country (
                        state TEXT PRIMARY KEY,
                        country TEXT NOT NULL
                    )
                ''')
                
                # Populate with existing state-country mappings from weeds table
                conn.execute('''
                    INSERT OR IGNORE INTO states_country (state, country)
                    SELECT DISTINCT state, country FROM weeds
                    WHERE state != 'federal'
                ''')
                
                conn.commit()
        finally:
            conn.close()
            
    def add_state_country_mapping(self, state: str, country: str):
        """
        Adds or updates a state-to-country mapping.
        
        Parameters:
        state (str): The state or province name
        country (str): The country code (e.g., 'US', 'Canada')
        """
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO states_country (state, country)
                VALUES (?, ?)
            ''', (state, country))
            conn.commit()
        finally:
            conn.close()

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
            # First try to get the country for this state directly
            cursor = conn.execute('''
                SELECT DISTINCT country 
                FROM weeds 
                WHERE state = ?
            ''', (state,))
            
            result = cursor.fetchone()
            
            if result:
                country = result['country']
            else:
                # If the state isn't in the database, check if it exists in states_country mapping table
                cursor = conn.execute('''
                    SELECT country 
                    FROM states_country 
                    WHERE state = ?
                ''', (state,))
                
                result = cursor.fetchone()
                if result:
                    country = result['country']
                else:
                    # Default to US if we can't determine the country
                    # This is a fallback and should be improved with a more complete mapping
                    country = 'US'
            
            # Get both state-specific and federal regulations for this country
            cursor = conn.execute('''
                SELECT canonical_name, common_name, family_name, usage_key, state
                FROM weeds 
                WHERE (state = ? OR (state = 'federal' AND country = ?))
                ORDER BY state DESC, canonical_name
            ''', (state, country))
            
            # Use a dictionary to track unique species based on canonical_name
            seen_species = {}
            for row in cursor:
                row_dict = dict(row)
                canonical_name = row_dict['canonical_name']
                
                # If we haven't seen this species yet, or if this is a state regulation (prioritize over federal)
                if canonical_name not in seen_species or row_dict['state'] == state:
                    seen_species[canonical_name] = row_dict
            
            # Format the results with proper field names
            results = []
            for species in seen_species.values():
                results.append({
                    'canonical_name': species['canonical_name'],
                    'family_name': species['family_name'],
                    'usage_key': species['usage_key'],
                    'level': 'State/Province' if species['state'] == state else 'Federal'
                })
            
            # Sort by level then by canonical_name 
            return sorted(results, key=lambda x: (0 if x['level'] == 'State/Province' else 1, 
                                                x['canonical_name'] or ""))
        finally:
            conn.close()

    def get_state_weed_counts(self) -> Dict[str, int]:
        conn = self.get_connection()
        try:
            # Get all states/provinces from the database or states_country mapping table
            cursor = conn.execute('''
                SELECT DISTINCT state, country 
                FROM (
                    SELECT state, country FROM weeds WHERE state != 'federal'
                    UNION
                    SELECT state, country FROM states_country
                )
            ''')
            all_regions = {row['state']: row['country'] for row in cursor.fetchall()}
            
            # Get unique species counts for federal regulations per country
            cursor = conn.execute('''
                SELECT country, COUNT(DISTINCT canonical_name) as count 
                FROM weeds 
                WHERE state = 'federal'
                GROUP BY country
            ''')
            federal_counts = {row['country']: row['count'] for row in cursor.fetchall()}
            
            # For each state/province, count unique species from both state and federal regulations
            combined_counts = {}
            
            for state, country in all_regions.items():
                # First get state-specific weed count
                cursor = conn.execute('''
                    SELECT COUNT(DISTINCT canonical_name) as count
                    FROM weeds
                    WHERE state = ?
                ''', (state,))
                
                state_count = cursor.fetchone()['count'] or 0
                
                # Add federal count for this country
                federal_count = federal_counts.get(country, 0)
                
                # For states with no state-specific weeds, use federal count
                if state_count == 0:
                    combined_counts[state] = federal_count
                else:
                    # For states with state-specific weeds, get combined count of unique species
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


    def get_states_by_weed(self, weed_name: str) -> List[str]:
        conn = self.get_connection()
        try:
            # First try by common name
            cursor = conn.execute('''
                SELECT DISTINCT w.state, w.country
                FROM weeds w
                WHERE w.common_name = ?
                AND w.state != 'federal'
                ORDER BY w.state
            ''', (weed_name,))
            
            states = [row['state'] for row in cursor.fetchall()]
            
            # If no results, try by canonical name (scientific name)
            if not states:
                cursor = conn.execute('''
                    SELECT DISTINCT w.state, w.country
                    FROM weeds w
                    WHERE w.canonical_name = ?
                    AND w.state != 'federal'
                    ORDER BY w.state
                ''', (weed_name,))
                
                states = [row['state'] for row in cursor.fetchall()]
            
            # Get usage key to check federal regulations
            cursor = conn.execute('''
                SELECT usage_key, country
                FROM weeds
                WHERE common_name = ? OR canonical_name = ?
                LIMIT 1
            ''', (weed_name, weed_name))
            
            result = cursor.fetchone()
            if result:
                usage_key = result['usage_key']
                country = result['country']
                
                # Check if federally regulated
                cursor = conn.execute('''
                    SELECT COUNT(*) as count
                    FROM weeds
                    WHERE usage_key = ?
                    AND state = 'federal'
                ''', (usage_key,))
                
                count = cursor.fetchone()['count']
                if count > 0:
                    states.append(f"Federal ({country})")
            
            # Format state names to be more readable
            formatted_states = []
            for state in states:
                if state.startswith('Federal'):
                    formatted_states.append(state)
                else:
                    # Here you could map state codes to full names if desired
                    formatted_states.append(state)
            
            return formatted_states
        finally:
            conn.close()

    def get_states_by_usage_key(self, usage_key: int) -> List[str]:
        conn = self.get_connection()
        try:
            # Get all state regulations
            cursor = conn.execute('''
                SELECT DISTINCT w.state, w.country
                FROM weeds w
                WHERE w.usage_key = ?
                ORDER BY 
                    CASE WHEN w.state = 'federal' THEN 1 ELSE 0 END,
                    w.country,
                    w.state
            ''', (usage_key,))
            
            results = cursor.fetchall()
            
            # Format state names
            formatted_states = []
            for row in results:
                state = row['state']
                country = row['country']
                
                if state == 'federal':
                    formatted_states.append(f"Federal ({country})")
                else:
                    # Here you could map state codes to full names if desired
                    formatted_states.append(state)
            
            return formatted_states
        finally:
            conn.close()