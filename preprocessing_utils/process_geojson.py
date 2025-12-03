# process_geojson.py
# Simplify and "smush" GeoJSON files for web mapping

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


def round_coords(obj, precision=3):
    """
    Recursively round coordinates in a GeoJSON-like dict/list.

    precision:
        Number of decimal places to keep. For a world map
        where you never zoom in very far, 2–3 is usually plenty.
    """
    if isinstance(obj, list):
        # Possible coordinate pair [lon, lat]
        if len(obj) == 2 and all(isinstance(x, (int, float)) for x in obj):
            return [round(obj[0], precision), round(obj[1], precision)]
        else:
            return [round_coords(x, precision) for x in obj]

    elif isinstance(obj, dict):
        if "coordinates" in obj:
            new_obj = obj.copy()
            new_obj["coordinates"] = round_coords(obj["coordinates"], precision)
            return new_obj
        else:
            return {k: round_coords(v, precision) for k, v in obj.items()}

    return obj


def simplify_geometry(geometry, simplification_level, keep_largest_only=True):
    """
    Convert raw GeoJSON geometry to shapely, simplify it,
    optionally keep only the largest polygon in a MultiPolygon,
    and return a simplified GeoJSON geometry mapping.
    """
    shape = shapely.geometry.shape(geometry)

    # If MultiPolygon and we don't care about micro-islands,
    # keep only the largest polygon.
    if keep_largest_only and isinstance(shape, shapely.geometry.MultiPolygon):
        if len(shape.geoms) > 1:
            shape = max(shape.geoms, key=lambda g: g.area)

    # Simplify geometry
    simplified = shape.simplify(simplification_level, preserve_topology=True)

    # Ensure geometry is valid
    if not simplified.is_valid:
        simplified = shapely.ops.make_valid(simplified)
        if not simplified.is_valid:
            # Fall back to original if still invalid
            simplified = shape

    # Skip empty geometries
    if simplified.is_empty:
        return None

    # Back to GeoJSON geometry
    return shapely.geometry.mapping(simplified)


def simplify_geojson(
    country_name,
    simplification_level=0.2,
    precision=3,
    keep_largest_only=True,
):
    """
    Simplifies a GeoJSON file using shapely and writes a compact,
    web-friendly output to the app's static directory.

    country_name:
        Name used to locate input (e.g. 'canada', 'us', 'australia', 'ksa').
        Input is expected at: data/geographic/{country_name}_original.geojson

    simplification_level:
        Tolerance for shapely's simplify().
        Higher = more simplified. For world-scale outlines where you never
        zoom in far, 0.2–0.5 is often acceptable.

    precision:
        Number of decimal places kept in coordinates (2–3 is usually enough
        for a zoomed-out world map).

    keep_largest_only:
        If True, MultiPolygons are reduced to their largest polygon –
        great for big countries with tiny islands that bloat file size.
    """
    # Paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # INPUT:
    # preprocessing_utils/data/geographic/<country>_original.geojson
    input_dir = os.path.join(script_dir, "data", "geographic")
    input_file = os.path.join(input_dir, f"{country_name}_original.geojson")

    # PROJECT ROOT = parent folder (invasive_plants)
    project_root = os.path.dirname(script_dir)

    # OUTPUT:
    # invasive_plants/app/static/data/geographic/<country>.geojson
    output_dir = os.path.join(project_root, "app", "static", "data", "geographic")
    output_file = os.path.join(output_dir, f"{country_name}.geojson")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file for '{country_name}' not found at: {input_file}")
        print("Make sure it exists and is named '{country_name}_original.geojson'.")
        return False

    print(f"Reading GeoJSON from {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    print(
        f"Simplifying '{country_name}' with tolerance={simplification_level}, "
        f"precision={precision}, keep_largest_only={keep_largest_only}..."
    )

    simplified_features = []
    skipped_features = 0

    # Derive a readable country label from the country_name argument
    pretty_country_name = (
        country_name.replace("_", " ").replace("-", " ").title()
        if country_name
        else ""
    )

    for feature in geojson_data.get("features", []):
        geometry = feature.get("geometry")
        properties = feature.get("properties", {})

        if geometry is None:
            skipped_features += 1
            continue

        # --- NEW: ensure we have a name/country in properties ---
        # Only touch it if there is no useful name at all
        name_keys = ["name", "NAME", "STATE_NAME", "state", "STATE"]
        has_name = any(properties.get(k) for k in name_keys)

        if not has_name and pretty_country_name:
            # Treat the whole feature as "the country"
            properties["name"] = pretty_country_name
            # Optional but nice for debugging / future use
            properties.setdefault("country", pretty_country_name)

        try:
            simplified_geo = simplify_geometry(
                geometry,
                simplification_level=simplification_level,
                keep_largest_only=keep_largest_only,
            )

            if simplified_geo is None:
                skipped_features += 1
                continue

            simplified_feature = {
                "type": "Feature",
                "geometry": simplified_geo,
                "properties": properties,
            }
            simplified_features.append(simplified_feature)

        except Exception as e:
            print(
                f"Warning: Could not process feature "
                f"{properties.get('name', 'unknown')}: {str(e)}"
            )
            print("Using original geometry for this feature.")
            simplified_features.append(feature)

    print(
        f"Processed {len(simplified_features)} features, "
        f"skipped {skipped_features} empty/invalid features"
    )

    simplified_geojson = {
        "type": "FeatureCollection",
        "features": simplified_features,
    }

    # Round coordinates to reduce size further
    simplified_geojson = round_coords(simplified_geojson, precision=precision)

    # Write compact JSON (no pretty-print whitespace)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(simplified_geojson, f, separators=(",", ":"))

    # Report file size
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    original_size_mb = os.path.getsize(input_file) / (1024 * 1024)

    print(f"✓ Successfully processed {country_name}")
    print(f"  Output file: {output_file}")
    print(f"  File size: {file_size_mb:.3f} MB")
    print(f"  Original size: {original_size_mb:.3f} MB")
    print(f"  Reduction: {100 * (1 - file_size_mb / original_size_mb):.1f}%")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simplify GeoJSON files for web mapping"
    )
    parser.add_argument(
        "country",
        help="Country name (e.g., canada, us, australia, ksa)",
    )
    parser.add_argument(
        "--level",
        type=float,
        default=0.2,
        help=(
            "Simplification level (tolerance). "
            "Higher = more simplified. "
            "For a world map, 0.2–0.5 is often fine."
        ),
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=3,
        help=(
            "Decimal places to keep in coordinates. "
            "2–3 is usually enough for a zoomed-out world map."
        ),
    )
    parser.add_argument(
        "--keep-largest-only",
        action="store_true",
        help=(
            "If set, for MultiPolygons, keep only the largest polygon. "
            "Useful for big countries with tiny islands."
        ),
    )

    args = parser.parse_args()

    simplify_geojson(
        args.country,
        simplification_level=args.level,
        precision=args.precision,
        keep_largest_only=args.keep_largest_only,
    )
