import sqlite3
from typing import List, Dict, Optional

class DatabaseBase:
    """Base class for database interactions with common functionality"""
    
    def __init__(self, db_path: str = 'weeds.db'):
        self.db_path = db_path
        self._ensure_states_country_table()
    
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
            
            # Default to US if we can't determine the country
            # This is a fallback and should be improved with a more complete mapping
            return 'US'
        finally:
            conn.close()