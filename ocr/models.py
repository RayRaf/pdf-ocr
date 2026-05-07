import os
import uuid
import json
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
    avg_confidence = models.FloatField(null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Document {self.id}"

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""


class DocumentPage(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="pages"
    )
    page_number = models.PositiveIntegerField()
    width = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    dpi = models.FloatField(null=True, blank=True)
    rotation = models.FloatField(null=True, blank=True)
    structured_data = models.JSONField(default=dict, blank=True)
    native_text = models.TextField(blank=True)
    ocr_text = models.TextField(blank=True)
    avg_confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["page_number"]
        unique_together = ["document", "page_number"]

    def __str__(self):
        return f"Page {self.page_number} of {self.document}"
