#!/bin/bash

# Change to the directory where the script and virtual environment are located
cd /root/Desktop/extraction-automation-main/schedule

# Activate virtual environment
source ../env_automation/bin/activate

# Check for activation (optional)
if [ ! -n "$VIRTUAL_ENV" ]; then
  echo "Error: Failed to activate virtual environment!"
  exit 1
fi

# Function to read environment variables from .env file
read_env_var() {
  var_name="$1"
  if grep -Eq "^$var_name=" ../.env; then
    var_value=$(grep -E "^$var_name=" ../.env | cut -d '=' -f2- | tr -d '"')
    export "$var_name"="$var_value"
  else
    echo "Warning: Variable '$var_name' not found in .env"
  fi
}

read_env_var_pass() {
  var_name="$1"
  if grep -Eq "^$var_name=" ../.env; then
    var_value=$(grep -E "^$var_name=" ../.env | cut -d '=' -f2-)
    export "$var_name"="$var_value"
  else
    echo "Warning: Variable '$var_name' not found in .env"
  fi
}

# Read FTP and local destination environment variables
read_env_var "FTP_SERVER"
read_env_var "FTP_PORT"
read_env_var "FTP_USER"
read_env_var_pass "FTP_PASS"
read_env_var "SCHEDULE_PATH"

# Validate and handle missing environment variables
if [[ -z "$FTP_SERVER" || -z "$FTP_PORT" || -z "$FTP_USER" || -z "$FTP_PASS" ]]; then
  echo "Error: Missing environment variables. Please configure FTP credentials and server details in .env file."
  exit 1
fi

# Download schedule_discoverer.json from the FTP server
REMOTE_FILE="ftp://$FTP_USER:$FTP_PASS@$FTP_SERVER:$FTP_PORT/02_schedule/schedule_discoverer.json"
LOCAL_FILE="../${SCHEDULE_PATH}/schedule_discoverer.json"

# Download the file using curl
curl -o "$LOCAL_FILE" "$REMOTE_FILE"

# Check if the download was successful
if [ $? -ne 0 ]; then
  echo "Error: Failed to download schedule_discoverer.json from the FTP server."
  exit 1
fi

dos2unix "$LOCAL_FILE"

# Get the current date
current_date=$(date +%Y-%m-%d)

# Function to acquire file lock with timeout
acquire_lock() {
    exec 200>"/root/Desktop/extraction-automation-main/reports_queue/queue.lock"
    local start_time=$(date +%s)
    while ! flock -n 200; do
        local current_time=$(date +%s)
        local elapsed_time=$((current_time - start_time))
        if [[ $elapsed_time -ge 300 ]]; then
            echo "Timeout reached while waiting for lock."
            exit 1
        fi
        sleep 1
    done
}

# Function to release file lock
release_lock() {
    flock -u 200
    rm -f "/root/Desktop/extraction-automation-main/reports_queue/queue.lock"
}

# Acquire lock before modifying the queue
acquire_lock

# Process the schedule to find jobs for the current day
QUEUE_FILE="../reports_queue/reports_queue.json"
if [[ ! -f "$QUEUE_FILE" ]]; then
    echo "[]" > "$QUEUE_FILE"
fi

jobs_to_add=()
existing_ids=$(jq -r '.[].id' "$QUEUE_FILE")

while IFS= read -r line; do
    job_date=$(echo "$line" | jq -r '.date')
    if [[ "$job_date" == "$current_date" ]]; then
        while IFS= read -r subjob; do
            id=$(echo "$subjob" | jq -r '.id')
            if ! echo "$existing_ids" | grep -q "$id"; then
                report=$(echo "$subjob" | jq -r '.report')
                extraction_month=$(echo "$subjob" | jq -r '.extraction_month // empty')
                job_time=$(echo "$subjob" | jq -r '.hour')
                entry="{\"id\": \"$id\", \"report_name\": \"$report\", \"status\": \"PENDING\", \"retry_count\": 0"
                if [[ -n "$extraction_month" ]]; then
                    entry+=", \"extraction_month\": \"$extraction_month\""
                fi
                entry+="}"
                jobs_to_add+=("$entry")
                echo "Adding job: id=$id, report_name=$report, extraction_month=$extraction_month, hour=$job_time"
            else
                echo "Job with ID $id already exists, skipping."
            fi
        done < <(echo "$line" | jq -c '.jobs[]')
    fi
done < <(jq -c '.[]' "$LOCAL_FILE")

# Sort the jobs by hour in ascending order
sorted_jobs=($(for job in "${jobs_to_add[@]}"; do echo "$job"; done | jq -c -s 'sort_by(.hour) | .[]'))

# Add the jobs to the queue
if [ ${#sorted_jobs[@]} -gt 0 ]; then
    for job in "${sorted_jobs[@]}"; do
        jq ". |= [$job] + ." "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" && mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"
    done
    echo "Added ${#sorted_jobs[@]} jobs to the queue."
else
    echo "No new jobs to add to the queue for today."
fi

# Release lock after modifying the queue
release_lock

# Optional: Unset environment variables for security
unset FTP_SERVER FTP_PORT FTP_USER FTP_PASS SCHEDULE_PATH
