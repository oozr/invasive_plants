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
            cursor = conn.execute('SELECT * FROM weeds ORDER BY state, weed_name')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_weeds_by_state(self, state: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT * FROM weeds 
                WHERE state = ? 
                ORDER BY weed_name
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
            cursor = conn.execute('''
                SELECT DISTINCT weed_name, category 
                FROM weeds 
                WHERE weed_name LIKE ? OR category LIKE ?
                GROUP BY weed_name, category
                ORDER BY weed_name
            ''', (f'%{query}%', f'%{query}%'))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_states_by_weed(self, weed_name: str) -> List[str]:
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                SELECT DISTINCT state 
                FROM weeds 
                WHERE weed_name = ?
                ORDER BY state
            ''', (weed_name,))
            return [row['state'] for row in cursor.fetchall()]
        finally:
            conn.close()