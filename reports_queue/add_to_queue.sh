#!/bin/bash

# Define the path to the reports queue JSON file
QUEUE_FILE="/root/Desktop/extraction-automation-main/reports_queue/reports_queue.json"
LOCK_FILE="/root/Desktop/extraction-automation-main/reports_queue/queue.lock"
LOCK_TIMEOUT=300  # Timeout in seconds (5 minutes)

# Generate a unique ID based on date, time, report name, and optional extraction month
generate_id() {
    local date=$(date +%Y%m%d)
    local time=$(date +%H%M%S)
    local report_name="$1"
    local extraction_month="$2"
    if [[ -n "$extraction_month" ]]; then
        # Remove dashes from the extraction month
        extraction_month=${extraction_month//-/}
        echo "${date}_${time}_${report_name}_${extraction_month}"
    else
        echo "${date}_${time}_${report_name}"
    fi
}

# Acquire file lock with timeout
acquire_lock() {
    exec 200>"$LOCK_FILE"
    local start_time=$(date +%s)
    while ! flock -n 200; do
        local current_time=$(date +%s)
        local elapsed_time=$((current_time - start_time))
        if [[ $elapsed_time -ge $LOCK_TIMEOUT ]]; then
            echo "Timeout reached while waiting for lock on $LOCK_FILE."
            exit 1
        fi
        echo "Waiting for lock on $LOCK_FILE..."
        sleep 1
    done
}

# Release file lock
release_lock() {
    flock -u 200
    rm -f "$LOCK_FILE"
}

# Add a report to the queue
add_to_queue() {
    local report_name="$1"
    local extraction_month="$2"
    local id=$(generate_id "$report_name" "$extraction_month")

    if [[ ! -f "$QUEUE_FILE" ]]; then
        echo "[]" > "$QUEUE_FILE"
    fi

    acquire_lock

    # Check if the ID already exists
    local existing_entry=$(jq ".[] | select(.id == \"$id\")" "$QUEUE_FILE")

    if [[ -n "$existing_entry" ]]; then
        # Update the state to PENDING
        jq "map(if .id == \"$id\" then .status = \"PENDING\" else . end)" "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" && mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"
        echo "Updated existing report $report_name with ID $id to PENDING."
    else
        # Add new entry
        local entry="{\"id\": \"$id\", \"report_name\": \"$report_name\", \"status\": \"PENDING\", \"retry_count\": 0"
        if [[ -n "$extraction_month" ]]; then
            entry+=", \"extraction_month\": \"$extraction_month\""
        fi
        entry+="}"

        jq ". |= [$entry] + ." "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" && mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"
        echo "Added new report $report_name to queue with ID $id."
    fi

    release_lock
}

# Main script logic
if [[ $# -ge 1 ]]; then
    report_name="$1"
    extraction_month="$2"
    add_to_queue "$report_name" "$extraction_month"
else
    echo "Usage: $0 <report_name> [extraction_month]"
    exit 1
fi
