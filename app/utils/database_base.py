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
        Synchronizes all US states and Canadian provinces from GeoJSON files to ensure
        all mappable territories are in the states_country table, even if they don't
        have specific weed entries.
        """
        # Paths to GeoJSON files (adjust as needed based on your project structure)
        us_geojson_path = os.path.join('app', 'static', 'data', 'us-states.geojson')
        canada_geojson_path = os.path.join('app', 'static', 'data', 'canada-provinces.geojson')
        
        territories = []
        
        # Try to load US states
        try:
            if os.path.exists(us_geojson_path):
                with open(us_geojson_path, 'r') as f:
                    data = json.load(f)
                    for feature in data['features']:
                        name = feature['properties'].get('name') or feature['properties'].get('NAME')
                        if name:
                            territories.append((name.strip(), 'US'))
            else:
                print(f"Warning: US GeoJSON file not found at {us_geojson_path}")
        except Exception as e:
            print(f"Error loading US GeoJSON: {e}")
        
        # Try to load Canadian provinces
        try:
            if os.path.exists(canada_geojson_path):
                with open(canada_geojson_path, 'r') as f:
                    data = json.load(f)
                    for feature in data['features']:
                        name = feature['properties'].get('name') or feature['properties'].get('NAME')
                        if name:
                            territories.append((name.strip(), 'Canada'))
            else:
                print(f"Warning: Canada GeoJSON file not found at {canada_geojson_path}")
        except Exception as e:
            print(f"Error loading Canada GeoJSON: {e}")
        
        # If we found territories, add them to the database
        if territories:
            conn = self.get_connection()
            try:
                for territory, country in territories:
                    conn.execute('''
                        INSERT OR IGNORE INTO states_country (state, country)
                        VALUES (?, ?)
                    ''', (territory, country))
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
        
        Returns:
        str: The country code (e.g., 'US', 'Canada')
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
            
            # Add debug logging to help troubleshoot territory matching issues
            print(f"Warning: Could not determine country for state/province: '{state}'")
            
            # Default to US if we can't determine the country
            # This is a fallback and should be improved with a more complete mapping
            return 'US'
        finally:
            conn.close()