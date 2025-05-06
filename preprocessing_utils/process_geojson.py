# process_geojson.py using Python libraries
import json
import os
import argparse
import sys
try:
    import shapely.geometry
    import shapely.ops
except ImportError:
    print("Required libraries not found. Install them with:")
    print("pip install shapely")
    sys.exit(1)

def simplify_geojson(country_name, simplification_level=0.05):
    """
    Simplifies a GeoJSON file using Python libraries
    """
    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)  # preprocessing_utils folder
    
    input_file = os.path.join(base_dir, 'data', 'geographic', f'{country_name}_original.geojson')
    
    # Output to app's static directory
    project_root = os.path.dirname(base_dir)  # invasive_plants directory
    output_dir = os.path.join(project_root, 'app', 'static', 'data', 'geographic')
    
    # Dictionary mapping countries to their file names
    country_filename_map = {
        'canada': 'canada-provinces.geojson',
        'us': 'us-states.geojson',
        'australia': 'australia.geojson'
    }
    
    output_filename = country_filename_map.get(country_name, f'{country_name}.geojson')
    output_file = os.path.join(output_dir, output_filename)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file for {country_name} not found at {input_file}")
        inputted_path = input("Enter full path to GeoJSON file: ")
        if inputted_path and os.path.exists(inputted_path):
            input_file = inputted_path
        else:
            return False
    
    print(f"Reading GeoJSON from {input_file}...")
    with open(input_file, 'r') as f:
        geojson_data = json.load(f)
    
    # Simplify the GeoJSON using shapely
    print(f"Simplifying with tolerance {simplification_level}...")
    simplified_features = []
    skipped_features = 0
    
    for feature in geojson_data['features']:
        geometry = feature['geometry']
        properties = feature.get('properties', {})
        
        try:
            # Convert to shapely geometry
            shape = shapely.geometry.shape(geometry)
            
            # Simplify the shape
            simplified = shape.simplify(simplification_level, preserve_topology=True)
            
            # Make sure the result is valid
            if not simplified.is_valid:
                # Try to fix the geometry
                simplified = shapely.ops.make_valid(simplified)
                
                # If still not valid, use original
                if not simplified.is_valid:
                    simplified = shape
            
            # Skip empty geometries
            if simplified.is_empty:
                skipped_features += 1
                continue
                
            # Convert back to GeoJSON
            simplified_geo = shapely.geometry.mapping(simplified)
            
            # Create a new feature with simplified geometry
            simplified_feature = {
                'type': 'Feature',
                'geometry': simplified_geo,
                'properties': properties
            }
            
            simplified_features.append(simplified_feature)
            
        except Exception as e:
            print(f"Warning: Could not process feature {properties.get('name', 'unknown')}: {str(e)}")
            print(f"Using original geometry for this feature")
            
            # Add the original feature
            simplified_features.append(feature)
    
    print(f"Processed {len(simplified_features)} features, skipped {skipped_features} empty features")
    
    # Create the simplified GeoJSON
    simplified_geojson = {
        'type': 'FeatureCollection',
        'features': simplified_features
    }
    
    # Write the simplified GeoJSON to file
    with open(output_file, 'w') as f:
        json.dump(simplified_geojson, f)
    
    # Report file size
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"✓ Successfully processed {country_name}")
    print(f"  Output file: {output_file}")
    print(f"  File size: {file_size_mb:.2f} MB")
    
    original_size_mb = os.path.getsize(input_file) / (1024 * 1024)
    print(f"  Original size: {original_size_mb:.2f} MB")
    print(f"  Reduction: {100 * (1 - file_size_mb/original_size_mb):.1f}%")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process GeoJSON files for mapping')
    parser.add_argument('country', help='Country name (e.g., canada, us, australia)')
    parser.add_argument('--level', type=float, default=0.05, 
                        help='Simplification level (0.01-0.1 recommended, higher = more simplified)')
    
    args = parser.parse_args()
    simplify_geojson(args.country, args.level)