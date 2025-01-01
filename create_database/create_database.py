# create_database.py
import sqlite3
import csv
import os
from datetime import datetime

def create_database(csv_file: str = 'weeds.csv'):
    """Create SQLite database from CSV file"""
    print("Connecting to database...")
    conn = sqlite3.connect('weeds.db')
    cursor = conn.cursor()

    print("Creating weeds table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT NOT NULL,
            weed_name TEXT NOT NULL,
            category TEXT NOT NULL
        )
    ''')

    print("Creating indices...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_state ON weeds(state)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_weed_name ON weeds(weed_name)')

    try:
        print(f"Reading CSV file: {csv_file}")
        with open(csv_file, 'r', newline='') as file:
            # Read CSV with specific field names to avoid empty columns
            csv_reader = csv.DictReader(file, fieldnames=['State', 'WeedName', 'Category'])
            
            # Skip the header row
            next(csv_reader)
            
            # Clear existing data
            cursor.execute('DELETE FROM weeds')
            
            # Insert rows
            count = 0
            for row in csv_reader:
                if all(row.values()): # Check if all required fields have values
                    cursor.execute('''
                        INSERT INTO weeds (state, weed_name, category)
                        VALUES (?, ?, ?)
                    ''', (
                        row['State'].strip(),
                        row['WeedName'].strip(),
                        row['Category'].strip()
                    ))
                    count += 1
                    
                if count % 100 == 0 and count > 0:
                    print(f"Processed {count} rows...")

        conn.commit()
        
        # Print statistics
        cursor.execute('SELECT COUNT(*) FROM weeds')
        total_records = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT state) FROM weeds')
        total_states = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT weed_name) FROM weeds')
        total_species = cursor.fetchone()[0]
        
        print("\nDatabase created successfully!")
        print(f"Total records: {total_records}")
        print(f"Number of states: {total_states}")
        print(f"Number of unique species: {total_species}")
        
        print("\nSample entries:")
        cursor.execute('SELECT * FROM weeds LIMIT 3')
        for row in cursor.fetchall():
            print(row)

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_database()