# utils/logs.py

from datetime import datetime, timedelta
import time
import os
import pyautogui
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Access variables
PRINT_MESSAGES = os.getenv('PRINT_MESSAGES', 'True') == 'True'
INFO = os.getenv('INFO', 'info')
WARNING = os.getenv('WARNING', 'warning')
ERROR = os.getenv('ERROR', 'error')

def log_message(message, level=INFO):
    """
    Generic log function to handle info, warning, and error levels.
    It logs to both the console and a log file.

    Args:
        message (str): The message to log.
        level (str): The log level - "info", "warning", "error". Default is "info".
    """
    current_time = datetime.now().strftime("%H:%M:%S")  # Get current time in HH:MM:SS format
    
    # Print message to console
    if PRINT_MESSAGES:
        if level == INFO:
            print(f"{current_time} - INFO: {message}")
        elif level == WARNING:
            print(f"{current_time} - WARNING: {message}")
        elif level == ERROR:
            print(f"{current_time} - ERROR: {message}")
    
    # Log to file
    if level == INFO:
        logging.info(message)
    elif level == WARNING:
        logging.warning(message)
    elif level == ERROR:
        logging.error(message)