#!/bin/bash

# Track the start time
SECONDS=0

# Change to the directory where the script and virtual environment are located
cd /root/Desktop/extraction-automation-main || exit 1

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

# keyboard fix - us pc105
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

# Capture exit status
exit_status=$?

# Calculate execution time
execution_time=$SECONDS

# ===============================
# PASSWORD EXPIRED HANDLING
# ===============================
#if echo "$python_output" | grep -q '^PASSWORD_EXPIRED:'; then
#  echo "Detected PASSWORD_EXPIRED entries in python output"
#
#  echo "$python_output" | grep '^PASSWORD_EXPIRED:' | cut -d: -f2- | sed 's/^\s*//;s/\s*$//' | sort -u | while read -r expired_user; do
#    echo "expired credentials: $expired_user"
#
#    # Mark credential as expired
#    if [[ -x "scripts/mark_credential_expired.sh" ]]; then
#      scripts/mark_credential_expired.sh config/credentials.json "$expired_user" || true
#    else
#      bash scripts/mark_credential_expired.sh config/credentials.json "$expired_user" || true
#    fi
#
#    # Notify operators
#    if [[ -x "notifications/notify.sh" || -f "notifications/notify.sh" ]]; then
#      ./notifications/notify.sh "$report_name" "PASSWORD_EXPIRED" "Password expired for user $expired_user" || true
#    fi
#  done
#fi

# ===============================
# LOGIN ERROR HANDLING (NEW)
# ===============================
#if echo "$python_output" | grep -q '^LOGIN_ERROR:'; then
#  echo "Detected LOGIN_ERROR entries in python output"
#
#  echo "$python_output" | grep '^LOGIN_ERROR:' | cut -d: -f2- | sed 's/^\s*//;s/\s*$//' | sort -u | while read -r login_user; do
#    echo "login error for credentials: $login_user"
#
#    # Notify operators
#    if [[ -x "notifications/notify.sh" || -f "notifications/notify.sh" ]]; then
#      ./notifications/notify.sh "$report_name" "LOGIN_ERROR" "Login error for user $login_user" || true
#    fi
#  done
#fi

# ===============================
# FAILURE HANDLING
# ===============================
if [ $exit_status -ne 0 ]; then
  echo "Python script failed with message:"
  echo "$python_output"

  # PRIORITY 1: Check for Password Expired
  # If this is found, we execute this block and SKIP the Login Error block.
  if echo "$python_output" | grep -q '^PASSWORD_EXPIRED:'; then
    expired_user=$(echo "$python_output" | grep '^PASSWORD_EXPIRED:' | head -n1 | cut -d: -f2-)
    echo "expired credentials: $expired_user"

    if [[ -x "scripts/mark_credential_expired.sh" ]]; then
      scripts/mark_credential_expired.sh config/credentials.json "$expired_user" || true
    else
      bash scripts/mark_credential_expired.sh config/credentials.json "$expired_user" || true
    fi

    if [[ -x "notifications/notify.sh" || -f "notifications/notify.sh" ]]; then
      ./notifications/notify.sh "$report_name" "PASSWORD_EXPIRED" "Password expired for user $expired_user" || true
    fi

  # PRIORITY 2: Check for Login Error
  # This runs ONLY if 'PASSWORD_EXPIRED' was NOT found above.
  elif echo "$python_output" | grep -q '^LOGIN_ERROR:'; then
    login_error_user=$(echo "$python_output" | grep '^LOGIN_ERROR:' | head -n1 | cut -d: -f2-)
    echo "login error credentials: $login_error_user"

    if [[ -x "notifications/notify.sh" || -f "notifications/notify.sh" ]]; then
      ./notifications/notify.sh "$report_name" "LOGIN_ERROR" "Login error for user $login_error_user" || true
    fi
  fi

  # Update stats as failure
  ./stats/append_stats.sh "$report_name" "$execution_time" "$STATUS_FAIL"
  exit 1
else
  # Success stats
  ./stats/append_stats.sh "$report_name" "$execution_time" "$STATUS_SUCCESS"
fi

# ===============================
# NEXT STEP
# ===============================
echo "Send File"
./report_transfer.sh "$report_name"
