import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_ocr_project.settings")

app = Celery("pdf_ocr_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
