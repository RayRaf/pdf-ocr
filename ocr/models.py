import os
import uuid
from django.db import models


def upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"documents/{uuid.uuid4()}{ext}"


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает обработки"
        PROCESSING = "processing", "Обрабатывается"
        DONE = "done", "Готово"
        ERROR = "error", "Ошибка"

    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to=upload_path)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    extracted_text = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Document {self.id}"

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""
