# PDF OCR

Django веб-приложение для извлечения текста из PDF-файлов с помощью OCR (PyMuPDF + Tesseract).

## Функции

- Загрузка PDF-файлов через веб-интерфейс
- Автоматическое извлечение текста с помощью OCR
- Просмотр результатов и скачивание извлечённого текста
- История обработанных документов

## Технологии

- **Django** — веб-фреймворк
- **PyMuPDF (fitz)** — работа с PDF
- **Tesseract OCR** + **Pillow** — распознавание текста
- **SQLite** — база данных (для разработки)

## Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/RayRaf/pdf-ocr.git
cd pdf-ocr

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Установить системные зависимости (Tesseract)
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr poppler-utils

# macOS:
brew install tesseract

# 4. Настроить переменные окружения
cp .env.example .env
# Отредактируй .env — укажи свой SECRET_KEY

# 5. Применить миграции и запустить
python manage.py migrate
python manage.py runserver
```

## Настройка

Создай файл `.env` рядом с `.env.example`:

```
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Использование

1. Открой `http://127.0.0.1:8000/`
2. Загрузи PDF через форму
3. Дождись обработки
4. Просматривай и скачивай результат

## Структура проекта

- `pdf_ocr_project/` — настройки Django
- `ocr/` — приложение: модели,视图, обработка PDF
- `templates/` — HTML-шаблоны
- `media/` — загруженные файлы

## Автор

[RayRaf](https://github.com/RayRaf)
