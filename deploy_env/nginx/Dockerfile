FROM nginx:stable-alpine

WORKDIR /app

# SSL証明書マウント先ディレクトリ
RUN mkdir -p /etc/nginx/certs

# confテンプレート (entrypointがSSL有効時にnginx.confとして使用)
COPY ./nginx-flask.conf /etc/nginx/templates/nginx-flask.conf

# エラーページ
COPY ./errors/ /etc/nginx/errors/

# 起動スクリプト (SSL証明書の有無でHTTP/HTTPSを切り替え)
COPY ./docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
