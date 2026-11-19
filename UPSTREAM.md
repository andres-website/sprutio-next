# Upstream

Код sprutio лежит в `sprutio/` как обычные файлы (без вложенных .git), чтобы весь форк жил в одном репозитории.

| Компонент | Репозиторий | Базовый коммит |
|---|---|---|
| sprutio (app, nginx, compose) | https://github.com/LTD-Beget/sprutio | 35773f0 (2017-10-17) |
| sprutio-rpc → `sprutio/rpc` | https://github.com/LTD-Beget/sprutio-rpc | 6ab5d14 (2017-01-20) |
| sprutio-frontend → `sprutio/app/public/fm` | https://github.com/LTD-Beget/sprutio-frontend | 24c137d (2017-01-20) |

Образы, с которыми снят эталон тестов: beget/sprutio-{app,rpc,nginx,frontend,cron}:latest (Docker Hub, 2017-10-17) + redis:3.0.
