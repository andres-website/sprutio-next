# Контекст сборки — корень репозитория sprutio/ (см. stand/compose.next.yml)
ARG BASE=sprutio-next/python
FROM ${BASE}

COPY app/requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

COPY app/init-ssl.sh /etc/cont-init.d/10-init-ssl.sh
COPY app/run-app.sh /etc/services.d/app/run
RUN chmod +x /etc/cont-init.d/* /etc/services.d/*/run

COPY app/ /app/
WORKDIR /app/
