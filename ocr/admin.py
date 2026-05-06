from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "status", "created_at", "updated_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "extracted_text"]
    readonly_fields = ["created_at", "updated_at", "filename"]
