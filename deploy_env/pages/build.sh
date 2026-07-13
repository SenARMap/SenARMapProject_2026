#!/bin/sh
# Cloudflare Pages のビルドコマンドとして実行するスクリプト。
#   Build command:          sh deploy_env/pages/build.sh
#   Build output directory: programs/html
#   環境変数:               GOOGLE_MAPS_API_KEY（Production / Preview 両方に設定）
#
# 旧 deploy_env/nginx/docker-entrypoint.sh が行っていた config.js 生成の移植。
set -e

if [ -z "$GOOGLE_MAPS_API_KEY" ]; then
    echo "ERROR: GOOGLE_MAPS_API_KEY is not set." >&2
    exit 1
fi

CONFIG_FILE="programs/html/navi/script/config.js"

mkdir -p "$(dirname "$CONFIG_FILE")"
cat > "$CONFIG_FILE" <<EOF
const CONFIG = {
  GOOGLE_MAPS_API_KEY: "${GOOGLE_MAPS_API_KEY}"
};
EOF

echo "[pages] config.js generated."
