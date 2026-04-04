#!/bin/bash

# --- Configuration ---
ENV_FILE=".env.production"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# --- Read .env variables ---
if [ ! -f "$ENV_FILE" ]; then
    echo "[$(date)] ERROR: $ENV_FILE not found!" >&2
    exit 1
fi

IG_ACCESS_TOKEN=$(grep "^IG_ACCESS_TOKEN=" "$ENV_FILE" | cut -d "=" -f2)
IG_APP_ID=$(grep "^IG_APP_ID=" "$ENV_FILE" | cut -d "=" -f2)
IG_APP_SECRET=$(grep "^IG_APP_SECRET=" "$ENV_FILE" | cut -d "=" -f2)

if [ -z "$IG_ACCESS_TOKEN" ] || [ -z "$IG_APP_ID" ] || [ -z "$IG_APP_SECRET" ]; then
    echo "[$(date)] ERROR: Missing required variables in $ENV_FILE" >&2
    exit 1
fi

# --- Refresh Token ---
echo "[$(date)] Refreshing Instagram token..."
RESPONSE=$(curl -s "https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id=${IG_APP_ID}&client_secret=${IG_APP_SECRET}&fb_exchange_token=${IG_ACCESS_TOKEN}")

if [[ "$RESPONSE" == *"error"* ]]; then
    echo "[$(date)] API ERROR: $RESPONSE" >&2
    exit 1
fi

NEW_TOKEN=$(echo "$RESPONSE" | jq -r ".access_token")
EXPIRES_IN=$(echo "$RESPONSE" | jq -r ".expires_in")

if [ -z "$NEW_TOKEN" ] || [ "$NEW_TOKEN" == "null" ]; then
    echo "[$(date)] ERROR: Failed to extract new token" >&2
    echo "[$(date)] API Response: $RESPONSE" >&2
    exit 1
fi

# --- Update .env File ---
cp "$ENV_FILE" "${ENV_FILE}.bak"
ESCAPED_TOKEN=$(printf "%s\n" "$NEW_TOKEN" | sed "s:[\/&]:\\\\&:g")
sed -i "s/^IG_ACCESS_TOKEN=.*/IG_ACCESS_TOKEN=${ESCAPED_TOKEN}/" "$ENV_FILE"

# Calculate expiry date
EXPIRES_DAYS=$((EXPIRES_IN / 86400))
if [[ "$OSTYPE" == "darwin"* ]]; then
    EXPIRY_DATE=$(date -v +${EXPIRES_DAYS}d "+%Y-%m-%d")
else
    EXPIRY_DATE=$(date -d "+${EXPIRES_DAYS} days" "+%Y-%m-%d")
fi

echo "[$(date)] Token refreshed successfully. Expires in ${EXPIRES_DAYS} days (${EXPIRY_DATE})"
