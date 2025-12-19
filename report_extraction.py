#!/usr/bin/env python
import pyautogui
import subprocess
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta 
from dotenv import load_dotenv

# Constants
LIMIT = 5
MAX_LIMIT = 50
MIN_SLEEP_TIME = 5
MAX_SLEEP_TIME = 20

# DEV Constants
#LIMIT = 5
#MAX_LIMIT = 5
#MIN_SLEEP_TIME = 3
#MAX_SLEEP_TIME = 10
#10
CONFIDENCE = 0.5

SCREENSHOTS = True
PRINT_MESSAGES  = True
INFO="info"
WARNING="warning"
ERROR="error"

START="_beginning"
END="_final"

# Reports that extract the prev month by defaulf
PREV_MONTH_REPORTS = ["ic01","accruals"]

# Logs
logging.basicConfig(filename='activity_logs.log', level=logging.INFO, format='%(asctime)s - %(levelname)s \t- %(message)s')

# Load environment variables from .env file
load_dotenv()

# Attempt to load helper for credentials (optional file)
try:
    from utils.credentials import load_credentials
except Exception:
    load_credentials = None

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


def load_report_config(report_name, user_folder=None):
    """
    Loads the report configuration. If `user_folder` is provided, try
    `config/{user_folder}/{report_name}.json` first, then fall back to
    `config/{report_name}.json`.
    """
    # Prefer configs placed relative to this script so execution from other
    # working directories still finds the files. Use uppercase username folder
    # and lowercase report filenames as per new convention.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths_to_try = []
    report_file = f"{report_name.lower()}.json"
    if user_folder:
        paths_to_try.append(os.path.join(script_dir, "config", user_folder.upper(), report_file))
    paths_to_try.append(os.path.join(script_dir, "config", report_file))

    for config_path in paths_to_try:
        log_message(f"Looking for report config at: {config_path}", INFO)
        if os.path.isfile(config_path):
            with open(config_path, "r") as f:
                return json.load(f)
    raise FileNotFoundError(f"Report config not found for {report_name} (user_folder={user_folder})")


def _read_credentials_file(path):
    """Read credentials file if present.

    Returns (data_obj, accounts_list, accounts_key)
    - data_obj: the parsed JSON (dict or list)
    - accounts_list: list of account dicts
    - accounts_key: None if top-level is list, or the key name (likely 'accounts')
    """
    if not os.path.isfile(path):
        return None, None, None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and "accounts" in data and isinstance(data["accounts"], list):
            return data, data["accounts"], "accounts"
        if isinstance(data, list):
            return data, data, None
        # unknown structure
        return data, None, None
    except Exception:
        return None, None, None


def _write_credentials_file(path, data_obj, accounts_list=None, accounts_key=None):
    """Write credentials back to disk atomically.

    If original structure used an accounts_key, update that key, otherwise
    write the provided accounts_list or data_obj.
    """
    try:
        if accounts_key and isinstance(data_obj, dict):
            data_obj[accounts_key] = accounts_list
            to_write = data_obj
        elif accounts_list is not None and accounts_key is None:
            to_write = accounts_list
        else:
            to_write = data_obj

        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(to_write, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except Exception as e:
        log_message(f"Failed to write credentials file {path}: {e}", WARNING)
        return False


class AutomationManager:
    def __init__(self, report_name, date=None):
        self.browser_instance = None
        self.steps = []
        self.report_name = report_name
        self.date = date
        # report_config will be loaded after successful login for the selected user
        self.report_config = None
        self.actions = {
                "perform_login": self.perform_login,
                "perform_select_responsabilite": self.perform_select_responsabilite,
                "perform_accept_optional": self.perform_accept_optional,
                "perform_browse": self.perform_browse,
                "perform_select_periode": self.perform_select_periode,
                "perform_wait": self.perform_wait,
                "perform_long_wait": self.perform_long_wait,
                "perform_wait_large_query": self.perform_wait_large_query,
                "perform_wait_large_query_duk008": self.perform_wait_large_query_duk008,
                "perform_extract": self.perform_extract,
                "perform_extract_ic01": self.perform_extract_ic01,
                "perform_download": self.perform_download,
                "perform_conditions":self.perform_conditions,
            }
        # steps are loaded after login succeeds (per-user configs)

    def load_steps(self):
        # Load steps configuration
        if not self.report_config:
            raise ValueError("Report config not loaded")
        for step_name, step_details in self.report_config.items():
            images = step_details.get('images')
            action = step_details.get('action')
            self.steps.append(Step(self.report_name, step_name, images, action))

    def select_and_login_and_load_steps(self):
        """Try credentials sequentially, load the per-user report config and steps on success."""
        # Resolve credentials file: prefer env var, otherwise use config/credentials.json
        # located relative to this script so running from other CWDs still works.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        creds_path = os.environ.get(
            "CREDENTIALS_FILE",
            os.path.join(script_dir, "config", "credentials.json"),
        )
        credentials = []
        try:
            if load_credentials:
                credentials = load_credentials(creds_path)
        except Exception as e:
            log_message(f"Could not load credentials from {creds_path}: {e}", WARNING)

        # Try to read credentials file directly to allow updating status/metadata
        file_data, file_accounts, file_accounts_key = _read_credentials_file(creds_path)
        if file_accounts:
            detected = [a.get("name") or a.get("username") for a in file_accounts]
            log_message(f"Detected accounts in credentials file {creds_path}: {detected}", INFO)
        else:
            # If no file-based accounts, log what we have in memory
            detected_mem = [a.get("name") or a.get("username") for a in credentials] if credentials else []
            log_message(f"Using credentials from env/loader: {detected_mem}", INFO)

        # If loader didn't return creds, use the raw credentials file accounts (preferred)
        if not credentials and file_accounts:
            credentials = file_accounts

        if not credentials:
            raise ValueError("No credentials available (set CREDENTIALS_FILE or provide config/credentials.json)")

        last_exc = None
        for account in credentials:
            user_folder = account.get("username")
            log_message(f"Attempting login using account: {user_folder}", INFO)
            attempt_ts = datetime.utcnow().isoformat() + "Z"
            try:
                # load per-user report config if available
                report_conf = load_report_config(self.report_name, user_folder=user_folder)
            except Exception as e:
                log_message(f"Could not load config for user {user_folder}: {e}", WARNING)
                # try next account
                last_exc = e
                continue

            # obtain login step images from report_conf
            login_images = None
            for step_name, step_details in report_conf.items():
                if step_details.get("action") == "perform_login":
                    login_images = step_details.get("images")
                    break

            if not login_images:
                log_message(f"Login step not defined in config for user {user_folder}", WARNING)
                last_exc = Exception("Login step not found")
                continue

            result = self.perform_login_attempt(account, login_images, report_conf)
            # Map attempt result to status string for credentials file
            if result == "success":
                new_status = "valid"
            elif result == "password_expired":
                new_status = "expired"
            else:
                new_status = "failed"

            # Update the credentials file entry (if present)
            try:
                if file_accounts:
                    # find matching account by name or username
                    match = None
                    for a in file_accounts:
                        if (a.get("name") and account.get("name") and a.get("name") == account.get("name")) or (
                            a.get("username") and account.get("username") and a.get("username") == account.get("username")
                        ):
                            match = a
                            break
                    if match is None:
                        # no exact match; try username-only match
                        for a in file_accounts:
                            if a.get("username") == account.get("username"):
                                match = a
                                break
                    if match is not None:
                        prev_status = match.get("status")
                        match["status"] = new_status
                        match["last_used"] = attempt_ts
                        if new_status == "expired":
                            match["expiry_date"] = attempt_ts
                        else:
                            # clear expiry_date when back to valid or failed
                            match.pop("expiry_date", None)
                        if prev_status != new_status:
                            match["status_changed_at"] = attempt_ts
                        wrote = _write_credentials_file(creds_path, file_data, file_accounts, file_accounts_key)
                        log_message(f"Updated credentials file {creds_path} for {match.get('name') or match.get('username')}: status={new_status} wrote={wrote}", INFO)
            except Exception as e:
                log_message(f"Error updating credentials file: {e}", WARNING)
            if result == "success":
                # set active config and load steps
                self.report_config = report_conf
                self.load_steps()
                self.current_account = account
                log_message(f"Login successful. Using account: {user_folder}", INFO)
                return True
            elif result == "password_expired":
                # log and continue to next account
                log_message(f"Password expired for {user_folder}", WARNING)
                # also emit a simple signal line for external handling
                print(f"PASSWORD_EXPIRED:{user_folder}")
                last_exc = Exception("Password expired")
                continue
            else:
                log_message(f"Login failed for {user_folder}", WARNING)
                last_exc = Exception("Login failed")
                continue

        # if we got here none worked
        if last_exc:
            raise last_exc
        raise Exception("No valid credentials found")

    def start(self, browser="FIREFOX"):
          try:
               self.browser_instance = self.open_browser(browser)
               # choose credentials, perform login and load per-user steps
               try:
                   self.select_and_login_and_load_steps()
               except Exception as e:
                   error_message = f"Login/setup failed: {str(e)}"
                   log_message(error_message, ERROR)
                   return error_message

               for step in self.steps:
                   log_message(f"Step {str(step.name)}", INFO)
                   log_message(f"Visual elements used on this step:\t {str(step.images)}", INFO)
                   try:
                       step.execute(self)
                   except FileNotFoundError as e:
                       error_message = f"Step '{step.name}' failed: Target image not detected on the screen - {str(e)}"
                       log_message(error_message, ERROR)
                       return error_message  # Return the error message with step name
                   except Exception as e:
                       error_message = f"Step '{step.name}' failed with an error: {str(e)}"
                       log_message(error_message, ERROR)
                       return error_message  # Return the error message with step name

               self.close_browser()
               log_message("\tSuccess", INFO)
               return "Success"  # Indicate success with a message
          except FileNotFoundError as e:
               error_message = f"Failed due to image detection issue: {str(e)}"
               log_message(error_message, ERROR)
               return error_message  # Return the detailed error message
          except Exception as e:
               error_message = f"Main Error: {str(e)}"
               log_message(error_message, ERROR)
               return error_message  # Return the detailed error message

    def open_browser(self, browser):
        url = os.environ.get("URL")
        browser_path = os.environ.get(browser + "_PATH")
        profile_path = os.environ.get(browser.upper() + "_PROFILE_PATH")  # optional
        
        if url is None or browser_path is None or profile_path is None:
            raise ValueError(f"URL or {browser}_PATH environment variable is not set")
        
        cmd = [browser_path]
        
        if profile_path:
            cmd += ["--profile", profile_path]
        
        cmd.append(url)
        cmd_message = f"FIREFOX COMMAND - {str(cmd)}"
        log_message(cmd_message, INFO)
        process = subprocess.Popen(cmd)
        
        # Maximize the window using xdotool

        subprocess.call(["xdotool", "search", "--onlyvisible", "--class", "Firefox", "windowmaximize"])
        return process

    def close_browser(self):
        if self.browser_instance:
            self.browser_instance.terminate()
            log_message("Browser closed.", INFO)
        log_message("Finished.", INFO)

    def perform_conditions(self, step_name, images):
        log_message("Performing Conditions", INFO)
        try:
            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+START,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            
            x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
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
            date_str = str(self.get_date_prev_month(step_name, self.date))
            formatted_date = f"'{date_str.upper()}'"
            pyautogui.press(list(formatted_date))
            time.sleep(MIN_SLEEP_TIME)
            
            StepExecutor.take_screenshot(step_name+"_dev",report_name=self.report_name)
            pyautogui.press('enter')
            time.sleep(MIN_SLEEP_TIME)
            time.sleep(MIN_SLEEP_TIME)
            
            #Yes Large query
            position = StepExecutor.check_image_exists(images[2],report_name=self.report_name)
            if position:
                        x, y = position
                        pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            StepExecutor.take_screenshot(step_name+END,report_name=self.report_name)

        except Exception as e:
            log_message(f"Error in login step: {str(e)}", WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
    
    def perform_login(self, step_name, images):
        log_message("Performing login", INFO)
        # Use the currently selected account for credentials. Do not read
        # username/password/database from environment variables.
        if not getattr(self, "current_account", None):
            raise ValueError("No current account set for login; credentials must come from credentials.json")
        username = self.current_account.get("username")
        password = self.current_account.get("password")
        database = self.current_account.get("database")

        try:
            #Connect to
            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"_1",report_name=self.report_name)
            pyautogui.click(x + 75, y)
            pyautogui.press('down')
            pyautogui.press('enter')
            time.sleep(MIN_SLEEP_TIME)
            #Oracle Applications
            #x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
            #StepExecutor.take_screenshot(step_name+"_2",report_name=self.report_name)
            #pyautogui.click(x, y)
            #time.sleep(MIN_SLEEP_TIME)
            
            #Username
            x, y = StepExecutor.wait_for_image(images[2],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"_3",report_name=self.report_name)
            pyautogui.click(x + 100, y)
            time.sleep(MIN_SLEEP_TIME)
            pyautogui.press(list(username))
            time.sleep(MIN_SLEEP_TIME)
            
            pyautogui.press('tab')
            pyautogui.press(list(password))
            StepExecutor.take_screenshot(step_name+"_4",report_name=self.report_name)
            
            pyautogui.press('tab')
            pyautogui.press(list(database))
            StepExecutor.take_screenshot(step_name+"_5",report_name=self.report_name)
            pyautogui.press('enter')
        except Exception as e:
            log_message(f"Error in login step: {str(e)}", WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise

    def perform_login_attempt(self, account, images, report_conf):
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
            # Connect / open login dialog
            x, y = StepExecutor.wait_for_image(images[0], report_name=self.report_name)
            StepExecutor.take_screenshot("login_start", report_name=self.report_name)
            pyautogui.click(x + 75, y)
            pyautogui.press('down')
            pyautogui.press('enter')
            time.sleep(MIN_SLEEP_TIME)

            # Enter username
            x, y = StepExecutor.wait_for_image(images[2], report_name=self.report_name)
            StepExecutor.take_screenshot("login_user", report_name=self.report_name)
            pyautogui.click(x + 100, y)
            time.sleep(MIN_SLEEP_TIME)
            pyautogui.press(list(username))
            time.sleep(MIN_SLEEP_TIME)

            pyautogui.press('tab')
            pyautogui.press(list(password))
            StepExecutor.take_screenshot("login_pass", report_name=self.report_name)

            pyautogui.press('tab')
            pyautogui.press(list(database) if database else [])
            StepExecutor.take_screenshot("login_db", report_name=self.report_name)
            pyautogui.press('enter')

            # After submitting, try to detect explicit failure or success images
            meta = report_conf.get("_meta", {}) if isinstance(report_conf, dict) else {}
            success_img = meta.get("login_success_image")
            expired_img = meta.get("password_expired_image")

            # Give UI a moment to show result
            time.sleep(3)

            if expired_img and StepExecutor.check_image_exists(expired_img, report_name=self.report_name):
                return "password_expired"

            if success_img and StepExecutor.check_image_exists(success_img, report_name=self.report_name):
                return "success"

            # If no specific images provided, assume success if no explicit expired image.
            if not expired_img and not success_img:
                # best-effort: small wait then consider success
                time.sleep(2)
                return "success"

            # If we had a success image configured but didn't find it, treat as failure
            return "failure"

        except Exception as e:
            log_message(f"Exception during login attempt for {account.get('name') or account.get('username')}: {e}", WARNING)
            return "failure"

    def perform_select_responsabilite(self, step_name, images):
        log_message("Performing select_responsabilite", INFO)
        try:
            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+START,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            pyautogui.press(['down', 'down'])
            time.sleep(MIN_SLEEP_TIME)
            StepExecutor.take_screenshot(step_name+END,report_name=self.report_name)

            pyautogui.press(['enter'])
            x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
            pyautogui.click(x, y)
        except Exception as e:
            log_message(f"Error in select_responsabilite step: {str(e)}", WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise

    def perform_accept_optional(self, step_name, images):
        log_message("Performing accept_optional", INFO)
        try:
            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+START,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)

            x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+END,report_name=self.report_name)
            pyautogui.click(x, y)
        except Exception as e:
            log_message(f"Error in accept_optional step: {str(e)}", WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise

    def perform_browse(self, step_name, images):
        log_message("Performing browse", INFO)
        try:
            time.sleep(MIN_SLEEP_TIME)
            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+START,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
            pyautogui.click(x, y)
            pyautogui.press(['down', 'enter'])
            
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[2],report_name=self.report_name)
            pyautogui.click(x, y)
            StepExecutor.take_screenshot(step_name+END,report_name=self.report_name)
            pyautogui.press('enter')
            
        except Exception as e:
            log_message(f'Error in browse step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
    def perform_select_periode(self, step_name, images):
        log_message("Performing select periode", INFO)

        try:

            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+START,report_name=self.report_name)
            pyautogui.click(x + 200, y)
            time.sleep(MIN_SLEEP_TIME)

            pyautogui.press(list(self.get_date_prev_month(step_name,self.date)))
            time.sleep(MIN_SLEEP_TIME)

            StepExecutor.take_screenshot(step_name+"1",report_name=self.report_name)
            pyautogui.press('enter')
            
            time.sleep(MIN_SLEEP_TIME)
            StepExecutor.take_screenshot(step_name+END,report_name=self.report_name)

        except Exception as e:
            log_message(f'Error in login step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
    
    def perform_wait(self, step_name, images):
        log_message("Performing wait", INFO)
        try:
            StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)
            StepExecutor.wait_for_image_to_disappear(images[0],report_name=self.report_name)
        except Exception as e:
            log_message(f'Error in wait step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
            
    def perform_long_wait(self, step_name, images):
        log_message("Performing wait", INFO)
        try:
            time.sleep(MAX_SLEEP_TIME)
            StepExecutor.long_wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"1",report_name=self.report_name)
            time.sleep(MIN_SLEEP_TIME)
            
        except Exception as e:
            log_message(f'Error in wait step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
            
    def perform_wait_large_query(self, step_name, images):
        log_message("Performing wait", INFO)
        try:
            time.sleep(MIN_SLEEP_TIME)
            #Yes Large query
            position = StepExecutor.check_image_exists(images[1],report_name=self.report_name)
            if position:
                x, y = position
                pyautogui.click(x, y)
                time.sleep(MIN_SLEEP_TIME)
            
            StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"1",report_name=self.report_name)
            #StepExecutor.take_screenshot(step_name+"2",report_name=self.report_name)
            StepExecutor.wait_for_image_to_disappear(images[0],report_name=self.report_name)
        except Exception as e:
            log_message(f'Error in wait step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
    
    def perform_wait_large_query_duk008(self, step_name, images):
        log_message("Performing wait", INFO)
        try:
            time.sleep(MIN_SLEEP_TIME)
            #Yes Large query
            #position = StepExecutor.check_image_exists(images[1],report_name=self.report_name)
            #if position:
            #   x, y = position
            #   pyautogui.click(x, y)
            #   time.sleep(MIN_SLEEP_TIME)

            StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"1",report_name=self.report_name)
            #StepExecutor.take_screenshot(step_name+"2",report_name=self.report_name)
            StepExecutor.wait_for_image_to_disappear(images[0],report_name=self.report_name)
        except Exception as e:
            log_message(f'Error in wait step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
            
    def perform_extract(self, step_name, images):
        log_message("Performing extract", INFO)
        try:
            time.sleep(MAX_SLEEP_TIME)
            x, y = StepExecutor.long_wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+START,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"1",report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[2],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"2",report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            destination_folder_path = os.environ.get("LOCAL_DESTINATION_FOLDER_PATH")
            file_name = self.get_file_name(step_name,self.date)
            destination = os.path.join(destination_folder_path, file_name)

            x, y = StepExecutor.wait_for_image(images[3],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"3",report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            pyautogui.write(destination, interval=0.25)
            StepExecutor.take_screenshot(step_name+"4",report_name=self.report_name)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[4],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"5",report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            position = StepExecutor.check_image_exists(images[5],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"6",report_name=self.report_name)
            if position:
                x, y = position
                pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[6],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+"7",report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            position = StepExecutor.check_image_exists(images[5],report_name=self.report_name)
            if position:
                x, y = position
                pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            StepExecutor.take_screenshot(step_name+END,report_name=self.report_name)

        except Exception as e:
            log_message(f'Error in extract step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise
    
    def perform_extract_ic01(self, step_name, images):
        log_message("Performing extract", INFO)
        try:
            time.sleep(MIN_SLEEP_TIME)
            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[2],report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            destination_folder_path = os.environ.get("LOCAL_DESTINATION_FOLDER_PATH")
            file_name = self.get_file_name(step_name,self.date)
            destination = os.path.join(destination_folder_path, file_name)

            x, y = StepExecutor.wait_for_image(images[3],report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            pyautogui.write(destination, interval=0.25)
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[4],report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            #YES
            position = StepExecutor.check_image_exists(images[5],report_name=self.report_name)
            if position:
                x, y = position
                pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[2],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[2],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            
            x, y = StepExecutor.wait_for_image(images[6],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)

            position = StepExecutor.check_image_exists(images[5],report_name=self.report_name)
            if position:
                x, y = position
                pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            StepExecutor.take_screenshot(step_name,report_name=self.report_name)

        except Exception as e:
            log_message(f'Error in extract step: {str(e)}', WARNING)
            #return f"FAIL_STEP: {step_name}"
            raise

    def perform_download(self, step_name, images):
        log_message("Performing download", INFO)
        try:
            time.sleep(MIN_SLEEP_TIME)
            time.sleep(MIN_SLEEP_TIME)
            x, y = StepExecutor.wait_for_image(images[0],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+START,report_name=self.report_name)
            pyautogui.click(x, y)
            time.sleep(MIN_SLEEP_TIME)
            time.sleep(MIN_SLEEP_TIME)

            x, y = StepExecutor.wait_for_image(images[1],report_name=self.report_name)
            StepExecutor.take_screenshot(step_name+END,report_name=self.report_name)
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

    def get_date_prev_month(self, step_name, date=None):
        # Load the report configuration
        report_config = load_report_config(self.report_name)
        # Get the specific date format for the given report name from the config
        date_format = report_config.get(step_name).get("date_format", "%b-%y")  # Default to "%y-%m-%d" if not specified
        if not date:
            # Calculate the date for the previous month
            today = datetime.now()
            # Create a timedelta object representing one month
            one_month_ago = timedelta(days=31)  # Adjust for days in different months if needed
            # Subtract one month from the current date
            date = today - one_month_ago
        # Format the previous month's date
        previous_month_str = date.strftime(date_format).upper()
        log_message(f"\tPeriode\t:\t{previous_month_str}", INFO)
        return f"{previous_month_str}"
    
    def get_file_name(self, step_name, date=None):
        # Load the report configuration
        report_config = load_report_config(self.report_name)
        # Get the file name components from the environment variable
        var_env_file_name = f"FILE_NAME_{self.report_name.upper()}"
        file_name_str = os.environ.get(var_env_file_name)
        if not file_name_str:
            raise ValueError(f"Environment variable {var_env_file_name} is not set")
        # Get the specific date format for the given report name from the config
        date_format = report_config.get(step_name).get("date_format", "%y-%m-%d")  # Default to "%y-%m-%d" if not specified
        
        if not date:
            # Calculate the current date in the desired format
            date = datetime.now()
            if self.report_name in PREV_MONTH_REPORTS:
                # Calculate the date for the previous month
                today = datetime.now()
                # Create a timedelta object representing one month
                one_month_ago = timedelta(days=31)  # Adjust for days in different months if needed
                # Subtract one month from the current date
                date = today - one_month_ago
        date = date.strftime(date_format)
        # Split the file name components
        file_name_lst = file_name_str.split(",")
        # Construct the final file name
        file_name = f"{file_name_lst[0]}{date}{file_name_lst[1]}"
        log_message(f"\t\tFile-{file_name}", INFO)
        return f"{self.report_name}/{file_name}"
        #return file_name

class Step:
    def __init__(self, report_name, name, images, action):
        self.report_name = report_name
        self.name = name
        self.images = images
        self.action = action

    def execute(self, manager):
        #StepExecutor.wait_for_image(self.images[0], report_name = self.report_name)
        action_method = manager.actions.get(self.action)
        if action_method:
            # Execute the action method and check for failures
            action_method(self.name, self.images)
            #if isinstance(result, str) and result.startswith("FAIL_STEP"):
            #    return result  # Return the failure step if it fails
        else:
            raise ValueError(f"Action {self.action} not found for step {self.name}")


class StepExecutor:
    @staticmethod
    def take_screenshot(step,report_name=""):
        if SCREENSHOTS:
            screenshot = pyautogui.screenshot()
            folder_path="/"
            if report_name:
                folder_path="/"+str(report_name)+"/"
            screenshot_path = f"screenshots{folder_path}{step}.bmp"
            screenshot.save(screenshot_path)
            last_screenshot_path = f"screenshots{folder_path}00_last_state.bmp"
            screenshot.save(last_screenshot_path)
            log_message(f"\tScreenshot {step}", INFO)

    @staticmethod
    def wait_for_image(image_file, report_name="", initial_sleep=MIN_SLEEP_TIME):
        log_message("\tInitiating image recognition on screen...", INFO)
        isUIfound = False
        patience = 0
        time.sleep(initial_sleep)
        log_message(f"\t\tScanning for visual element \t: {image_file}", INFO)
        image_name = os.path.splitext(os.path.basename(image_file))[0]
        while not isUIfound and patience < LIMIT:
            try:
                #time.sleep(MAX_SLEEP_TIME)
                elemUI = pyautogui.locateCenterOnScreen(image_file, grayscale=True)
                if elemUI is not None:
                    log_message(f"\t\tVisual element identified \t\t: {image_file}", INFO)
                    return elemUI
            except Exception as e:                
                log_message(f"\tIssue identifying visual element : {image_file}: {str(e)}", WARNING)
                StepExecutor.take_screenshot(image_name+"_searching", report_name=report_name)
            patience += 1
            log_message(f"\tMy patience: {str(patience)}", WARNING)
            time.sleep(MAX_SLEEP_TIME)
        log_message(f"\t\tUnable to identify visual element after {LIMIT} attempts \t\t: {image_file}", ERROR)
        StepExecutor.take_screenshot(image_name+"_notfound", report_name=report_name)
        raise FileNotFoundError(f"Image recognition failed - {image_file}")

    @staticmethod
    def long_wait_for_image(image_file, report_name="", initial_sleep=MIN_SLEEP_TIME):
        log_message("\tInitiating image recognition on screen...", INFO)
        isUIfound = False
        patience = 0
        time.sleep(initial_sleep)
        log_message(f"\t\tScanning for visual element \t: {image_file}", INFO)
        image_name = os.path.splitext(os.path.basename(image_file))[0]
        while not isUIfound and patience < MAX_LIMIT:
            try:
                #time.sleep(MAX_SLEEP_TIME)
                elemUI = pyautogui.locateCenterOnScreen(image_file, grayscale=True)
                if elemUI is not None:
                    log_message(f"\t\tVisual element identified \t\t: {image_file}", INFO)
                    return elemUI
            except Exception as e:                
                log_message(f"\tIssue identifying visual element : {image_file}: {str(e)}", WARNING)
                StepExecutor.take_screenshot(image_name+"_searching", report_name=report_name)
            patience += 1
            log_message(f"\tMy patience: {str(patience)}/{str(MAX_LIMIT)}", WARNING)
            time.sleep(MAX_SLEEP_TIME)
        log_message(f"\t\tUnable to identify visual element after {MAX_LIMIT} attempts \t\t: {image_file}", ERROR)
        StepExecutor.take_screenshot(image_name+"_notfound", report_name=report_name)
        raise FileNotFoundError(f"Image recognition failed - {image_file}")

    @staticmethod
    def wait_for_image_to_disappear(image_file, report_name="", initial_sleep=0):
        finalFlag=5
        isUIfound = True
        patience = 0
        log_message(f"\tMonitoring for visual element to disappear: {image_file}", INFO)
        image_name = os.path.splitext(os.path.basename(image_file))[0]
        while isUIfound and patience < finalFlag:
            try:
                elemUI = pyautogui.locateCenterOnScreen(image_file, grayscale=True)
                if elemUI is None:
                    log_message(f"\t\tVisual element disappeared \t: {image_file}", INFO)
                    StepExecutor.take_screenshot(image_name+"_disappeared", report_name=report_name)
                    return
                else:
                    pyautogui.click(elemUI) #prevent inactivity
                    StepExecutor.take_screenshot(image_name+"_current_status", report_name=report_name)
            except Exception as e:
                log_message(f"\tCycle {patience+1}/{finalFlag}: Awaiting visual element disappearance: {image_file}", INFO)
                patience += 1
            time.sleep(MIN_SLEEP_TIME)
    
    @staticmethod
    def check_image_exists(image_file, report_name="", initial_sleep=5):
        """
        Checks if an image exists on the screen.

        Args:
            image_file (str): Path to the image file.
            confidence (float, optional): Confidence level for image matching. Defaults to 0.9.

        Returns:
            tuple: Coordinates of the image center if found, None otherwise.
        """
        log_message("\tInitiating image recognition on screen...", INFO)
        time.sleep(initial_sleep)
        log_message(f"\t\tScanning for visual element \t: {image_file}", INFO)
        image_name = os.path.splitext(os.path.basename(image_file))[0]
        try:
            elemUI = pyautogui.locateCenterOnScreen(image_file, grayscale=True)
            if elemUI is not None:
                log_message(f"\t\tVisual element identified \t\t: {image_file}", INFO)
                StepExecutor.take_screenshot(image_name+"_check_found", report_name=report_name)
                return elemUI
        except Exception as e:
            log_message(f"\tIssue identifying visual element : {image_file}: {str(e)}", WARNING)
            StepExecutor.take_screenshot(image_name+"_check_notfound", report_name=report_name)
        log_message(f"Visual element not detected: {image_file}", WARNING)
        return None


if __name__ == "__main__":
    report_name = sys.argv[1] if len(sys.argv) > 1 else "duk008"
    config_path = os.path.join("config", f"{report_name}.json")
    
    # Check if the configuration file exists
    if not os.path.isfile(config_path):
        error_message = f"Process for report '{report_name}' is not allowed or does not exist."
        log_message(error_message, ERROR)
        sys.exit(error_message)  # Exit with the error message

    log_message(f"Loading configuration file : {config_path}", INFO)
    
    # Handle date argument for specific reports
    if report_name.lower() in PREV_MONTH_REPORTS:
        date = sys.argv[2] if len(sys.argv) > 2 else None
        if date:
            date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        if len(sys.argv) > 2:
            log_message("Warning: Date argument is ignored for this report.", WARNING)
        date = None
    
    periode_str = f"- periode : {date}" if date is not None else ''
    log_message(f"Start extraction for report: {report_name} {periode_str}", INFO)

    # Initialize AutomationManager and start the process
    manager = AutomationManager(report_name, date=date)
    result = manager.start()

    # Log and return either "Success" or the error message
    if result == "Success":
        log_message(f"Extraction Result - {result}", INFO)
        sys.exit(0)  # Exit with success
    else:
        log_message(f"Extraction Failed - {result}", ERROR)
        sys.exit(result)  # Exit with the error message

