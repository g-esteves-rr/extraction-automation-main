#!/bin/bash

# Track the start time
SECONDS=0

# Change to the directory where the script and virtual environment are located
cd /root/Desktop/extraction-automation-main

# Activate virtual environment
source env_automation/bin/activate

# Check for activation (optional)
if [ ! -n "$VIRTUAL_ENV" ]; then
  echo "Error: Failed to activate virtual environment!"
  exit 1
fi

# Function to read environment variables from .env file
read_env_var() {
  var_name="$1"
  if grep -Eq "^$var_name=" .env; then
    var_value=$(grep -E "^$var_name=" .env | cut -d '=' -f2- | tr -d '"')
    export "$var_name"="$var_value"
  else
    echo "Warning: Variable '$var_name' not found in .env"
  fi
}

read_env_var "STATUS_START"
read_env_var "STATUS_FAIL"
read_env_var "STATUS_SUCCESS"
read_env_var "HEADLESS"
read_env_var "VSCREEN_W"
read_env_var "VSCREEN_H"
read_env_var "VSCREEN_DPI"

# force dark widgets inside the virtual display
#export GTK_THEME=Adwaita:dark

# keyboard fix - us pc105 - due to problem of 7 instead of /
command -v setxkbmap >/dev/null 2>&1 && setxkbmap -layout us -model pc105 || true

# Get report name from the first argument (if provided)
report_name=""
if [ $# -ge 1 ]; then
  report_name="$1"
fi

# Get date from the second argument (if provided)
date=""
if [ $# -ge 2 ]; then
  date="$2"
fi

# Notify that the process has started
#./notifications/notify.sh "$report_name" "$STATUS_START"

# Run the Python script based on HEADLESS mode
if [ "$HEADLESS" = "true" ]; then
  if [ -n "$date" ]; then
    python_output=$(xvfb-run --server-args="-screen 0 1892x880x24 -dpi 96" python3 report_extraction.py "$report_name" "$date" 2>&1)
  else
    python_output=$(xvfb-run --server-args="-screen 0 1892x880x24 -dpi 96" python3 report_extraction.py "$report_name" 2>&1)
  fi
else
  if [ -n "$date" ]; then
    python_output=$(python3 report_extraction.py "$report_name" "$date" 2>&1)
  else
    python_output=$(python3 report_extraction.py "$report_name" 2>&1)
  fi
fi

# Check the exit status of the Python script
exit_status=$?

# Calculate execution time
execution_time=$SECONDS

if [ $exit_status -ne 0 ]; then
  echo "Python script failed with message: $python_output"
  
  # Send failure notification with the error message
  #./notifications/notify.sh "$report_name" "$STATUS_FAIL" "$python_output"
  #"ERROR on Extraction"
  #"$python_output"
  
  # Update stats with the failure status and execution time
  ./stats/append_stats.sh "$report_name" "$execution_time" "$STATUS_FAIL"
  exit 1
else
  # Update stats with the success status and execution time
  ./stats/append_stats.sh "$report_name" "$execution_time" "$STATUS_SUCCESS"
fi

# If successful, continue to the next step
echo "Send File"
./report_transfer.sh "$report_name"

