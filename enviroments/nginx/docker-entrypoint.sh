#!/bin/sh
set -e

CERT=/etc/nginx/certs/server.crt
KEY=/etc/nginx/certs/server.key

if [ -f "$CERT" ] && [ -f "$KEY" ]; then
    echo "[nginx] SSL証明書を検出 → HTTPSモード (port 80 → 443)"
    cp /etc/nginx/templates/nginx-flask.conf /etc/nginx/nginx.conf
else
    echo "[nginx] SSL証明書なし → HTTPのみ (port 80)"
    cat > /etc/nginx/nginx.conf << 'NGINXCONF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;

    server {
        listen 80;
        server_name _;

        error_page 400 /errors/400.html;
        error_page 401 /errors/401.html;
        error_page 403 /errors/403.html;
        error_page 404 /errors/404.html;
        error_page 500 /errors/500.html;
        error_page 502 /errors/502.html;
        error_page 503 /errors/503.html;
        error_page 504 /errors/504.html;

        location ^~ /errors/ {
            root /etc/nginx;
            internal;
        }

        location /3d/ {
            proxy_pass         http://python:5001/3d/;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
        }
        location /api/ {
            proxy_pass         http://python:5001/api/;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
        }

        location / {
            root      /project/programs/html;
            try_files $uri $uri/ =404;
        }
    }
}
NGINXCONF
fi

exec nginx -g "daemon off;"
