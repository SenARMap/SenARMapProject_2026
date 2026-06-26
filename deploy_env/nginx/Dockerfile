FROM nginx:stable-alpine

WORKDIR /app

COPY . /project/

RUN find /project -type d -exec chmod 755 {} \; && \
    find /project -type f -exec chmod 644 {} \;

COPY deploy_env/nginx/errors/ /etc/nginx/errors/

COPY deploy_env/nginx/nginx.conf /etc/nginx/conf.d/default.conf
