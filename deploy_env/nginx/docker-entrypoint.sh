#!/bin/sh
set -e

mkdir /project/programs/html/navi/script/

CONFIG_FILE="/project/programs/html/navi/script/config.js"

echo "const CONFIG = {" > "$CONFIG_FILE"
echo "  GOOGLE_MAPS_API_KEY: \"${GOOGLE_MAPS_API_KEY}\"" >> "$CONFIG_FILE"
echo "};" >> "$CONFIG_FILE"

echo "[nginx] config.js generated successfully with injected API key."

exec nginx -g "daemon off;"