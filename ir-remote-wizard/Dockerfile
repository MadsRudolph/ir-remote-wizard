ARG BUILD_FROM=python:3.12-slim
FROM ${BUILD_FROM}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clone Flipper-IRDB at build time
RUN git clone --depth 1 https://github.com/Lucaslhm/Flipper-IRDB.git /data/Flipper-IRDB

COPY scripts/ /app/scripts/
COPY app/ /app/app/

COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
