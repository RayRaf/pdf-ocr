# PDF OCR

Django приложение для извлечения текста из PDF с помощью OCR (PyMuPDF + Tesseract).
Теперь с **фоновой асинхронной обработкой** через Celery + Redis.

## Stack

- **Django 5.2** + Gunicorn (production)
- **Celery** — фоновая обработка OCR
- **Redis** — брокер Celery
- **Tesseract OCR** + Pillow — распознавание текста
- **Traefik** — реверс-прокси в production (автообнаружение через labels)
- **Docker Compose** — оркестрация

## Структура docker-compose

| файл | назначение |
|------|-----------|
| `docker-compose.yml` | Production конфиг: без exposed портов, Traefik labels, env vars |
| `docker-compose.override.yml` | Local dev: порты `8000`, volume `.`, `.env` напрямую |
| `Dockerfile` | Multi-ready образ с `entrypoint.sh` (миграции + static) |

## Запуск локально

```bash
cp .env.example .env
# отредактируй .env — укажи SECRET_KEY и т.д.

docker compose up --build
```

- Web: http://localhost:8000
- Celery worker: `docker compose logs -f worker`

## Запуск в production (Dokploy)

1. В настройках Dokploy задай Environment Variables:
   ```
   SECRET_KEY=your-secret-here
   ALLOWED_HOSTS=your-domain.com
   CSRF_TRUSTED_ORIGINS=https://your-domain.com
   PDF_OCR_HOST=your-domain.com
   ```
2. Загрузи `docker-compose.yml` (без `.override`)
3. Dokploy сам поднимет Traefik и проксит трафик через `traefik.enable=true`

## Endpoints

| URL | Метод | Описание |
|-----|-------|----------|
| `/` | GET | Главная — список документов |
| `/upload/` | POST | Загрузка PDF |
| `/process/<id>/` | POST | Запуск OCR (async → Celery) |
| `/status/<id>/` | GET | Проверка статуса обработки |
| `/detail/<id>/` | GET | Просмотр распознанного текста |
| `/delete/<id>/` | POST | Удаление документа + файла |

## Environment Variables

```
DEBUG=False
SECRET_KEY=change-me
ALLOWED_HOSTS=your-domain.com,localhost
CSRF_TRUSTED_ORIGINS=https://your-domain.com
USE_X_FORWARDED_HOST=True
REDIS_URL=redis://redis:6379/0
PDF_OCR_HOST=your-domain.com
```

## Примечания

- Для деплоя через **Dokploy** убедись, что `.env` не попадает в git
- Traefik подхватывает сервис по `traefik.http.routers...` labels
- Внутри Docker веб-сервер смотрит на порт `8000` (`expose: ["8000"]`), порт наружу не выставлен в production

---

Автор: [RayRaf](https://github.com/RayRaf)
