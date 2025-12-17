#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <report_name> <execution_time> <status>"
  exit 1
fi

REPORT_NAME="$1"
EXECUTION_TIME="$2"
STATUS="$3"
STAT_FILE="./stats/report_stats.txt"

# Check if the stat file exists, if not, create it
if [ ! -f "$STAT_FILE" ]; then
  touch "$STAT_FILE"
fi

# Get the current date and time
CURRENT_DATETIME=$(date '+%Y-%m-%d %H:%M:%S')

# Append the current date and time, report name, execution time, status, and retry count to the stat file
echo "$CURRENT_DATETIME,$REPORT_NAME,$EXECUTION_TIME,$STATUS" >> "$STAT_FILE"

echo "Execution time for report '$REPORT_NAME' recorded as $EXECUTION_TIME seconds with status '$STATUS' and retry count $RETRY_COUNT."
