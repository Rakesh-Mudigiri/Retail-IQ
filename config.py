"""
Configuration settings for RetailIQ Application.
Contains database credentials and Flask app secret keys.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file (if exists)
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'retailiq_super_secret_key_2026')
    
    # Database Configurations
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Rakesh@26') 
    DB_NAME = os.environ.get('DB_NAME', 'sales')
    
    # Upload Configurations
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'dataset')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    
    # Report Export Configurations
    REPORT_FOLDER = os.path.join(BASE_DIR, 'reports')
    
    # Machine Learning Configurations
    MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sales_model.pkl')
