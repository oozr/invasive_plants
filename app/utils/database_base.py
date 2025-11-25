import sqlite3
import json
import os
from typing import List, Dict, Optional

class DatabaseBase:
    """Base class for database interactions with common functionality"""
    
    def __init__(self, db_path: str = 'weeds.db'):
        self.db_path = db_path
        self._ensure_states_country_table()
        self._sync_territories_from_geojson()
    
    def get_connection(self):
        """Create and return a database connection with row factory set"""
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
    
    def _sync_territories_from_geojson(self):
        """
        Synchronize all states/provinces from *all* GeoJSON files in
        app/static/data/geographic into the states_country table.
        - Country name is inferred from filename, e.g.
        'united_states.geojson' -> 'United States'
        """
        geo_dir = os.path.join('app', 'static', 'data', 'geographic')

        if not os.path.isdir(geo_dir):
            print(f"Warning: GeoJSON directory not found at {geo_dir}")
            return

        territories = []

        for filename in os.listdir(geo_dir):
            if not filename.lower().endswith('.geojson'):
                continue

            # Derive country name from filename
            # 'united_states.geojson' -> 'united_states' -> 'United States'
            country_slug = filename[:-8]  # strip ".geojson"
            country_name = country_slug.replace('_', ' ').title()

            full_path = os.path.join(geo_dir, filename)

            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for feature in data.get('features', []):
                    props = feature.get('properties', {})
                    state_name = (
                        props.get('name')
                        or props.get('NAME')
                        or props.get('STATE_NAME')
                        or props.get('state')
                        or props.get('STATE')
                    )

                    if state_name:
                        territories.append((state_name.strip(), country_name))

            except Exception as e:
                print(f"Error loading GeoJSON {full_path}: {e}")

        if territories:
            conn = self.get_connection()
            try:
                for state, country in territories:
                    conn.execute(
                        '''
                        INSERT OR IGNORE INTO states_country (state, country)
                        VALUES (?, ?)
                        ''',
                        (state, country),
                    )
                conn.commit()
                print(f"Added {len(territories)} territories to states_country table")
            finally:
                conn.close()

    
    def get_country_for_state(self, state: str) -> str:
        """
        Get the country for a given state/province name.
        Falls back to the states_country mapping table if not found in weeds table.
        
        Parameters:
        state (str): The state or province name
        """
        conn = self.get_connection()
        try:
            # First try to get the country for this state directly from weeds table
            cursor = conn.execute('''
                SELECT DISTINCT country 
                FROM weeds 
                WHERE state = ?
            ''', (state,))
            
            result = cursor.fetchone()
            
            if result:
                return result['country']
            
            # If the state isn't in the weeds table, check states_country mapping table
            cursor = conn.execute('''
                SELECT country 
                FROM states_country 
                WHERE state = ?
            ''', (state,))
            
            result = cursor.fetchone()
            if result:
                return result['country']
            
            print(f"Warning: Could not determine country for state/province: '{state}'")
            return None

        finally:
            conn.close()