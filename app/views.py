# views.py
import csv
import os
from flask import Blueprint, render_template, jsonify, current_app, request
from app import db
from app.utils.generate_blog import BlogGenerator
from app.config import Config

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
    counts = db.get_state_weed_counts()
    return jsonify(counts)

# Species routes
@species.route('/')
def index():
    return render_template('species.html')

@species.route('/api/search')
def search_species():
    query = request.args.get('q', '')
    results = db.search_weeds(query)
    return jsonify(results)

@home.route('/api/state/<state>')
def state_weeds(state):
    weeds = db.get_weeds_by_state(state)
    return jsonify(weeds)

@species.route('/api/weed-states/<weed_name>')
def weed_states(weed_name):
    results = db.get_states_by_weed(weed_name)
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