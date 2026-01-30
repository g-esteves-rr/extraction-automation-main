# utils/actions.py

from datetime import datetime, timedelta
import time
import os
import json
import pyautogui

from utils.step_executor import StepExecutor
from dotenv import load_dotenv
from utils.logs import log_message

# Load environment variables from .env
load_dotenv()

# Access variables
LIMIT = int(os.getenv('LIMIT', 5))
MAX_LIMIT = int(os.getenv('MAX_LIMIT', 50))
MIN_SLEEP_TIME = int(os.getenv('MIN_SLEEP_TIME', 5))
MAX_SLEEP_TIME = int(os.getenv('MAX_SLEEP_TIME', 20))
CONFIDENCE = float(os.getenv('CONFIDENCE', 0.5))
SCREENSHOTS = os.getenv('SCREENSHOTS', 'True') == 'True'
PRINT_MESSAGES = os.getenv('PRINT_MESSAGES', 'True') == 'True'
INFO = os.getenv('INFO', 'info')
WARNING = os.getenv('WARNING', 'warning')
ERROR = os.getenv('ERROR', 'error')
START = os.getenv('START', '_beginning')
END = os.getenv('END', '_final')
PREV_MONTH_REPORTS = os.getenv('PREV_MONTH_REPORTS', '').split(',')



def load_report_config(report_name, user_folder=None):
    """
    Loads the report configuration. If `user_folder` is provided, try
    `config/{user_folder}/{report_name}.json` first, then fall back to
    `config/{report_name}.json`.
    """
    # Prefer configs placed relative to this script so execution from other
    # working directories still finds the files. Use uppercase username folder
    # and lowercase report filenames as per new convention.
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths_to_try = []
    report_file = f"{report_name.lower()}.json"
    if user_folder:
        paths_to_try.append(os.path.join(script_dir, "config", user_folder.upper(), report_file))
    paths_to_try.append(os.path.join(script_dir, "config", report_file))

    for config_path in paths_to_try:
        log_message(f"Looking for report config at: {config_path}", INFO)
        if os.path.isfile(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
            # Log and print the exact config path being used
            log_message(f"Using report config file: {config_path}", INFO)
            print(f"REPORT_CONFIG:{config_path}")
            return cfg
    raise FileNotFoundError(f"Report config not found for {report_name} (user_folder={user_folder})")


def perform_login(manager, step_name, images):
    import time
    log_message("Performing login", INFO)
    # Use the currently selected account for credentials. Do not read
    # username/password/database from environment variables.
    if not getattr(manager, "current_account", None):
        raise ValueError("No current account set for login; credentials must come from credentials.json")
    username = manager.current_account.get("username")
    password = manager.current_account.get("password")
    database = manager.current_account.get("database")

    try:
        #Connect to
        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"_1",report_name=manager.report_name)
        pyautogui.click(x + 75, y)
        pyautogui.press('down')
        pyautogui.press('enter')
        time.sleep(MIN_SLEEP_TIME)
        #Oracle Applications
        #x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        #StepExecutor.take_screenshot(step_name+"_2",report_name=manager.report_name)
        #pyautogui.click(x, y)
        #time.sleep(MIN_SLEEP_TIME)
        
        #Username
        x, y = StepExecutor.wait_for_image(images[2],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"_3",report_name=manager.report_name)
        pyautogui.click(x + 100, y)
        time.sleep(MIN_SLEEP_TIME)
        pyautogui.press(list(username))
        time.sleep(MIN_SLEEP_TIME)
        
        pyautogui.press('tab')
        pyautogui.press(list(password))
        StepExecutor.take_screenshot(step_name+"_4",report_name=manager.report_name)
        
        pyautogui.press('tab')
        pyautogui.press(list(database))
        StepExecutor.take_screenshot(step_name+"_5",report_name=manager.report_name)
        pyautogui.press('enter')
    except Exception as e:
        log_message(f"Error in login step: {str(e)}", WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_login_attempt(manager, account, images, report_conf):
    """Attempt login using provided account and images.

    Returns: "success", "password_expired", or "failure".
    Uses optional metadata in report_conf['_meta']:
      - login_success_image: image path to detect successful login
      - password_expired_image: image path to detect expired password dialog
    """
    username = account.get("username")
    password = account.get("password")
    database = account.get("database")

    try:
        # Delegate the actual UI interactions to the single `perform_login`
        # function so all login logic remains in one place.
        manager.current_account = account
        try:
            manager.perform_login("login_attempt", images)
        except Exception as e:
            log_message(f"Exception during perform_login for {username}: {e}", WARNING)
            return "failure"

        # After performing login, confirm result using report meta or
        # the next-step image. Do NOT check the global expired image here;
        # the dedicated `1b-password_check` step will handle expiry.
        meta = report_conf.get("_meta", {}) if isinstance(report_conf, dict) else {}
        success_img = meta.get("login_success_image")
        expired_img = meta.get("password_expired_image")

        # short pause for UI
        time.sleep(1)

        # If the report defines an expired image specifically, check it
        if expired_img and StepExecutor.check_image_exists(expired_img, report_name=manager.report_name):
            return "password_expired"

        # Try to find the image that starts the next step in the report
        next_step_img = None
        if isinstance(report_conf, dict):
            try:
                items = list(report_conf.items())
                login_index = None
                for idx, (sname, sdet) in enumerate(items):
                    if sdet.get("action") == "perform_login":
                        login_index = idx
                        break
                if login_index is not None and login_index + 1 < len(items):
                    next_details = items[login_index + 1][1]
                    nimgs = next_details.get("images") or []
                    if len(nimgs) > 0:
                        next_step_img = nimgs[0]
            except Exception:
                next_step_img = None

        TIMEOUT_CONFIRM = 10
        POLL_INTERVAL = 1
        if next_step_img:
            elapsed = 0
            while elapsed < TIMEOUT_CONFIRM:
                if StepExecutor.check_image_exists(next_step_img, report_name=manager.report_name):
                    print(f"LOGIN_CONFIRMED:{username}")
                    return "success"
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL

        if success_img and StepExecutor.check_image_exists(success_img, report_name=manager.report_name):
            print(f"LOGIN_CONFIRMED:{username}")
            return "success"

        # If no explicit images provided, assume success
        if not expired_img and not success_img and not next_step_img:
            time.sleep(2)
            print(f"LOGIN_CONFIRMED:{username}")
            return "success"

        print(f"LOGIN_FAILED:{username}")
        return "failure"

    except Exception as e:
        log_message(f"Exception during login attempt for {account.get('name') or account.get('username')}: {e}", WARNING)
        return "failure"

def perform_select_responsabilite(manager, step_name, images):
    log_message("Performing select_responsabilite", INFO)
    try:
        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+START,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        pyautogui.press(['down', 'down'])
        time.sleep(MIN_SLEEP_TIME)
        StepExecutor.take_screenshot(step_name+END,report_name=manager.report_name)

        pyautogui.press(['enter'])
        x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        pyautogui.click(x, y)
    except Exception as e:
        log_message(f"Error in select_responsabilite step: {str(e)}", WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_check_password_expired(manager, step_name, images):
    """
    images[0] -> expired password
    images[2] -> login error
    """
    log_message("Performing login state checks", INFO)
    if not images:
        log_message(f"No images configured for {step_name}", WARNING)
        return
    try:
        username = None
        if getattr(manager, "current_account", None):
            username = manager.current_account.get("username")
        # Password expired (highest priority)
        if len(images) > 0 and images[0]:
            if StepExecutor.check_image_exists(images[0], report_name=manager.report_name):
                log_message(f"Expired-password detected for user {username}", WARNING)
                print(f"PASSWORD_EXPIRED:{username}")
                manager._update_credentials_status(username, status="expired")
                raise Exception("Password expired detected")
        # Login error
        if len(images) > 1 and images[1]:
            if StepExecutor.check_image_exists(images[1], report_name=manager.report_name):
                log_message(f"Login error detected for user {username}", WARNING)
                print(f"LOGIN_ERROR:{username}")
                raise Exception("Login error detected")
        log_message(f"No login issues detected for {step_name}", INFO)
    except Exception as e:
        log_message(f"Error in login check: {e}", WARNING)
        raise

def perform_accept_optional(manager, step_name, images):
    log_message("Performing accept_optional", INFO)
    try:
        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+START,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)

        x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+END,report_name=manager.report_name)
        pyautogui.click(x, y)
    except Exception as e:
        log_message(f"Error in accept_optional step: {str(e)}", WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_browse(manager, step_name, images):
    log_message("Performing browse", INFO)
    try:
        time.sleep(MIN_SLEEP_TIME)
        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+START,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        pyautogui.click(x, y)
        pyautogui.press(['down', 'enter'])
        
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[2],report_name=manager.report_name)
        pyautogui.click(x, y)
        StepExecutor.take_screenshot(step_name+END,report_name=manager.report_name)
        pyautogui.press('enter')
        
    except Exception as e:
        log_message(f'Error in browse step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise
def perform_select_periode(manager, step_name, images):
    log_message("Performing select periode", INFO)

    try:

        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+START,report_name=manager.report_name)
        pyautogui.click(x + 200, y)
        time.sleep(MIN_SLEEP_TIME)

        pyautogui.press(list(manager.get_date_prev_month(step_name,manager.date)))
        time.sleep(MIN_SLEEP_TIME)

        StepExecutor.take_screenshot(step_name+"1",report_name=manager.report_name)
        pyautogui.press('enter')
        
        time.sleep(MIN_SLEEP_TIME)
        StepExecutor.take_screenshot(step_name+END,report_name=manager.report_name)

    except Exception as e:
        log_message(f'Error in login step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_wait(manager, step_name, images):
    log_message("Performing wait", INFO)
    try:
        StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)
        StepExecutor.wait_for_image_to_disappear(images[0],report_name=manager.report_name)
    except Exception as e:
        log_message(f'Error in wait step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise
        
def perform_long_wait(manager, step_name, images):
    log_message("Performing wait", INFO)
    try:
        time.sleep(MAX_SLEEP_TIME)
        StepExecutor.long_wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"1",report_name=manager.report_name)
        time.sleep(MIN_SLEEP_TIME)
        
    except Exception as e:
        log_message(f'Error in wait step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise
        
def perform_wait_large_query(manager, step_name, images):
    log_message("Performing wait", INFO)
    try:
        time.sleep(MIN_SLEEP_TIME)
        #Yes Large query
        position = StepExecutor.check_image_exists(images[1],report_name=manager.report_name)
        if position:
            x, y = position
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
        
        StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"1",report_name=manager.report_name)
        #StepExecutor.take_screenshot(step_name+"2",report_name=manager.report_name)
        StepExecutor.wait_for_image_to_disappear(images[0],report_name=manager.report_name)
    except Exception as e:
        log_message(f'Error in wait step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_wait_large_query_duk008(manager, step_name, images):
    log_message("Performing wait", INFO)
    try:
        time.sleep(MIN_SLEEP_TIME)
        #Yes Large query
        #position = StepExecutor.check_image_exists(images[1],report_name=manager.report_name)
        #if position:
        #   x, y = position
        #   pyautogui.click(x, y)
        #   time.sleep(MIN_SLEEP_TIME)

        StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"1",report_name=manager.report_name)
        #StepExecutor.take_screenshot(step_name+"2",report_name=manager.report_name)
        StepExecutor.wait_for_image_to_disappear(images[0],report_name=manager.report_name)
    except Exception as e:
        log_message(f'Error in wait step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise
        
def perform_extract(manager, step_name, images):
    log_message("Performing extract", INFO)
    try:
        time.sleep(MAX_SLEEP_TIME)
        x, y = StepExecutor.long_wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+START,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"1",report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[2],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"2",report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        destination_folder_path = os.environ.get("LOCAL_DESTINATION_FOLDER_PATH")
        file_name = manager.get_file_name(step_name,manager.date)
        destination = os.path.join(destination_folder_path, file_name)

        x, y = StepExecutor.wait_for_image(images[3],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"3",report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        pyautogui.write(destination, interval=0.25)
        StepExecutor.take_screenshot(step_name+"4",report_name=manager.report_name)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[4],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"5",report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        position = StepExecutor.check_image_exists(images[5],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"6",report_name=manager.report_name)
        if position:
            x, y = position
            pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[6],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+"7",report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        position = StepExecutor.check_image_exists(images[5],report_name=manager.report_name)
        if position:
            x, y = position
            pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        StepExecutor.take_screenshot(step_name+END,report_name=manager.report_name)

    except Exception as e:
        log_message(f'Error in extract step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_extract_ic01(manager, step_name, images):
    log_message("Performing extract", INFO)
    try:
        time.sleep(MIN_SLEEP_TIME)
        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[2],report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        destination_folder_path = os.environ.get("LOCAL_DESTINATION_FOLDER_PATH")
        file_name = manager.get_file_name(step_name,manager.date)
        destination = os.path.join(destination_folder_path, file_name)

        x, y = StepExecutor.wait_for_image(images[3],report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        pyautogui.write(destination, interval=0.25)
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[4],report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        #YES
        position = StepExecutor.check_image_exists(images[5],report_name=manager.report_name)
        if position:
            x, y = position
            pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[2],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[2],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        
        x, y = StepExecutor.wait_for_image(images[6],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        position = StepExecutor.check_image_exists(images[5],report_name=manager.report_name)
        if position:
            x, y = position
            pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        StepExecutor.take_screenshot(step_name,report_name=manager.report_name)

    except Exception as e:
        log_message(f'Error in extract step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_download(manager, step_name, images):
    log_message("Performing download", INFO)
    try:
        time.sleep(MIN_SLEEP_TIME)
        time.sleep(MIN_SLEEP_TIME)
        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+START,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        time.sleep(MIN_SLEEP_TIME)

        x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+END,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)

        time.sleep(MIN_SLEEP_TIME)
        pyautogui.hotkey('alt', 'f4')
        time.sleep(MIN_SLEEP_TIME)
        pyautogui.hotkey('alt', 'f4')
    except Exception as e:
        log_message(f'Error in download step: {str(e)}', WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

def perform_conditions(manager, step_name, images):
    log_message("Performing Conditions", INFO)
    try:
        x, y = StepExecutor.wait_for_image(images[0],report_name=manager.report_name)
        StepExecutor.take_screenshot(step_name+START,report_name=manager.report_name)
        pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        
        x, y = StepExecutor.wait_for_image(images[1],report_name=manager.report_name)
        pyautogui.doubleClick(x, y)
        time.sleep(MIN_SLEEP_TIME)
        
        pyautogui.press('tab')
        time.sleep(MIN_SLEEP_TIME)
        pyautogui.press('tab')
        time.sleep(MIN_SLEEP_TIME)
        pyautogui.press('tab')
        time.sleep(MIN_SLEEP_TIME)
        pyautogui.press('tab')
        time.sleep(MIN_SLEEP_TIME)
        date_str = str(manager.get_date_prev_month(step_name, manager.date))
        formatted_date = f"'{date_str.upper()}'"
        pyautogui.press(list(formatted_date))
        time.sleep(MIN_SLEEP_TIME)
        
        StepExecutor.take_screenshot(step_name+"_dev",report_name=manager.report_name)
        pyautogui.press('enter')
        time.sleep(MIN_SLEEP_TIME)
        time.sleep(MIN_SLEEP_TIME)
        
        #Yes Large query
        position = StepExecutor.check_image_exists(images[2],report_name=manager.report_name)
        if position:
                    x, y = position
                    pyautogui.click(x, y)
        time.sleep(MIN_SLEEP_TIME)
        StepExecutor.take_screenshot(step_name+END,report_name=manager.report_name)

    except Exception as e:
        log_message(f"Error in login step: {str(e)}", WARNING)
        #return f"FAIL_STEP: {step_name}"
        raise

