#!/bin/bash

# Navigate to the directory where the .env file is located
cd /root/Desktop/extraction-automation-main/

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

read_env_var_pass() {
  var_name="$1"
  if grep -Eq "^$var_name=" .env; then
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

# Validate and handle missing environment variables
if [[ -z "$FTP_SERVER" || -z "$FTP_PORT" || -z "$FTP_USER" || -z "$FTP_PASS" ]]; then
  echo "Error: Missing environment variables. Please configure FTP credentials and server details in .env file."
  exit 1
fi

# Navigate to the heartbeat directory
cd heartbeat

# Local temporary file
heartbeat_file="heartbeat_discoverer.json"
REMOTE_DIR="ftp://$FTP_SERVER:$FTP_PORT/00_notifications/"

# Create the heartbeat_discoverer JSON file
timestamp=$(TZ="Europe/Paris" date +"%Y-%m-%dT%H:%M:%S%z")
status="OK"

echo "$timestamp"

cat <<EOF > "$heartbeat_file"
{
    "timestamp": "$timestamp",
    "status": "$status"
}
EOF

# Check if the heartbeat_discoverer file was created
if [ ! -f "$heartbeat_file" ]; then
  echo "Error: Failed to create the heartbeat_discoverer JSON file"
  exit 1
fi

echo "$REMOTE_DIR$heartbeat_file"

# Upload the heartbeat_discoverer file
curl -T "$heartbeat_file" --ftp-method nocwd --ftp-pasv --ftp-ssl -u $FTP_USER:$FTP_PASS -Q "TYPE I" "$REMOTE_DIR$heartbeat_file"

# Check if the upload was successful
if [ $? -ne 0 ]; then
  echo "Error: Failed to upload $REMOTE_DIR$heartbeat_file"
else
  echo "Successfully uploaded $REMOTE_DIR$heartbeat_file"
fi

# Optional: Unset environment variables for security
unset FTP_SERVER FTP_PORT FTP_USER FTP_PASS
