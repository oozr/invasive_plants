from typing import List, Dict
from app.utils.database_base import DatabaseBase

class StateDatabase(DatabaseBase):
    """Class for state/province-related database operations"""
    
    def get_weeds_by_state(self, state: str) -> List[Dict]:
        """
        Get all weeds regulated in a specific state/province.
        Includes federal regulations for the state's country.
        
        Parameters:
        state (str): The state or province name
        
        Returns:
        List[Dict]: List of weed species regulated in the state
        """
        country = self.get_country_for_state(state)
        conn = self.get_connection()
        
        try:
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
                    'common_name': species.get('common_name'),  # Include common name in results
                    'family_name': species['family_name'],
                    'usage_key': species['usage_key'],
                    'level': 'State/Province' if species['state'] == state else 'Federal'
                })
            
            # Sort by level then by canonical_name 
            return sorted(results, key=lambda x: (0 if x['level'] == 'State/Province' else 1, 
                                               x['canonical_name'] or ""))
        finally:
            conn.close()

    def get_state_weed_counts(self) -> Dict[str, Dict]:
        """
        Get counts of regulated weeds for all states/provinces.
        Includes both state/province-specific and federal regulations.
        Also includes country information for each state/province.
        
        Returns:
        Dict[str, Dict]: Dictionary mapping state/province names to data including weed counts and country
        """
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
                    weed_count = federal_count
                else:
                    # For states with state-specific weeds, get combined count of unique species
                    cursor = conn.execute('''
                        SELECT COUNT(DISTINCT canonical_name) as count
                        FROM weeds
                        WHERE (state = ? OR (state = 'federal' AND country = ?))
                    ''', (state, country))
                    
                    weed_count = cursor.fetchone()['count']
                
                # Store both the count and the country information
                combined_counts[state] = {
                    'count': weed_count,
                    'country': country
                }
            
            return combined_counts
        finally:
            conn.close()