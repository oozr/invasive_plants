from typing import List, Dict
from app.utils.database_base import DatabaseBase

class StateDatabase(DatabaseBase):
    """Class for state/province-related database operations"""
    
    def get_highlight_metrics(self) -> Dict[str, int]:
        """Aggregated stats for homepage highlights"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT canonical_name) as count
                FROM weeds
            ''')
            species_count = cursor.fetchone()['count'] or 0

            cursor = conn.execute('''
                SELECT COUNT(DISTINCT state) as count FROM (
                    SELECT state FROM weeds WHERE state != 'federal'
                    UNION
                    SELECT state FROM states_country
                )
            ''')
            jurisdiction_count = cursor.fetchone()['count'] or 0

            cursor = conn.execute('''
                SELECT country
                FROM weeds
                WHERE country IS NOT NULL AND TRIM(country) != ''
                ORDER BY id DESC
                LIMIT 1
            ''')
            latest_country_row = cursor.fetchone()
            latest_country = latest_country_row['country'] if latest_country_row else None

            latest_country_regions = 0
            latest_country_state = None
            if latest_country:
                cursor = conn.execute('''
                    SELECT COUNT(DISTINCT state) as count
                    FROM weeds
                    WHERE country = ? AND state != 'federal'
                ''', (latest_country,))
                latest_country_regions = cursor.fetchone()['count'] or 0

                cursor = conn.execute('''
                    SELECT state FROM (
                        SELECT state FROM weeds 
                        WHERE country = ? AND state NOT IN ('', 'federal') AND state IS NOT NULL
                        UNION
                        SELECT state FROM states_country
                        WHERE country = ? AND state NOT IN ('', 'federal') AND state IS NOT NULL
                    )
                    ORDER BY state
                    LIMIT 1
                ''', (latest_country, latest_country))
                state_row = cursor.fetchone()
                latest_country_state = state_row['state'] if state_row else None

            cursor = conn.execute('''
                SELECT canonical_name, COUNT(DISTINCT state) as jurisdiction_count
                FROM weeds
                WHERE state IS NOT NULL 
                  AND state != '' 
                  AND state != 'federal'
                GROUP BY canonical_name
                ORDER BY jurisdiction_count DESC, canonical_name ASC
                LIMIT 1
            ''')
            top_species_row = cursor.fetchone()
            top_species = None
            if top_species_row:
                common_name_row = conn.execute('''
                    SELECT common_name
                    FROM weeds
                    WHERE canonical_name = ?
                      AND common_name IS NOT NULL
                      AND TRIM(common_name) != ''
                    LIMIT 1
                ''', (top_species_row['canonical_name'],)).fetchone()

                common_name = None
                if common_name_row and common_name_row['common_name']:
                    name_parts = [part.strip() for part in common_name_row['common_name'].split(',')]
                    common_name = name_parts[0]

                top_species = {
                    'name': top_species_row['canonical_name'],
                    'common_name': common_name,
                    'jurisdiction_count': top_species_row['jurisdiction_count']
                }

            cursor = conn.execute('''
                SELECT state, country, COUNT(DISTINCT canonical_name) as species_count
                FROM weeds
                WHERE state IS NOT NULL 
                  AND state != '' 
                  AND state != 'federal'
                GROUP BY state, country
                ORDER BY species_count DESC, state ASC
                LIMIT 1
            ''')
            top_jurisdiction_row = cursor.fetchone()
            top_jurisdiction = None
            if top_jurisdiction_row:
                top_jurisdiction = {
                    'name': top_jurisdiction_row['state'],
                    'country': top_jurisdiction_row['country'],
                    'species_count': top_jurisdiction_row['species_count']
                }

            return {
                'species_count': species_count,
                'jurisdiction_count': jurisdiction_count,
                'latest_country': latest_country,
                'latest_country_regions': latest_country_regions,
                'latest_country_state': latest_country_state,
                'top_species': top_species,
                'top_jurisdiction': top_jurisdiction
            }
        finally:
            conn.close()
    
    def get_weeds_by_state(self, state: str, include_federal: bool = True, include_state: bool = True) -> List[Dict]:
        """
        Get all weeds regulated in a specific state/province.
        Optionally includes federal regulations for the state's country.
        
        Parameters:
        state (str): The state or province name
        include_federal (bool): Whether to include federal regulations
        include_state (bool): Whether to include state/province regulations
        
        Returns:
        List[Dict]: List of weed species regulated in the state
        """
        country = self.get_country_for_state(state)
        conn = self.get_connection()
        
        try:
            # Build query based on toggle preferences
            where_conditions = []
            params = []
            
            if include_state:
                where_conditions.append("state = ?")
                params.append(state)
            
            if include_federal:
                where_conditions.append("(state = 'federal' AND country = ?)")
                params.append(country)
            
            # If neither is selected, return empty list
            if not where_conditions:
                return []
            
            query = f'''
                SELECT canonical_name, common_name, family_name, usage_key, state
                FROM weeds 
                WHERE ({' OR '.join(where_conditions)})
                ORDER BY state DESC, canonical_name
            '''
            
            cursor = conn.execute(query, params)
            
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
                # Take first two common names and combine with comma
                combined_common_name = None
                if species.get('common_name'):
                    names = [name.strip() for name in species['common_name'].split(',')]
                    first_two = names[:2]  # Take first two names
                    if first_two:
                        combined_common_name = ', '.join(first_two)
                
                # Check if this species has federal regulation
                has_federal = False
                if species['state'] == 'federal':
                    has_federal = True
                else:
                    # Check if there's a federal regulation for this species in the same country
                    temp_cursor = conn.execute('''
                        SELECT COUNT(*) as count
                        FROM weeds 
                        WHERE canonical_name = ? AND state = 'federal' AND country = ?
                    ''', (species['canonical_name'], country))
                    has_federal = temp_cursor.fetchone()['count'] > 0
                
                results.append({
                    'canonical_name': species['canonical_name'],
                    'common_name': combined_common_name,
                    'family_name': species['family_name'],
                    'usage_key': species['usage_key'],
                    'level': 'State/Province' if species['state'] == state else 'Federal',
                    'has_federal_regulation': has_federal
                })
            
            # Sort alphabetically by canonical_name only
            return sorted(results, key=lambda x: x['canonical_name'] or "")
        finally:
            conn.close()

    def get_state_weed_counts(self, include_federal: bool = True, include_state: bool = True) -> Dict[str, Dict]:
        """
        Get counts of regulated weeds for all states/provinces.
        Optionally includes state/province-specific and federal regulations.
        Also includes country information for each state/province.
        
        Parameters:
        include_federal (bool): Whether to include federal regulations
        include_state (bool): Whether to include state/province regulations
        
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
            
            # For each state/province, count unique species based on toggle preferences
            combined_counts = {}
            
            for state, country in all_regions.items():
                # Build query based on toggle preferences
                where_conditions = []
                params = []
                
                if include_state:
                    where_conditions.append("state = ?")
                    params.append(state)
                
                if include_federal:
                    where_conditions.append("(state = 'federal' AND country = ?)")
                    params.append(country)
                
                # If neither is selected, count is 0
                if not where_conditions:
                    weed_count = 0
                else:
                    query = f'''
                        SELECT COUNT(DISTINCT canonical_name) as count
                        FROM weeds
                        WHERE ({' OR '.join(where_conditions)})
                    '''
                    cursor = conn.execute(query, params)
                    weed_count = cursor.fetchone()['count'] or 0
                
                # Store both the count and the country information
                combined_counts[state] = {
                    'count': weed_count,
                    'country': country
                }
            
            return combined_counts
        finally:
            conn.close()
