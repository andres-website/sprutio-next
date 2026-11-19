# Тестовый FTP-сервер для стенда (pyftpdlib): пользователь из FTP_USER/FTP_PASS, корень /data.
FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir pyftpdlib==2.*
COPY ftpd.py /ftpd.py
RUN mkdir -p /data
CMD ["python", "/ftpd.py"]
