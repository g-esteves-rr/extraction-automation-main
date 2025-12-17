#!/bin/bash

# Track the start time
SECONDS=0

# Change to project dir
cd /root/Desktop/extraction-automation-main

# Activate virtual environment
source env_automation/bin/activate

if [ -z "$VIRTUAL_ENV" ]; then
  echo "Error: Failed to activate virtual environment!"
  exit 1
fi

# Read .env vars helper
read_env_var() {
  var_name="$1"
  if grep -Eq "^$var_name=" .env; then
    var_value=$(grep -E "^$var_name=" .env | cut -d '=' -f2- | tr -d '"')
    export "$var_name"="$var_value"
  fi
}

# Read important vars
read_env_var "STATUS_START"
read_env_var "STATUS_FAIL"
read_env_var "STATUS_SUCCESS"
read_env_var "HEADLESS"
read_env_var "VSCREEN_W"
read_env_var "VSCREEN_H"
read_env_var "VSCREEN_DPI"

BASE_W=${VSCREEN_W:-1892}
BASE_H=${VSCREEN_H:-880}
DPI=${VSCREEN_DPI:-96}

report_name="$1"
date="$2"

# Test loop: -50 to +50 in steps of 1 pixel
for dw in $(seq -40 8 40); do   # steps of 8
  for dh in $(seq -40 8 40); do
    W=$((BASE_W + dw))
    H=$((BASE_H + dh))
    echo "Testing resolution ${W}x${H}..."

    if [ "$HEADLESS" = "true" ]; then
      if [ -n "$date" ]; then
        python_output=$(xvfb-run --server-args="-screen 0 ${W}x${H}x24 -dpi $DPI -keybd evdev,,xkbrules=evdev,xkbmodel=pc105,xkblayout=us" \
          python3 resoluction_detector.py "$report_name" "$date" >tmp_output.log 2>&1)
      else
        python_output=$(xvfb-run --server-args="-screen 0 ${W}x${H}x24 -dpi $DPI -keybd evdev,,xkbrules=evdev,xkbmodel=pc105,xkblayout=us" \
          python3 resoluction_detector.py "$report_name" >tmp_output.log 2>&1)
      fi
    else
      if [ -n "$date" ]; then
        python_output=$(python3 resoluction_detector.py "$report_name" "$date" >tmp_output.log 2>&1)
      else
        python_output=$(python3 resoluction_detector.py "$report_name" >tmp_output.log 2>&1)
      fi
    fi
    
    exit_status=$?
    python_output=$(<tmp_output.log)


    if [ $exit_status -eq 0 ]; then
      echo "✅ SUCCESS at resolution ${W}x${H}"
      exit 0
    else
      echo "❌ FAIL at resolution ${W}x${H} -> $python_output"
    fi
  done
done

echo "No resolution worked!"
exit 1
