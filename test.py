#!/usr/bin/env python
import pyautogui
import subprocess
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta

# --- Config (your exact paths) ---
FIREFOX_PATH = "/root/Desktop/Browser/firefox-sdk/bin/firefox"
FIREFOX_PROFILE_PATH = "/root/.mozilla/firefox/svfz90d1.default-esr"

# --- Minimal HTML to show DARK/LIGHT via prefers-color-scheme ---
HTML_CONTENT = """<!doctype html>
<meta charset="utf-8">
<title>Dark mode check</title>
<style>
  html,body { height:100%; margin:0; }
  body { display:flex; align-items:center; justify-content:center; font-family:sans-serif; font-size:64px; }
  @media (prefers-color-scheme: dark)  { body{ background:#111; color:#eee; } }
  @media (prefers-color-scheme: light) { body{ background:#fff; color:#111; } }
</style>
<div id="out">Detecting…</div>
<script>
  const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  document.getElementById('out').textContent = dark ? 'DARK MODE' : 'LIGHT MODE';
</script>
"""

def write_test_html():
    path = "/tmp/darkmode_check.html"
    with open(path, "w") as f:
        f.write(HTML_CONTENT)
    return path

def estimate_brightness(img, box_ratio=0.5, step=20):
    """Estimate brightness (0-255) from a central region without importing PIL explicitly."""
    w, h = img.size
    cx, cy = w // 2, h // 2
    half_w = int(w * box_ratio / 2)
    half_h = int(h * box_ratio / 2)
    x0 = max(0, cx - half_w)
    y0 = max(0, cy - half_h)
    x1 = min(w, cx + half_w)
    y1 = min(h, cy + half_h)

    total = 0
    count = 0
    for y in range(y0, y1, max(1, step)):
        for x in range(x0, x1, max(1, step)):
            r, g, b = img.getpixel((x, y))[:3]
            total += (r + g + b) // 3
            count += 1
    return (total // count) if count else 0

def take_screenshot_bmp(step, report_name=""):
    """Your exact style: pyautogui.screenshot() -> BMP saved twice (step + 00_last_state)."""
    screenshot = pyautogui.screenshot()
    folder_path = "/"
    if report_name:
        folder_path = "/" + str(report_name) + "/"
    out_dir = "screenshots" + folder_path
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    screenshot_path = f"{out_dir}{step}.bmp"
    screenshot.save(screenshot_path)
    last_screenshot_path = f"{out_dir}00_last_state.bmp"
    screenshot.save(last_screenshot_path)
    return screenshot, screenshot_path

def main():
    html_path = write_test_html()
    url = "file://" + html_path

    # Launch Firefox with the same profile & a new instance
    cmd = [FIREFOX_PATH, "--profile", FIREFOX_PROFILE_PATH, "-no-remote", url]
    proc = subprocess.Popen(cmd)

    try:
        # Give Firefox time to render the page under Xvfb
        time.sleep(6)

        # Try to focus the window and fullscreen (helps the screenshot)
        try:
            w, h = pyautogui.size()
            pyautogui.click(w // 2, h // 2)
            time.sleep(0.2)
            pyautogui.press('f11')
        except Exception:
            pass

        time.sleep(1.2)

        # Take screenshot in your exact format
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        img, path = take_screenshot_bmp(step=f"darkmode_check_{ts}", report_name="darkmode")

        # Decide DARK vs LIGHT by central brightness (no extra libs)
        mean = estimate_brightness(img, box_ratio=0.6, step=20)
        mode = "DARK" if mean < 128 else "LIGHT"

        # Print ONLY the mode (so you can capture cleanly with $(...))
        print(mode)

    finally:
        # Close Firefox we spawned
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main() or 0)
