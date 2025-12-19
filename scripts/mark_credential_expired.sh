#!/usr/bin/env bash
# Mark a credential as expired (set state = "expired") in config/credentials.json
set -euo pipefail

CREDS_FILE="${1:-config/credentials.json}"
TARGET="${2:-}"

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 <credentials_file> <account_name_or_username>" >&2
  echo "Or: $0 <account_name_or_username>" >&2
  exit 2
fi

if [[ ! -f "$CREDS_FILE" ]]; then
  echo "Credentials file not found: $CREDS_FILE" >&2
  exit 3
fi

# Try to match by name first, then username
tmpfile="${CREDS_FILE}.tmp"

jq --arg tgt "$TARGET" '
  .accounts |= map(
    if (.name == $tgt) or (.username == $tgt) then
      .state = "expired"
    else
      .
    end
  )
' "$CREDS_FILE" > "$tmpfile" && mv "$tmpfile" "$CREDS_FILE"

echo "Marked credential '$TARGET' as expired in $CREDS_FILE"
exit 0
