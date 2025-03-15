# views.py
import csv
import os
from flask import Blueprint, render_template, jsonify, current_app, request
from app.utils.state_database import StateDatabase
from app.utils.species_database import SpeciesDatabase
from app.utils.generate_blog import BlogGenerator
from app.config import Config

# Databases:
from app.config import Config
state_db = StateDatabase(db_path=Config.DATABASE_PATH)
species_db = SpeciesDatabase(db_path=Config.DATABASE_PATH)

# Initialize blueprints
home = Blueprint('home', __name__)
species = Blueprint('species', __name__, url_prefix='/species')
blog = Blueprint('blog', __name__, url_prefix='/blog')
about = Blueprint('about', __name__, url_prefix='/about')

# Initialize blog generator
blog_generator = BlogGenerator()

# Home routes
@home.route('/')
def index():
    return render_template('home.html')

@home.route('/api/state-weed-counts')
def state_weed_counts():
    print("DEBUG: Fetching state weed counts")
    counts = state_db.get_state_weed_counts()
    print(f"DEBUG: Retrieved counts: {counts}")
    return jsonify(counts)

@home.route('/api/state/<state>')
def state_weeds(state):
    weeds = state_db.get_weeds_by_state(state)
    return jsonify(weeds)

# Species routes
@species.route('/')
def index():
    return render_template('species.html')

@species.route('/api/search')
def search_species():
    query = request.args.get('q', '')
    results = species_db.search_weeds(query)
    return jsonify(results)

@species.route('/api/weed-states/by-key/<int:usage_key>')
def weed_states_by_key(usage_key):
    """Get states where a weed is regulated by GBIF usage key (more accurate)"""
    results = species_db.get_states_by_usage_key(usage_key)
    return jsonify(results)

# Blog routes
@blog.route('/')
def index():
    tag = request.args.get('tag')
    posts = blog_generator.get_posts_by_tag(tag) if tag else blog_generator.blog_posts
    
    return render_template(
        'blog.html', 
        blog_posts=posts,
        all_tags=blog_generator.tags,
        current_tag=tag,
        title="Blog" if not tag else f"Blog - {tag}",
        description="Latest updates about regulated weeds"
    )

@blog.route('/<slug>')
def post(slug):
    post = blog_generator.get_post_by_slug(slug)
    if post:
        return render_template(
            'blog_post.html', 
            post=post,
            title=post['title']
        )
    return "Post not found", 404

# About routes
@about.route('/')
def index():
    states = []
    csv_path = os.path.join(current_app.root_path, 'static', 'data', 'ref4eachstate.csv')

    with open(csv_path, 'r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            state = {
                'name': row['state'],
                'authority': row['Issueing Authority'],
                'updated': row['Last Updated YR']
            }
            states.append(state)
    
    # Sort states alphabetically by name
    states.sort(key=lambda x: x['name'])
    
    return render_template('about.html', states=states)

@home.route('/debug/table-check')
def check_tables():
    conn = state_db.get_connection()
    try:
        # Check if table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weeds'")
        tables = cursor.fetchall()
        
        # Count rows in weeds table if it exists
        row_count = 0
        if tables:
            cursor = conn.execute("SELECT COUNT(*) as count FROM weeds")
            row_count = cursor.fetchone()['count']
            
        return jsonify({
            'tables_found': [dict(t) for t in tables],
            'row_count': row_count
        })
    finally:
        conn.close()