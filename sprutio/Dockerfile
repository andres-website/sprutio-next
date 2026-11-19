# Базовый образ sprutio (форк): Python 3.12 + s6-overlay v3.
# Заменяет beget/sprutio-python (python:3.4 + s6-overlay 1.11).
FROM python:3.12-slim-bookworm

ARG S6_OVERLAY_VERSION=3.2.0.2
ARG TARGETARCH=amd64

RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends xz-utils ca-certificates curl openssl \
        libarchive13 libpam0g libpam-modules libcurl4 zip unzip \
 && S6ARCH=$( [ "$TARGETARCH" = "arm64" ] && echo aarch64 || echo x86_64 ) \
 && for t in noarch $S6ARCH symlinks-noarch; do \
      curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${t}.tar.xz" \
        | tar -C / -Jxp; \
    done \
 && rm -rf /var/lib/apt/lists/*

# Совместимость со скриптами оригинала: падение cont-init останавливает контейнер,
# переменные окружения доступны через with-contenv.
ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2 \
    S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY vendor/ /opt/sprutio-vendor/
ENV PYTHONPATH=/opt/sprutio-vendor

ENTRYPOINT ["/init"]
