import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .models import Document


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

    doc.status = Document.Status.PROCESSING
    doc.save()

    try:
        text_parts = []
        pdf_path = doc.file.path
        doc_folder = os.path.splitext(pdf_path)[0]
        os.makedirs(doc_folder, exist_ok=True)

        with fitz.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf, start=1):
                # Render page to image
                mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
                pix = page.get_pixmap(matrix=mat)
                img_path = os.path.join(doc_folder, f"page_{page_num}.png")
                pix.save(img_path)

                # OCR
                img = Image.open(img_path)
                page_text = pytesseract.image_to_string(img, lang="rus+eng")
                if page_text.strip():
                    text_parts.append(f"--- Страница {page_num} ---\n{page_text}")

                # Cleanup image
                os.remove(img_path)

        # Cleanup folder if empty
        if not os.listdir(doc_folder):
            os.rmdir(doc_folder)

        full_text = "\n\n".join(text_parts)
        doc.extracted_text = full_text
        doc.status = Document.Status.DONE
        doc.save()

        return JsonResponse({
            "id": doc.id,
            "status": doc.status,
            "text_preview": full_text[:500] + "..." if len(full_text) > 500 else full_text,
        })

    except Exception as e:
        doc.status = Document.Status.ERROR
        doc.error_message = str(e)
        doc.save()
        return JsonResponse({"error": str(e)}, status=500)


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
