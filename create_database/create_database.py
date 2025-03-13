import sqlite3
import csv
import os
import glob
from datetime import datetime

def clean_value(value):
    """Clean and standardize field values"""
    if value is None:
        return None
    value = str(value).strip()
    if value.lower() == "na" or value == "":
        return None
    return value

def create_database(csv_folder="./data"):
    """Create SQLite database from the most recent weed list CSV in the specified folder"""
    # Find the most recent CSV file
    csv_files = glob.glob(os.path.join(csv_folder, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {csv_folder}!")
        return
    
    # Sort by modification time (newest first)
    csv_files.sort(key=os.path.getmtime, reverse=True)
    csv_file = csv_files[0]
    
    print(f"Using most recent CSV file: {os.path.basename(csv_file)}")
    
    # Connect to database
    print("Connecting to database...")
    conn = sqlite3.connect('weeds.db')
    cursor = conn.cursor()

    print("Dropping existing table if it exists...")
    cursor.execute('DROP TABLE IF EXISTS weeds')

    print("Creating weeds table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usage_key INTEGER,
            canonical_name TEXT NOT NULL,
            state TEXT NOT NULL,
            common_name TEXT,
            family_name TEXT,
            country TEXT NOT NULL,
            classification TEXT,
            taxon_level TEXT
        )
    ''')

    print("Creating indices...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_usage_key ON weeds(usage_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_state ON weeds(state)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_canonical_name ON weeds(canonical_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_country ON weeds(country)')

    try:
        print(f"Reading CSV file: {csv_file}")
        with open(csv_file, 'r', newline='', encoding='utf-8-sig') as file:
            csv_reader = csv.DictReader(file)
            record_count = 0
            
            for row in csv_reader:
                # Skip rows without required data
                if not row.get('state') or not row.get('prefName'):
                    continue
                
                # Convert usage_key to integer or None
                usage_key = None
                if row.get('GBIFusageKey') and row['GBIFusageKey'].strip() and row['GBIFusageKey'].strip().lower() != 'na':
                    try:
                        usage_key = int(row['GBIFusageKey'])
                    except ValueError:
                        usage_key = None
                
                cursor.execute('''
                    INSERT INTO weeds (
                        usage_key, canonical_name, state, common_name, 
                        family_name, country, classification, taxon_level
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    usage_key,
                    clean_value(row['prefName']),
                    clean_value(row['state']),
                    clean_value(row.get('englishName')),
                    clean_value(row.get('family')),
                    clean_value(row.get('country')) or 'Unknown',
                    clean_value(row.get('classification')),
                    clean_value(row.get('taxonLevel'))
                ))
                
                record_count += 1
                if record_count % 100 == 0:
                    print(f"Processed {record_count} records...")

        conn.commit()
        
        # Print statistics
        cursor.execute('SELECT COUNT(*) FROM weeds')
        total_records = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT state) FROM weeds')
        total_states = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT canonical_name) FROM weeds')
        total_species = cursor.fetchone()[0]
        
        cursor.execute('SELECT country, COUNT(*) FROM weeds GROUP BY country')
        country_stats = cursor.fetchall()
        
        print("\nDatabase created successfully!")
        print(f"Total records: {total_records}")
        print(f"Number of states/provinces: {total_states}")
        print(f"Number of unique species: {total_species}")
        print("\nRecords by country:")
        for country, count in country_stats:
            print(f"{country}: {count} records")
        
        print("\nSample entries:")
        cursor.execute('SELECT * FROM weeds LIMIT 3')
        for row in cursor.fetchall():
            print(row)
            
        # Show state distribution
        print("\nState/Province distribution:")
        cursor.execute('SELECT state, COUNT(*) as count FROM weeds GROUP BY state ORDER BY count DESC LIMIT 10')
        for state, count in cursor.fetchall():
            print(f"{state}: {count} records")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    # You can change this path to wherever you keep your CSV files
    data_folder = "./data"
    
    # Create the data folder if it doesn't exist
    os.makedirs(data_folder, exist_ok=True)
    
    # Check if given path is valid
    if not os.path.exists(data_folder):
        print(f"Error: Data folder {data_folder} does not exist!")
    else:
        create_database(data_folder)