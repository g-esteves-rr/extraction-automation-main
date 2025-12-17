#!/bin/bash

# Define the paths to the queue JSON file and the log file
QUEUE_FILE="/root/Desktop/extraction-automation-main/reports_queue/reports_queue.json"
LOG_FILE="/root/Desktop/extraction-automation-main/reports_queue/cleanup.log"
LOCK_FILE="/root/Desktop/extraction-automation-main/reports_queue/queue.lock"
LOCK_TIMEOUT=300  # Timeout in seconds (5 minutes)

# Function to acquire file lock with timeout
acquire_lock() {
    exec 200>"$LOCK_FILE"
    local start_time=$(date +%s)
    while ! flock -n 200; do
        local current_time=$(date +%s)
        local elapsed_time=$((current_time - start_time))
        if [[ $elapsed_time -ge $LOCK_TIMEOUT ]]; then
            echo "Timeout reached while waiting for lock."
            exit 1
        fi
        sleep 1
    done
}

# Function to release file lock
release_lock() {
    flock -u 200
    rm -f "$LOCK_FILE"
}

# Function to log the removal of reports
log_removal() {
    local report_id="$1"
    local report_name="$2"
    local status="$3"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$timestamp - Removed report with ID $report_id, Name $report_name, Status $status"
    echo "$timestamp - Removed report with ID $report_id, Name $report_name, Status $status" >> "$LOG_FILE"
}

# Acquire lock before modifying the queue
acquire_lock

# Filter out reports with status "SUCCESS" or "FAILED" and log their removal
jq -c '.[] | select(.status == "SUCCESS" or .status == "FAILED")' "$QUEUE_FILE" | while read -r report; do
    report_id=$(echo "$report" | jq -r '.id')
    report_name=$(echo "$report" | jq -r '.report_name')
    status=$(echo "$report" | jq -r '.status')
    log_removal "$report_id" "$report_name" "$status"
done

# Clean up the queue file by removing reports with status "SUCCESS" or "FAILED"
jq 'map(select(.status != "SUCCESS" and .status != "FAILED"))' "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" && mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"

echo "Cleaned up the queue. Removed reports with status 'SUCCESS' or 'FAILED'."

# Release lock after modifying the queue
release_lock
