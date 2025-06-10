from typing import List, Dict
from app.utils.database_base import DatabaseBase

class SpeciesDatabase(DatabaseBase):
    """Class for species-related database operations"""
    
    def get_all_weeds(self) -> List[Dict]:
        """
        Get all weeds from the database.
        
        Returns:
        List[Dict]: List of all weed species in the database
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute('SELECT * FROM weeds ORDER BY state, canonical_name')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_weeds(self, query: str) -> List[Dict]:
        """
        Search for weeds based on a query string.
        Searches both common and canonical (scientific) names.
        
        Parameters:
        query (str): The search query
        
        Returns:
        List[Dict]: List of matching weed species
        """
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
                    synonyms,
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
        """
        Get weeds by their GBIF usage key.
        
        Parameters:
        usage_key (int): The GBIF usage key
        
        Returns:
        List[Dict]: List of weed records with the specified usage key
        """
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
        """
        Get states where a specific weed is regulated.
        
        Parameters:
        weed_name (str): The common or canonical name of the weed
        
        Returns:
        List[str]: List of state/province names where the weed is regulated
        """
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

    def get_states_by_usage_key(self, usage_key: int) -> Dict[str, List[str]]:
        """
        Get states where a weed with a specific usage key is regulated,
        grouped by country.
        
        Parameters:
        usage_key (int): The GBIF usage key
        
        Returns:
        Dict[str, List[str]]: Dictionary with countries as keys and list of states as values
                             If federally regulated, returns "Federal Level" as the only state
        """
        conn = self.get_connection()
        try:
            # Get all regulations for this usage key
            cursor = conn.execute('''
                SELECT DISTINCT w.state, w.country
                FROM weeds w
                WHERE w.usage_key = ?
                ORDER BY w.state
            ''', (usage_key,))
            
            results = cursor.fetchall()
            
            # Group by country
            regulations_by_country = {}
            
            for row in results:
                state = row['state']
                country = row['country']
                
                # Initialize country entry if it doesn't exist
                if country not in regulations_by_country:
                    regulations_by_country[country] = []
                
                # If there's a federal regulation, we'll handle it specially
                if state == 'federal':
                    # Clear any existing states for this country and just use "Federal Level"
                    regulations_by_country[country] = ["Federal Level"]
                    # Skip adding more states for this country since it's federally regulated
                    continue
                
                # Only add the state if the country isn't already set to federal level
                if regulations_by_country[country] != ["Federal Level"]:
                    regulations_by_country[country].append(state)
            
            return regulations_by_country
        finally:
            conn.close()