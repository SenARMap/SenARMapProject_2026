#!/bin/sh
set -e

mkdir -p /project/programs/html/navi/script/

CONFIG_FILE="/project/programs/html/navi/script/config.js"

# ファイルが既に存在する場合はスキップする
if [ ! -f "$CONFIG_FILE" ]; then
    echo "const CONFIG = {" > "$CONFIG_FILE"
    echo "  GOOGLE_MAPS_API_KEY: \"${GOOGLE_MAPS_API_KEY}\"" >> "$CONFIG_FILE"
    echo "};" >> "$CONFIG_FILE"
    echo "[nginx] config.js generated."
else
    echo "[nginx] config.js already exists. Skipping generation."
fi

exec nginx -g "daemon off;"