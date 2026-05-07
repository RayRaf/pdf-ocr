import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .models import Document
from .tasks import process_document


def index(request):
    documents = Document.objects.order_by("-created_at")
    return render(request, "ocr/index.html", {"documents": documents})


@require_http_methods(["POST"])
def upload(request):
    file = request.FILES.get("pdf_file")
    if not file:
        return JsonResponse({"error": "Файл не выбран"}, status=400)

    if not file.name.lower().endswith(".pdf"):
        return JsonResponse({"error": "Только PDF файлы"}, status=400)

    doc = Document.objects.create(
        title=file.name,
        file=file,
        status=Document.Status.PENDING,
    )
    return JsonResponse({
        "id": doc.id,
        "title": doc.title,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
    })


@require_http_methods(["POST"])
def process(request, pk):
    doc = get_object_or_404(Document, pk=pk)

    if doc.status == Document.Status.PROCESSING:
        return JsonResponse({"error": "Уже обрабатывается"}, status=409)

    # Отправляем в Celery worker вместо синхронной обработки
    process_document.delay(doc.id)

    return JsonResponse({
        "id": doc.id,
        "status": "processing",
        "message": "Обработка запущена в фоновом режиме",
    })


def status(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    return JsonResponse({
        "id": doc.id,
        "status": doc.status,
        "status_display": doc.get_status_display(),
        "extracted_text_preview": doc.extracted_text[:300] if doc.extracted_text else "",
        "error_message": doc.error_message,
    })


@require_http_methods(["POST"])
def delete(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    try:
        # Delete file from disk
        if doc.file and os.path.exists(doc.file.path):
            os.remove(doc.file.path)
            # Remove parent folder if empty
            folder = os.path.dirname(doc.file.path)
            if os.path.isdir(folder) and not os.listdir(folder):
                os.rmdir(folder)
        doc.delete()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def detail(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    return render(request, "ocr/detail.html", {"doc": doc})
