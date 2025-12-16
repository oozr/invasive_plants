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

   # Highlights overrides (optional)
   _LATEST_COUNTRY_NAMES_RAW = os.getenv('LATEST_COUNTRY_NAMES')
   if _LATEST_COUNTRY_NAMES_RAW:
       LATEST_COUNTRY_NAMES = [c.strip() for c in _LATEST_COUNTRY_NAMES_RAW.split(",") if c.strip()]
   else:
       # Backward compatibility: single value fallback
       single = os.getenv('LATEST_COUNTRY_NAME', 'Israel, Qatar, Saudi Arabia')
       LATEST_COUNTRY_NAMES = [single] if single else []
   LATEST_COUNTRY_REGION = os.getenv('LATEST_COUNTRY_REGION')

   # Development vs Production
   DEBUG = os.getenv('FLASK_DEBUG', False)
   
   # Cache settings
   SEND_FILE_MAX_AGE_DEFAULT = 0
   CACHE_CONTROL = 'no-store, no-cache, must-revalidate'
   PRAGMA = 'no-cache'
   EXPIRES = '-1'
   
   # Directory paths
   BLOG_DIR = "app/blog_posts"

   # Blog settings
   POSTS_PER_PAGE = 10
