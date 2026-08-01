FROM python:3.13-slim-trixie

ENV TERM=xterm-256color

RUN echo "alias ls='ls --color=auto'" >> /root/.bashrc && \
    echo "alias grep='grep --color=auto'" >> /root/.bashrc && \
    echo "export PS1='\[\e[1;32m\][PRODUCTION] \u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '" >> /root/.bashrc

RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /project/enviroments

COPY deploy_env/python/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . /project/

RUN find /project -type d -exec chmod 755 {} \; && \
    find /project -type f -exec chmod 644 {} \;

WORKDIR /project/programs/3D_Graph