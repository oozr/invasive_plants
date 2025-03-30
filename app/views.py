# views.py
import csv
import os
from flask import Blueprint, render_template, jsonify, current_app, request, flash, url_for, redirect
from flask_mail import Message
from app import mail, limiter

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
method = Blueprint('method', __name__, url_prefix='/method')
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
    """Get states where a weed is regulated by GBIF usage key grouped by country"""
    try:
        regulations_by_country = species_db.get_states_by_usage_key(usage_key)
        return jsonify(regulations_by_country)
    except Exception as e:
        current_app.logger.error(f"Error fetching states for usage key {usage_key}: {str(e)}")
        return jsonify({"error": "Failed to fetch states"}), 500

@species.route('/api/weed-states/by-name/<string:weed_name>')
def weed_states_by_name(weed_name):
    """Get states where a weed is regulated by common or canonical name"""
    results = species_db.get_states_by_weed(weed_name)
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

# Method, About and Home routes
@method.route('/')
def index():
    sources = []
    csv_path = os.path.join(current_app.root_path, 'static', 'data', 'regulatory_sources.csv')
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as file:  # Use utf-8-sig to handle BOM
            csv_reader = csv.DictReader(file)
            
            for row in csv_reader:
                source = {
                    'country': row.get('country', 'Unknown'),
                    'name': row.get('state_province', 'Unknown'),
                    'authority': row.get('authority_name', 'Unknown'),
                    'source_url': row.get('source_url', '#'),
                    'updated': row.get('last_updated_year', row.get('last_updated', 'Unknown'))
                }
                sources.append(source)
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return render_template('method.html', sources=[])
    
    return render_template('method.html', sources=sources)

# About routes
@about.route('/')
def index():
    return render_template('about.html')

@about.route('/contact', methods=['POST'])
@limiter.limit("5 per hour")  # Apply rate limiting to this route
def contact():
    """Handle contact form submission and send email"""
    # Check for honeypot field (bot detection)
    if request.form.get('website'):
        # This is likely a bot as real users won't fill the hidden field
        return redirect(url_for('about.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject_type = request.form.get('subject')
        message_text = request.form.get('message')
        
        # Form validation
        if not all([name, email, subject_type, message_text]):
            flash('All fields are required', 'error')
            return redirect(url_for('about.index'))
        
        # Create email subject based on the form's subject dropdown
        subject_map = {
            'general': 'General Inquiry',
            'data': 'Data Correction Request',
            'collaboration': 'Collaboration Request',
            'other': 'Other Inquiry'
        }
        
        email_subject = f"[Regulated Plants] {subject_map.get(subject_type, 'Contact Form')}"
        
        # Compose email message
        email_body = f"""
        You have received a new message from the Regulated Plants contact form:
        
        Name: {name}
        Email: {email}
        Subject: {subject_map.get(subject_type, 'Not specified')}
        
        Message:
        {message_text}
        """
        
        try:
            # Create a message object
            msg = Message(
                subject=email_subject,
                recipients=[current_app.config.get('EMAIL_USERNAME')],  # Use your configured email
                body=email_body,
                reply_to=email  # Set reply-to as the sender's email
            )
            
            # Send the email
            mail.send(msg)
            
            flash('Thank you for your message! We will get back to you soon.', 'success')
        except Exception as e:
            current_app.logger.error(f"Error sending email: {str(e)}")
            flash('There was an issue sending your message. Please try again later.', 'error')
        
        return redirect(url_for('about.index'))

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