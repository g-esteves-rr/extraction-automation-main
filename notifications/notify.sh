#!/bin/bash

# Change to the directory where the script and virtual environment are located
cd /root/Desktop/extraction-automation-main || exit 1

# Activate virtual environment
source env_automation/bin/activate

# Check for activation (optional)
if [ -z "$VIRTUAL_ENV" ]; then
  echo "Error: Failed to activate virtual environment!"
  exit 1
fi

# Function to read environment variables from .env file
read_env_var() {
  local var_name="$1"
  if grep -Eq "^$var_name=" .env; then
    local var_value
    var_value=$(grep -E "^$var_name=" .env | cut -d '=' -f2- | tr -d '"')
    export "$var_name"="$var_value"
  else
    echo "Warning: Variable '$var_name' not found in .env"
  fi
}

# Function to read environment variables without stripping quotes
read_env_var_pass() {
  local var_name="$1"
  if grep -Eq "^$var_name=" .env; then
    local var_value
    var_value=$(grep -E "^$var_name=" .env | cut -d '=' -f2-)
    export "$var_name"="$var_value"
  else
    echo "Warning: Variable '$var_name' not found in .env"
  fi
}

# Read common environment variables
read_env_var "FTP_SERVER"
read_env_var "FTP_PORT"
read_env_var "FTP_USER"
read_env_var_pass "FTP_PASS"
read_env_var "LOCAL_DESTINATION_FOLDER_PATH"
read_env_var "VALID_REPORTS"
read_env_var "NOTIFY_URL"
read_env_var "SERVER_NAME"

# Validate required variables
if [[ -z "$FTP_SERVER" || -z "$FTP_PORT" || -z "$FTP_USER" || -z "$FTP_PASS" || -z "$VALID_REPORTS" || -z "$NOTIFY_URL" || -z "$SERVER_NAME" ]]; then
  echo "Error: Missing environment variables. Please configure .env properly."
  exit 1
fi

# Convert VALID_REPORTS to array
IFS=',' read -r -a valid_reports <<< "${VALID_REPORTS:-}"

# Get arguments
report_name=$(tr '[:lower:]' '[:upper:]' <<< "$1" | xargs)
status="$2"
error_message="${3:-""}"

# Validate args
if [[ -z "$report_name" || -z "$status" ]]; then
  echo "Usage: $0 <report_name> <status> [error_message]"
  exit 1
fi

# ===============================
# SPECIAL ALERTS (UPDATED)
# ===============================
SPECIAL_ALERTS=("PASSWORD_EXPIRED" "LOGIN_ERROR")

is_special=false
for alert in "${SPECIAL_ALERTS[@]}"; do
  if [[ "$report_name" == "$alert" || "$status" == "$alert" ]]; then
    is_special=true
    break
  fi
done

# Validate report name if not special
if [[ "$is_special" == false ]]; then
  found=false
  for valid_report in "${valid_reports[@]}"; do
    if [[ "$(echo "$valid_report" | xargs)" == "$report_name" ]]; then
      found=true
      break
    fi
  done

  if [[ "$found" == false ]]; then
    echo "Error: Invalid report name '$report_name'. Valid options are: ${valid_reports[*]}"
    exit 1
  fi
fi

# ===============================
# BUILD & SEND NOTIFICATION
# ===============================

safe_error_message=$(echo "$error_message" | tail -n 2)
wrapped_error_message="\`$safe_error_message\`"

json_payload=$(mktemp)
cat <<EOF > "$json_payload"
{
  "report": "$report_name",
  "status": "$status",
  "source_server": "$SERVER_NAME",
  "extra": "$wrapped_error_message"
}
EOF

curl -sS -X POST "$NOTIFY_URL" \
  -H "Content-Type: application/json" \
  -d @"$json_payload"

curl_exit=$?

rm "$json_payload"

if [ $curl_exit -ne 0 ]; then
  echo "Error: Failed to send notification"
  exit 1
fi

echo "Notification sent: $report_name / $status"

# Cleanup sensitive env vars
unset FTP_SERVER FTP_PORT FTP_USER FTP_PASS LOCAL_DESTINATION_FOLDER_PATH VALID_REPORTS NOTIFY_URL SERVER_NAME
