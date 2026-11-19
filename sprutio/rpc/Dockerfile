# Контекст сборки — корень репозитория sprutio/ (см. stand/compose.next.yml)
ARG BASE=sprutio-next/python
FROM ${BASE}

COPY rpc/requirements.txt /requirements.txt
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends build-essential swig libarchive-dev libpam0g-dev \
        libcurl4-openssl-dev libssl-dev libxml2-dev libxslt1-dev \
 && pip install -r /requirements.txt \
 && apt-get purge -y -qq build-essential swig libarchive-dev libpam0g-dev libcurl4-openssl-dev libssl-dev \
        libxml2-dev libxslt1-dev \
 && apt-get autoremove -y -qq && apt-get install -y -qq --no-install-recommends libxml2 libxslt1.1 ripgrep findutils \
 && rm -rf /var/lib/apt/lists/*

COPY rpc/run-rpc.sh /etc/services.d/rpc/run
COPY rpc/run-sendfile.sh /etc/services.d/sendfile/run
COPY rpc/init-db.sh /etc/cont-init.d/10-init-db.sh
COPY rpc/init-tmp.sh /etc/cont-init.d/20-init-tmp.sh
COPY rpc/init-passwd.sh /etc/cont-init.d/30-init-passwd.sh
RUN chmod +x /etc/cont-init.d/* /etc/services.d/*/run

COPY rpc/ /rpc/
WORKDIR /rpc/
