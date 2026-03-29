# app/config.py
from dotenv import load_dotenv
import os

load_dotenv(override=False)

class Config:
   # Secret key for sessions/cookies
   SECRET_KEY = os.getenv('SECRET_KEY')
   
   # Database configuration
   DATABASE_PATH = os.getenv('DATABASE_PATH', 'weeds.db')
   
   # Email configuration
   EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME')
   EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

   # reCAPTCHA configuration  
   RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY')
   RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')

   # Site configuration
   SITE_NAME = "Regulated Plants Database"
   SITE_AUTHOR = "Regulated Plants Database Team"
   BASE_URL = os.getenv('BASE_URL', 'https://regulatedplants.unu.edu')
   OOZR_BASE_URL = os.getenv('OOZR_BASE_URL', '').rstrip('/')
   OOZR_PROJECT_SLUG = os.getenv('OOZR_PROJECT_SLUG', 'regulatedplants')
   OOZR_METRICS_ENABLED = os.getenv('OOZR_METRICS_ENABLED', '0')

   # Highlights override (single country name; optional)
   LATEST_COUNTRY_NAME = os.getenv('LATEST_COUNTRY_NAME', 'South Africa')

   # Development vs Production
   DEBUG = os.getenv('FLASK_DEBUG', False)
   
   # Cache settings
   SEND_FILE_MAX_AGE_DEFAULT = 0
   CACHE_CONTROL = 'no-store, no-cache, must-revalidate'
   PRAGMA = 'no-cache'
   EXPIRES = '-1'

   # Data service configuration
   DATA_MODE = os.getenv('DATA_MODE', 'local_sample')
   DATA_REMOTE_BASE_URL = os.getenv('DATA_REMOTE_BASE_URL')
   DATA_REMOTE_TOKEN = os.getenv('DATA_REMOTE_TOKEN')
   DATA_MANIFEST_PATH = os.getenv('DATA_MANIFEST_PATH', '/manifest.json')
   DATA_MANIFEST_TTL_SECONDS = int(os.getenv('DATA_MANIFEST_TTL_SECONDS', '0'))
   DATA_CACHE_DIR = os.getenv('DATA_CACHE_DIR', 'data_cache')
   DATA_REMOTE_TIMEOUT_SECONDS = int(os.getenv('DATA_REMOTE_TIMEOUT_SECONDS', '90'))
   LOCAL_SAMPLE_DB_PATH = os.getenv(
      'LOCAL_SAMPLE_DB_PATH',
      os.path.join('app', 'static', 'data', 'sample', 'weeds_sample.db')
   )
   LOCAL_SAMPLE_GEOJSON_DIR = os.getenv(
      'LOCAL_SAMPLE_GEOJSON_DIR',
      os.path.join('app', 'static', 'data', 'sample', 'geojson')
   )
   
   # Directory paths
   BLOG_DIR = "app/blog_posts"

   # Blog settings
   POSTS_PER_PAGE = 10
