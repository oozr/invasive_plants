# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Environment
- Install dependencies: `pip install -r requirements.txt`
- Activate virtual environment: `source weeds_env/bin/activate` (if exists)
- Run application locally: `python main.py` (runs on http://localhost:3000)
- Deploy: Uses Gunicorn via Procfile: `web: gunicorn "app:create_app()"`

### Database Operations
- Main database file: `weeds.db` (SQLite)
- Preprocessing scripts in `preprocessing_utils/`:
  - `create_database.py` - Creates and populates the database
  - `process_geojson.py` - Processes geographic data files

## Architecture

### Flask Application Structure
- **Entry point**: `main.py` creates app instance using factory pattern
- **App factory**: `app/__init__.py` contains `create_app()` function
- **Configuration**: `app/config.py` manages environment variables and settings
- **Views**: `app/views.py` contains all route handlers organized as Flask blueprints:
  - `home` - Main map interface and state data APIs
  - `species` - Species search functionality  
  - `blog` - Blog post rendering
  - `method` - Methodology information
  - `about` - About page with contact form

### Database Layer
- **Base class**: `app/utils/database_base.py` - Shared SQLite connection and geographic data management
- **State operations**: `app/utils/state_database.py` - State-to-weed mapping queries
- **Species operations**: `app/utils/species_database.py` - Species search and retrieval
- **Blog generation**: `app/utils/generate_blog.py` - Markdown blog post processing

### Key Features
- **Geographic visualization**: Interactive map using Leaflet.js with GeoJSON data for US, Canada, and Australia
- **Species search**: Full-text search across common and scientific names
- **Rate limiting**: Flask-Limiter with per-IP restrictions
- **Contact form**: Flask-Mail integration with reCAPTCHA validation
- **Blog system**: Markdown files with frontmatter in `app/blog_posts/`

### Static Assets
- **Map data**: `app/static/data/geographic/` contains compressed GeoJSON files
- **JavaScript**: Map interactions, search functionality, contact form handling
- **CSS**: Responsive design with separate files for map, blog, and general styling

### Environment Configuration
The app uses environment variables for:
- `SECRET_KEY` - Flask session security
- `DATABASE_PATH` - SQLite database location (default: weeds.db)
- `EMAIL_USERNAME`/`EMAIL_PASSWORD` - Gmail SMTP credentials
- `RECAPTCHA_SITE_KEY`/`RECAPTCHA_SECRET_KEY` - reCAPTCHA integration
- `BASE_URL` - Site URL for canonical links

### Deployment
- Configured for Heroku with `Procfile`
- Uses Gunicorn WSGI server
- Static file serving handled by Flask in production