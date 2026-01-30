#!/bin/bash

# Define the path to the reports queue JSON file
QUEUE_FILE="/root/Desktop/extraction-automation-main/reports_queue/reports_queue.json"
ARCHIVE_SCRIPT="/root/Desktop/extraction-automation-main/screenshots/archive_screenshots.sh"
NOTIFICATION_SCRIPT="/root/Desktop/extraction-automation-main/notifications/notify.sh"

# Define the log file
log_file="/root/Desktop/extraction-automation-main/reports_queue/process_log.log"

# Log function to write to file and console
log_message() {
    echo "$(date +'%Y-%m-%d %H:%M:%S') - $1" | tee -a "$log_file"
}

# Update report status
update_status() {
    local id="$1"
    local new_status="$2"
    log_message "Updating status of report ID $id to $new_status"
    jq "(map(if .id == \"$id\" then .status = \"$new_status\" else . end))" "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" && mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"
}

# Increment retry count
increment_retry_count() {
    local id="$1"
    log_message "Incrementing retry count for report ID $id"
    jq "(map(if .id == \"$id\" then .retry_count += 1 else . end))" "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" && mv "${QUEUE_FILE}.tmp" "$QUEUE_FILE"
}

# Error handling function
handle_error() {
    local id="$1"
    log_message "An error occurred. Setting status to FAIL for report with ID $id."
    update_status "$id" "FAIL"
    # Call archive_screenshots.sh with the report name
    archive_screenshots "$report_name"
}

# Archive and clean up screenshots
archive_screenshots() {
    local report_name="$1"
    log_message "Archiving and cleaning up screenshots for report: $report_name"
    if [[ -f "$ARCHIVE_SCRIPT" ]]; then
        bash "$ARCHIVE_SCRIPT" "$report_name"
        if [[ $? -eq 0 ]]; then
            log_message "Screenshots for report $report_name archived successfully."
        else
            log_message "Error while archiving screenshots for report $report_name."
        fi
    else
        log_message "Archive script not found at $ARCHIVE_SCRIPT"
    fi
}

# Process the queue
process_queue() {
    while true; do
        local entry=$(jq -c '.[] | select(.status == "PENDING" or .status == "FAIL" or .status == "RUNNING")' "$QUEUE_FILE" | head -n 1)

        if [[ -z "$entry" ]]; then
            log_message "Queue is empty. Exiting."
            break
        fi

        local id=$(echo "$entry" | jq -r '.id')
        local report_name=$(echo "$entry" | jq -r '.report_name')
        local status=$(echo "$entry" | jq -r '.status')
        local retry_count=$(echo "$entry" | jq -r '.retry_count')
        local extraction_month=$(echo "$entry" | jq -r '.extraction_month // empty')

        log_message "Processing report $report_name with ID $id, status $status, retry count $retry_count."

        # Notify only if it's the first time (PENDING)
        if [[ "$status" == "PENDING" ]]; then
            log_message "Sending START notification for report $report_name"
            #"$NOTIFICATION_SCRIPT" "$report_name" "START"
        fi
        
        # If retry count exceeded, send FAIL notification
        if [[ $retry_count -gt 10 ]]; then
            log_message "Retry count for report $report_name with ID $id exceeded 10. Marking as FAILED."
            "$NOTIFICATION_SCRIPT" "$report_name" "FAIL" "Retry limit reached after $retry_count attempts."
            update_status "$id" "FAILED"
            archive_screenshots "$report_name"
            continue
        fi

        # Update status to RUNNING
        update_status "$id" "RUNNING"

        # Trap any errors and call the handle_error function
        trap 'handle_error $id' ERR

        # Run the report extraction
        if [[ -n "$extraction_month" ]]; then
            log_message "Running extraction for report $report_name with extraction month $extraction_month."
            /root/Desktop/extraction-automation-main/trigger_report_extraction.sh "$report_name" "$extraction_month"
        else
            log_message "Running extraction for report $report_name without extraction month."
            /root/Desktop/extraction-automation-main/trigger_report_extraction.sh "$report_name"
        fi

        # Check the exit status of the report extraction
        if [[ $? -eq 0 ]]; then
            log_message "Report $report_name with ID $id processed successfully."
            # Update status to SUCCESS
            update_status "$id" "SUCCESS"
            archive_screenshots "$report_name"
        else
            log_message "Report $report_name with ID $id failed to process."
            # Increment retry count and update status to FAIL
            increment_retry_count "$id"
            update_status "$id" "FAIL"
            log_message "Retry count incremented for report $report_name. Will retry after 60 seconds."
            sleep 60  # Wait for 1 minute before retrying
            archive_screenshots "$report_name"
        fi

        # Remove the error trap
        trap - ERR
    done
}

# Main script logic
if [[ $# -ge 1 ]]; then
    report_name="$1"
    extraction_month="$2"
    log_message "Starting queue processing for report $report_name."
    process_queue
else
    log_message "Starting queue processing for all pending reports."
    process_queue
fi
