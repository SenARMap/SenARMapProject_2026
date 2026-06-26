FROM nginx:stable-alpine

WORKDIR /app

COPY . /project/

RUN find /project -type d -exec chmod 755 {} \; && \
    find /project -type f -exec chmod 644 {} \;

COPY deploy_env/nginx/errors/ /etc/nginx/errors/

COPY deploy_env/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deploy_env/nginx/docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]