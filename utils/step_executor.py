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

