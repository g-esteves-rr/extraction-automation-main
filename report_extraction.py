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

from utils.logs import log_message
from utils import actions
from utils.notifications import send_notification
from utils.credentials import (
    load_credentials,
    mark_expired,
    update_status,
)

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
creds_path = os.getenv('CREDENTIALS_PATH', './config/credentials.json')

# Logs
logging.basicConfig(filename='activity_logs.log', level=logging.INFO, format='%(asctime)s - %(levelname)s \t- %(message)s')


class AutomationManager:
    def __init__(self, report_name, date=None):
        self.browser_instance = None
        self.steps = []
        self.report_name = report_name
        self.date = date
        # report_config will be loaded after successful login for the selected user
        self.report_config = None
        self.actions = {
                "perform_login": actions.perform_login,
                "perform_check_password_expired": actions.perform_check_password_expired,
                "perform_select_responsabilite": actions.perform_select_responsabilite,
                "perform_accept_optional": actions.perform_accept_optional,
                "perform_browse": actions.perform_browse,
                "perform_select_periode": actions.perform_select_periode,
                "perform_wait": actions.perform_wait,
                "perform_long_wait": actions.perform_long_wait,
                "perform_wait_large_query": actions.perform_wait_large_query,
                "perform_wait_large_query_duk008": actions.perform_wait_large_query_duk008,
                "perform_extract": actions.perform_extract,
                "perform_extract_ic01": actions.perform_extract_ic01,
                "perform_download": actions.perform_download,
                "perform_conditions":actions.perform_conditions,
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
        """
        Try credentials sequentially.
        - Uses utils.credentials as the single source of truth
        - Marks expired credentials
        - Sends notifications
        - Loads per-user steps on success
        """
        log_message(f"Loading credentials from {creds_path}", INFO)
        try:
            credentials = load_credentials(creds_path)
        except Exception as e:
            log_message(f"Failed to load credentials: {e}", ERROR)
            raise

        if not credentials:
            raise Exception("No credentials available")

        last_error = None

        for account in credentials:
            username = account.get("username")
            user_folder = account.get("config_folder") or username.upper()

            log_message(f"Trying user {username}", INFO)

            # Always start clean
            try:
                self.close_browser()
            except Exception:
                pass

            self.browser_instance = self.open_browser("FIREFOX")
            self.current_account = account

            # Load user-specific config
            try:
                report_conf = actions.load_report_config(self.report_name, user_folder=user_folder)
            except Exception as e:
                log_message(f"Config not found for user {username}: {e}", WARNING)
                last_error = e
                continue

            # Find login step
            login_step = None
            pwd_check_step = None

            for step_name, step in report_conf.items():
                if step.get("action") == "perform_login":
                    login_step = (step_name, step.get("images"))
                elif step.get("action") == "perform_check_password_expired":
                    pwd_check_step = (step_name, step.get("images"))

            if not login_step:
                log_message(f"No login step for user {username}", WARNING)
                continue

            # --- LOGIN ---
            try:
                actions.perform_login(self, login_step[0], login_step[1])
            except Exception as e:
                log_message(f"Login UI failed for {username}: {e}", WARNING)
                last_error = e
                continue

            # --- PASSWORD CHECK ---
            try:
                if pwd_check_step:
                    actions.perform_check_password_expired(
                        self,
                        pwd_check_step[0],
                        pwd_check_step[1]
                    )

                # USER IS VALID
                log_message(f"Login successful for {username}", INFO)
                print(f"LOGIN_CONFIRMED:{username}")

                update_status(creds_path, username, "SUCCESS")

                # Remove login steps
                cleaned_conf = {
                    k: v for k, v in report_conf.items()
                    if v.get("action") not in (
                        "perform_login",
                        "perform_check_password_expired",
                    )
                }

                self.report_config = cleaned_conf
                self.load_steps()

                return True

            except Exception as e:
                msg = str(e).lower()

                # PASSWORD EXPIRED
                if "expired" in msg:
                    log_message(f"Password expired for {username}", WARNING)

                    mark_expired(creds_path, username)

                    send_notification(
                        report=self.report_name,
                        status="PASSWORD_EXPIRED",
                        message=f"Password expired for user {username}",
                    )

                    print(f"PASSWORD_EXPIRED:{username}")
                    last_error = e
                    continue

                # LOGIN ERROR
                else:
                    log_message(f"Login error for {username}: {e}", WARNING)

                    update_status(creds_path, username, "FAILED")

                    send_notification(
                        report=self.report_name,
                        status="LOGIN_ERROR",
                        message=f"Login error for user {username}",
                    )

                    print(f"LOGIN_ERROR:{username}")
                    last_error = e
                    continue

        # If all users failed
        log_message("No valid credentials found", ERROR)

        if last_error:
            raise last_error

        raise Exception("No valid credentials found")

    def start(self, browser="FIREFOX", max_retries=10):
        """
        Start the extraction process.

        Behaviour:
        - Selects a valid user once (credentials logic)
        - Executes extraction steps
        - If failure is NOT credential-related:
            retry up to `max_retries`
        - If credential-related failure:
            stop immediately
        """

        attempt = 1
        last_error = None

        while attempt <= max_retries:
            log_message(f"Extraction attempt {attempt}/{max_retries}", INFO)
            print(f"[INFO] Extraction attempt {attempt}/{max_retries}")

            try:
                # LOGIN + LOAD STEPS (ONLY ON FIRST ATTEMPT)
                if attempt == 1:
                    try:
                        self.select_and_login_and_load_steps()
                    except Exception as e:
                        # Credential-related failures → NO RETRY
                        error_msg = f"Login/setup failed: {str(e)}"
                        log_message(error_msg, ERROR)
                        print(f"[ERROR] {error_msg}")

                        # Optional notification hook
                        # send_notification(self.report_name, "FAIL", error_msg)

                        return error_msg

                # EXECUTE STEPS
                for step in self.steps:
                    log_message(f"Executing step: {step.name}", INFO)
                    log_message(f"Images: {step.images}", INFO)

                    step.execute(self)

                # SUCCESS
                self.close_browser()
                log_message("Extraction finished successfully", INFO)
                print("[SUCCESS] Extraction completed")
                return "Success"

            except FileNotFoundError as e:
                # UI / IMAGE DETECTION → RETRY
                last_error = f"UI detection error: {str(e)}"
                log_message(last_error, WARNING)
                print(f"[WARN] {last_error}")

            except Exception as e:
                # GENERIC NON-CREDENTIAL ERROR → RETRY
                last_error = f"Runtime error: {str(e)}"
                log_message(last_error, WARNING)
                print(f"[WARN] {last_error}")

            finally:
                # Always close browser before retry
                try:
                    self.close_browser()
                except Exception:
                    pass

            attempt += 1
            time.sleep(3)

        # FINAL FAILURE AFTER RETRIES
        final_error = (
            f"Extraction failed after {max_retries} attempts. "
            f"Last error: {last_error}"
        )

        log_message(final_error, ERROR)
        print(f"[ERROR] {final_error}")

        # Optional notification hook
        # send_notification(self.report_name, "FAIL", final_error)

        return final_error

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



    def get_date_prev_month(self, step_name, date=None):
        # Load the report configuration
        report_config = actions.load_report_config(self.report_name)
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
        report_config = actions.load_report_config(self.report_name)
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
        action_method = manager.actions.get(self.action)
        if action_method:
            # Execute the action method and check for failures
            action_method(manager, self.name, self.images)
        else:
            raise ValueError(f"Action {self.action} not found for step {self.name}")



if __name__ == "__main__":
    report_name = sys.argv[1] if len(sys.argv) > 1 else "duk008"
    
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

