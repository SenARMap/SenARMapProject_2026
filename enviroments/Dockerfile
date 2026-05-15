FROM python:3.13-slim-trixie

WORKDIR /project/enviroments

ENV TERM=xterm-256color

RUN echo "alias ls='ls --color=auto'" >> /root/.bashrc && \
    echo "alias grep='grep --color=auto'" >> /root/.bashrc && \
    echo "export PS1='\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '" >> /root/.bashrc

RUN apt-get update && apt-get install -y --no-install-recommends \
    vim nodejs npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g typescript

COPY requirements.txt .
    
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install -r requirements.txt

WORKDIR /project/programs