#!/usr/bin/env python
import pyautogui
import os
import sys
import time
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Settings
CONFIDENCE = 0.5
LIMIT = 5
SLEEP = 3
PRINT_MESSAGES = True
SCREENSHOT_DIR = "resolution_test_screenshots"

logging.basicConfig(filename='activity_logs.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

def log_message(msg, level="INFO"):
    if PRINT_MESSAGES:
        print(f"{datetime.now().strftime('%H:%M:%S')} - {level}: {msg}")
    getattr(logging, level.lower())(msg)

def load_first_image(report_name):
    config_path = os.path.join("config", f"{report_name}.json")
    if not os.path.isfile(config_path):
        log_message(f"Config file not found for report {report_name}", "ERROR")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = json.load(f)

    # Grab first step and its first image
    first_step = next(iter(config.values()))
    first_image = first_step.get("images", [None])[0]
    if not first_image:
        log_message(f"No images defined in first step of {report_name}", "ERROR")
        sys.exit(1)

    return first_image


def save_screenshot(label):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"{label}_{int(time.time())}.png")
    screenshot = pyautogui.screenshot()
    screenshot.save(path)
    log_message(f"Screenshot saved: {path}")

def detect_image(image_file):
    patience = 0
    while patience < LIMIT:
        log_message(f"Looking for {image_file}, attempt {patience+1}/{LIMIT}")
        save_screenshot(f"attempt_{patience+1}")  # save screenshot for each attempt
        try:
            elem = pyautogui.locateCenterOnScreen(image_file, confidence=CONFIDENCE, grayscale=True)
            if elem:
                log_message(f"Image detected: {image_file} at {elem}")
                save_screenshot("success")  # save screenshot when found
                return True
        except Exception as e:
            log_message(f"Error detecting {image_file}: {e}", "WARNING")
        patience += 1
        time.sleep(SLEEP)
    save_screenshot("failed")  # save screenshot on final failure
    return False

if __name__ == "__main__":
    report_name = sys.argv[1] if len(sys.argv) > 1 else "duk008"
    image = load_first_image(report_name)

    log_message(f"Testing first image for report {report_name}: {image}")

    if detect_image(image):
        sys.exit(0)   # success
    else:
        sys.exit(1)   # fail
def detect_image(image_file):
    patience = 0
    while patience < LIMIT:
        log_message(f"Looking for {image_file}, attempt {patience+1}/{LIMIT}")
        save_screenshot(f"attempt_{patience+1}")  # save screenshot for each attempt
        try:
            elem = pyautogui.locateCenterOnScreen(image_file, confidence=CONFIDENCE, grayscale=True)
            if elem:
                log_message(f"Image detected: {image_file} at {elem}")
                save_screenshot("success")  # save screenshot when found
                return True
        except Exception as e:
            log_message(f"Error detecting {image_file}: {e}", "WARNING")
        patience += 1
        time.sleep(SLEEP)
    save_screenshot("failed")  # save screenshot on final failure
    return False

if __name__ == "__main__":
    report_name = sys.argv[1] if len(sys.argv) > 1 else "duk008"
    image = load_first_image(report_name)

    log_message(f"Testing first image for report {report_name}: {image}")

    if detect_image(image):
        sys.exit(0)   # success
    else:
        sys.exit(1)   # fail
