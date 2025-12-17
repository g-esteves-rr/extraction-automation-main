#!/bin/bash

# === Load .env Variables ===
read_env_var() {
  var_name="$1"
  if grep -Eq "^$var_name=" .env; then
    var_value=$(grep -E "^$var_name=" .env | cut -d '=' -f2- | tr -d '"')
    export "$var_name"="$var_value"
  else
    echo "Warning: Variable '$var_name' not found in .env"
  fi
}

read_env_var_pass() {
  var_name="$1"
  if grep -Eq "^$var_name=" .env; then
    var_value=$(grep -E "^$var_name=" .env | cut -d '=' -f2-)
    export "$var_name"="$var_value"
  else
    echo "Warning: Variable '$var_name' not found in .env"
  fi
}

# === Load Required Environment Variables ===
read_env_var "FTP_USER"
read_env_var_pass "FTP_PASS"
read_env_var "LOCAL_DESTINATION_FOLDER_PATH"
read_env_var "VALID_REPORTS"

# === Validate Required Environment Variables ===
if [[ -z "$FTP_USER" || -z "$FTP_PASS" || -z "$VALID_REPORTS" || -z "$LOCAL_DESTINATION_FOLDER_PATH" ]]; then
  echo "Error: Missing environment variables. Please check your .env file."
  echo "Required: FTP_USER, FTP_PASS, VALID_REPORTS, LOCAL_DESTINATION_FOLDER_PATH"
  exit 1
fi

# === Parse Input Report Name ===
report_name=$(tr '[:lower:]' '[:upper:]' <<< "$1")
if [[ -z "$report_name" ]]; then
  echo "Usage: $0 <REPORT_NAME>"
  exit 1
fi

IFS=',' read -r -a valid_reports <<< "$VALID_REPORTS"
if [[ ! " ${valid_reports[*]} " =~ " $report_name " ]]; then
  echo "Error: Invalid report name '$report_name'. Valid options: ${valid_reports[*]}"
  exit 1
fi

json_config_path="report_routing_config.json"

# === Validate Report Exists in JSON Config ===
if ! jq -e --arg report "$report_name" '.reports[] | select(.report_name == $report)' "$json_config_path" > /dev/null; then
  echo "Error: Report '$report_name' not found in routing config."
  exit 1
fi

# === Determine File Naming Format ===
read_env_var "FILE_NAME_${report_name}"
file_name_str=$(eval echo "\$FILE_NAME_${report_name}")
case "$report_name" in
  "DUK008"|"DUK008_XLS") DATE_FORMAT="%y-%m-%d" ;;
  "IC01"|"PROVISION"|"ACCRUALS") DATE_FORMAT="%Y-%m" ;;
  *) DATE_FORMAT="%Y%m%d" ;;
esac

current_date=$(date +"$DATE_FORMAT")
before_comma=${file_name_str%%,*}
after_comma=${file_name_str#*,}
constructed_file_name="$before_comma$current_date$after_comma"

# === Prepare Local Folders ===
lc_report_name="${report_name,,}"
LOCAL_DIR="${LOCAL_DESTINATION_FOLDER_PATH}${lc_report_name}/"
ARCHIVE_DIR="${LOCAL_DIR}archive/"
mkdir -p "$ARCHIVE_DIR"

# === Process Each File in Report Folder ===
for file in "$LOCAL_DIR"*; do
  [ -d "$file" ] && continue
  file_base=$(basename "$file")

  mapfile -t targets < <(jq -r --arg report "$report_name" \
    '.reports[] | select(.report_name == $report) | .servers_targets[] | "\(.server)|\(.port)|\(.destination_path)"' "$json_config_path")

  transfer_success=false

  for target in "${targets[@]}"; do
    IFS='|' read -r server port dest_path <<< "$target"
    dest_path=$(echo "$dest_path" | sed 's|\\|/|g')  # Normalize slashes

    url="ftp://$server:$port/$dest_path/$file_base"

    curl -T "$file" --ftp-method nocwd --ftp-pasv --ftp-ssl -u "$FTP_USER:$FTP_PASS" -Q "TYPE I" "$url" --silent --show-error --fail

    if [ $? -eq 0 ]; then
      echo "📤 Sending $report_name to $server: SUCCESS"
      transfer_success=true
    else
      echo "📤 Sending $report_name to $server: FAILED"
    fi
  done

  if $transfer_success; then
    mv "$file" "$ARCHIVE_DIR"
  else
    echo "All transfers failed for $file_base. File kept in $LOCAL_DIR for retry."
  fi
done

# === Clean Up ===
unset FTP_USER FTP_PASS VALID_REPORTS LOCAL_DESTINATION_FOLDER_PATH
