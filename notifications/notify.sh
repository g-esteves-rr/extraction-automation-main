#!/bin/bash

# Change to the directory where the script and virtual environment are located
cd /root/Desktop/extraction-automation-main

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
read_env_var "VALID_REPORTS"  # Load the list of valid reports from the .env file
read_env_var "NOTIFY_URL"
read_env_var "SERVER_NAME"

# Validate and handle missing environment variables
if [[ -z "$FTP_SERVER" || -z "$FTP_PORT" || -z "$FTP_USER" || -z "$FTP_PASS" || -z "$VALID_REPORTS" || -z "$NOTIFY_URL" || -z "$SERVER_NAME" ]]; then
  echo "Error: Missing environment variables. Please configure FTP credentials, server details, and valid reports in .env file."
  exit 1
fi

# Convert VALID_REPORTS to an array (may be empty for special alerts)
IFS=',' read -r -a valid_reports <<< "${VALID_REPORTS:-}"

# Get report name, status, and optional error message from the script arguments
report_name=$(tr '[:lower:]' '[:upper:]' <<< "$1" | xargs)  # Convert to uppercase and trim spaces
status="$2"
error_message="${3:-""}"  # Third argument is optional, default to empty string if not provided

# Validate arguments
if [[ -z "$report_name" || -z "$status" ]]; then
  echo "Usage: $0 <report_name> <status> [error_message]"
  exit 1
fi

# If this is a special password expiration alert, bypass the VALID_REPORTS check
if [[ "$report_name" == "PASSWORD_EXPIRED" || "$status" == "PASSWORD_EXPIRED" ]]; then
  found=true
else
  # Check if provided report name is valid (case-insensitive)
  found=false
  for valid_report in "${valid_reports[@]}"; do
    # Trim whitespace from valid_report and compare with report_name
    if [[ "$(echo $valid_report | xargs)" == "$report_name" ]]; then
      found=true
      break
    fi
  done

  if [[ "$found" == false ]]; then
    echo "Error: Invalid report name '$report_name'. Valid options are: ${valid_reports[*]}"
    exit 1
  fi
fi

# Local temporary file
tmp_file=$(mktemp)
updated_file="notifications_general.json"
REMOTE_DIR="ftp://$FTP_SERVER:$FTP_PORT/00_notifications/"

#Send notification via API
# Properly escape double quotes and backslashes in the error message
#safe_error_message=$(echo "$error_message" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')

# Now safely build the JSON
#curl -X POST "$NOTIFY_URL" -H "Content-Type: application/json" -d "{\"report\":\"$report_name\",\"status\":\"$status\",\"source_server\":\"$SERVER_NAME\",\"extra\":\"$safe_error_message\"}"
# Build the JSON safely with jq
#json_payload=$(jq -n \
#  --arg report "$report_name" \
#  --arg status "$status" \
#  --arg source_server "$SERVER_NAME" \
#  --arg extra "$error_message" \
#  '{report: $report, status: $status, source_server: $source_server, extra: $extra}')

# Send it
#curl -X POST "$NOTIFY_URL" -H "Content-Type: application/json" -d "$json_payload"

# START SECTION OLD NOTIFCATIONS
# Remote file
#remote_file="notifications_general.json"

# Change to the script's directory
cd /root/Desktop/extraction-automation-main/notifications || exit 1

# Ensure notifications.json exists locally
#if [ ! -f "$updated_file" ]; then
#  echo "[]" >"$updated_file"
#fi

# Download the remote file if possible
#if ! curl -u "$FTP_USER:$FTP_PASS" "$REMOTE_DIR/$remote_file" -o "$tmp_file"; then
#  echo "Warning: Failed to download $remote_file. Using local file."
#  cp "$updated_file" "$tmp_file"
#else
# Merge remote notifications with local notifications
#  jq -s '.[0] + .[1]' "$tmp_file" "$updated_file" >"$tmp_file.merge" && mv "$tmp_file.merge" "$tmp_file"
#fi

# Run the Python script to update the JSON file, passing the error message if available
#if ! python3 update_notifications.py "$tmp_file" "$updated_file" "$report_name" "$status" "$error_message"; then
#  echo "Error: Python script failed"
#  rm -f "$tmp_file"
#  exit 1
#fi

# Upload the updated file
#if curl -T "$updated_file" -u "$FTP_USER:$FTP_PASS" "$REMOTE_DIR$remote_file"; then
#  echo "Successfully uploaded $remote_file"
#  # Clear local notifications file upon successful upload
#  echo "[]" >"$updated_file"
#else
#  echo "Error: Failed to upload $remote_file. Keeping local notifications for future upload."
#fi

# END SECTION OLD NOTIFCATIONS

# Removes all double quotes and replaces colons
#sanitized_error_message=$(echo "$error_message" | sed 's/"/'\''/g' | sed 's/:/-/g' | tr '\n' ' ' | tr '\r' ' ')

#curl -X POST "$NOTIFY_URL" -H "Content-Type: application/json" -d "$(printf '{"report":"%s","status":"%s","source_server":"%s","extra":"%s"}' "$report_name" "$status" "$SERVER_NAME" "$error_message")"

#
# Safely extract last 20 lines, escape backslashes, quotes, newlines
#safe_error_message=$(echo "$error_message" | tail -n 5 | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
#safe_error_message=$(echo "$error_message" | tail -n 5 | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
safe_error_message=$(echo "$error_message" | tail -n 2 )

#wrapped_error_message="$safe_error_message"

wrapped_error_message="\`$safe_error_message\`"

# Build JSON payload into a temporary file
json_payload=$(mktemp)
cat <<EOF > "$json_payload"
{
    "report": "$report_name",
    "status": "$status",
    "source_server": "$SERVER_NAME",
    "extra": "$wrapped_error_message"
}
EOF

# Send the POST request safely using file input
curl -X POST "$NOTIFY_URL" \
    -H "Content-Type: application/json" \
    -d @"$json_payload"

# Cleanup temp file
rm "$json_payload"

# Get last 10 lines of the error message (if it's multiline), then sanitize
#sanitized_error_message=$(echo "$error_message" | tail -n 10 | sed 's/"/'\''/g' | sed 's/:/-/g' | tr '\n' ' ' | tr '\r' ' ')

# Send via curl
#curl -X POST "$NOTIFY_URL" \
#  -H "Content-Type: application/json" \
#  -d "$(printf '{"report":"%s","status":"%s","source_server":"%s","extra":"%s"}' "$report_name" "$status" "$SERVER_NAME" "$sanitized_error_message")"

#curl -X POST "$NOTIFY_URL" -H "Content-Type: application/json" -d "$(printf '{"report":"1%s","status":"%s","source_server":"%s","extra":"%s"}' "$report_name" "$status" "$SERVER_NAME" "$error_message")"

#json_payload=$(jq -n --arg report "$report_name" --arg status "$status" --arg source_server "$SERVER_NAME" --arg extra "$error_message" '{report: $report, status: $status, source_server: $source_server, extra: $extra}')

#echo "Sending JSON:"
#echo "$json_payload"

#curl -sS -X POST "$NOTIFY_URL" \
#  -H "Content-Type: application/json" \
#  -d "$json_payload"


# Send notification via API
#payload=$(printf '{"report":"%s","status":"%s","source_server":"%s","extra":"%s"}' "$report_name" "$status" "$SERVER_NAME" "$error_message")

#if ! curl -sS -X POST "$NOTIFY_URL" -H "Content-Type: application/json" -d "$payload"; then
#  echo "Error: Failed to send API notification"
#else
#  echo "Notification sent: $status - $report_name"
#fi

# Cleanup
rm -f "$tmp_file"

# Optional: Unset environment variables for security
unset FTP_SERVER FTP_PORT FTP_USER FTP_PASS LOCAL_DESTINATION_FOLDER_PATH VALID_REPORTS NOTIFY_URL SERVER_NAME
