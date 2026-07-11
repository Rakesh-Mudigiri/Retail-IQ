"""
Utility functions for validation, formatting, and logging.
"""

import logging
import os
import datetime

# Configure logging
def setup_logger():
    """Sets up the application logger."""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    log_filename = os.path.join('logs', f'retailiq_{datetime.datetime.now().strftime("%Y-%m-%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logger()

def get_currency_symbol():
    """Detects the currency symbol based on the average total_price in the sales table."""
    try:
        from database import Database
        result = Database.execute_query("SELECT AVG(total_price) as avg_price FROM sales", fetch=True, fetch_all=False)
        if result and result['avg_price'] and float(result['avg_price']) > 500:
            return "₹"
        return "$"
    except Exception as e:
        return "$"

def format_currency(value):
    """Formats a numeric value to the detected currency dynamically."""
    symbol = get_currency_symbol()
    try:
        # Standard formatting with commas
        return f"{symbol}{float(value):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"

def validate_csv_extension(filename):
    """Validates if the uploaded file is a CSV."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

def handle_exception(e, custom_message="An error occurred"):
    """Logs the exception and returns a formatted message."""
    logger.error(f"{custom_message}: {str(e)}", exc_info=True)
    return f"{custom_message}. Please check logs for details."
