import sqlite3
import csv
import os
from datetime import datetime

def create_database(csv_file: str = 'weeds.csv'):
    """Create SQLite database from CSV file"""
    print("Connecting to database...")
    conn = sqlite3.connect('weeds.db')
    cursor = conn.cursor()

    print("Dropping existing table if it exists...")
    cursor.execute('DROP TABLE IF EXISTS weeds')

    print("Creating weeds table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usage_key INTEGER NOT NULL,
            canonical_name TEXT NOT NULL,
            state TEXT NOT NULL,
            common_name TEXT NOT NULL,
            family_name TEXT NOT NULL
        )
    ''')

    print("Creating indices...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_usage_key ON weeds(usage_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_state ON weeds(state)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_canonical_name ON weeds(canonical_name)')

    try:
        print(f"Reading CSV file: {csv_file}")
        # Changed encoding to 'latin-1' which is more permissive
        with open(csv_file, 'r', newline='', encoding='latin-1') as file:
            csv_reader = csv.DictReader(file)
            
            count = 0
            for row in csv_reader:
                if all(row.values()): # Check if all required fields have values
                    cursor.execute('''
                        INSERT INTO weeds (usage_key, canonical_name, state, common_name, family_name)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        int(row['usageKeyFedList']),
                        row['canonicalName'].strip(),
                        row['state'].strip(),
                        row['commonName'].strip(),
                        row['familyName'].strip()
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
        
        cursor.execute('SELECT COUNT(DISTINCT canonical_name) FROM weeds')
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