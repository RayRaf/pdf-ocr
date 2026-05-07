import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from celery import shared_task
from django.conf import settings

from ocr.models import Document


@shared_task(bind=True, max_retries=2)
def process_document(self, document_id: int):
    """
    Celery задача для OCR обработки PDF.
    """
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return {"error": f"Document {document_id} not found"}

    # Статус уже PROCESSING благодаря view — просто работаем
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

        return {
            "id": doc.id,
            "status": doc.status,
            "text_preview": full_text[:500] + "..." if len(full_text) > 500 else full_text,
        }

    except Exception as e:
        doc.status = Document.Status.ERROR
        doc.error_message = str(e)
        doc.save()
        # Можно retry, но OCR ошибки обычно не лечатся ретраем
        return {"error": str(e)}
