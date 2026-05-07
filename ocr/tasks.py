import os
import json
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import cv2
import numpy as np
from celery import shared_task
from django.conf import settings

from ocr.models import Document, DocumentPage


def preprocess_image(img_path: str) -> str:
    """
    Deskew + adaptive threshold + save back.
    Returns path to preprocessed image.
    """
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return img_path

    # --- Deskew ---
    # Compute skew angle via Hough lines on inverted binary image
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    lines = cv2.HoughLinesP(binary, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)
    if lines is not None and len(lines) > 0:
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(angle) < 45:
                angles.append(angle)
        if angles:
            median_angle = np.median(angles)
            if abs(median_angle) > 0.5:
                h, w = img.shape
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # --- Binarization ---
    img = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )

    # Save to temp file
    pre_path = img_path.replace(".png", "_pre.png")
    cv2.imwrite(pre_path, img)
    return pre_path


def extract_native_text(page) -> dict:
    """
    Extract native text + bbox from PDF page using PyMuPDF.
    Returns dict with blocks/lines/words and text.
    """
    blocks = page.get_text("dict").get("blocks", [])
    words = []
    lines = []
    text_parts = []
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            line_text = " ".join(span["text"] for span in line["spans"])
            line_bbox = line["bbox"]
            lines.append({
                "text": line_text,
                "bbox": line_bbox,
            })
            text_parts.append(line_text)
            for span in line["spans"]:
                words.append({
                    "text": span["text"],
                    "bbox": span["bbox"],
                    "font": span.get("font", ""),
                    "size": span.get("size", 0),
                })
    return {
        "text": "\n".join(text_parts),
        "blocks": len(blocks),
        "lines": lines,
        "words": words,
    }


def run_ocr_with_boxes(img_path: str, lang: str = "rus+eng") -> dict:
    """
    Run Tesseract image_to_data and return structured dict with words/lines/blocks.
    """
    img = Image.open(img_path)
    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

    words = []
    lines_dict = {}
    blocks_dict = {}
    text_parts = []
    confidences = []

    n_boxes = len(data["text"])
    for i in range(n_boxes):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])
        if not text or conf < 0:
            continue
        word = {
            "text": text,
            "bbox": [
                data["left"][i],
                data["top"][i],
                data["left"][i] + data["width"][i],
                data["top"][i] + data["height"][i],
            ],
            "confidence": conf,
            "page_num": data["page_num"][i],
            "block_num": data["block_num"][i],
            "par_num": data["par_num"][i],
            "line_num": data["line_num"][i],
            "word_num": data["word_num"][i],
        }
        words.append(word)
        confidences.append(conf)
        text_parts.append(text)

        line_key = (data["page_num"][i], data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if line_key not in lines_dict:
            lines_dict[line_key] = {
                "text": text,
                "bbox": word["bbox"],
                "words": [word],
                "confidence": conf,
            }
        else:
            lines_dict[line_key]["text"] += " " + text
            lines_dict[line_key]["words"].append(word)
            lines_dict[line_key]["confidence"] = (
                lines_dict[line_key]["confidence"] * (len(lines_dict[line_key]["words"]) - 1) + conf
            ) / len(lines_dict[line_key]["words"])
            # Expand bbox
            l, t, r, b = lines_dict[line_key]["bbox"]
            wl, wt, wr, wb = word["bbox"]
            lines_dict[line_key]["bbox"] = [min(l, wl), min(t, wt), max(r, wr), max(b, wb)]

        block_key = (data["page_num"][i], data["block_num"][i])
        if block_key not in blocks_dict:
            blocks_dict[block_key] = {
                "lines": [lines_dict[line_key]],
                "bbox": lines_dict[line_key]["bbox"],
            }
        else:
            blocks_dict[block_key]["lines"].append(lines_dict[line_key])
            l, t, r, b = blocks_dict[block_key]["bbox"]
            wl, wt, wr, wb = lines_dict[line_key]["bbox"]
            blocks_dict[block_key]["bbox"] = [min(l, wl), min(t, wt), max(r, wr), max(b, wb)]

    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0

    return {
        "text": " ".join(text_parts),
        "words": words,
        "lines": list(lines_dict.values()),
        "blocks": [
            {
                "bbox": b["bbox"],
                "lines": b["lines"],
            }
            for b in blocks_dict.values()
        ],
        "avg_confidence": avg_conf,
        "word_count": len(words),
    }


@shared_task(bind=True, max_retries=2)
def process_document(self, document_id: int):
    """
    Celery задача для OCR обработки PDF.
    Гибридный подход: native text first, OCR fallback + structured output.
    """
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return {"error": f"Document {document_id} not found"}

    doc.status = Document.Status.PROCESSING
    doc.save()

    # Cleanup old pages if re-processing
    DocumentPage.objects.filter(document=doc).delete()

    try:
        text_parts = []
        page_structures = []
        all_confidences = []
        pdf_path = doc.file.path
        doc_folder = os.path.splitext(pdf_path)[0]
        os.makedirs(doc_folder, exist_ok=True)

        with fitz.open(pdf_path) as pdf:
            doc.page_count = len(pdf)
            doc.save(update_fields=["page_count"])

            for page_num, page in enumerate(pdf, start=1):
                # --- 1. Native text extraction ---
                native = extract_native_text(page)
                native_text = native["text"]
                native_word_count = len(native.get("words", []))

                # --- 2. Determine if OCR needed ---
                use_ocr = False
                if len(native_text.strip()) < 50 or native_word_count < 10:
                    use_ocr = True

                # --- 3. Render page to image (for both metrics and OCR) ---
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = os.path.join(doc_folder, f"page_{page_num}.png")
                pix.save(img_path)

                page_width = pix.width
                page_height = pix.height
                page_dpi = 72 * 2  # 2x zoom

                # --- 4. Preprocess image ---
                pre_path = preprocess_image(img_path)

                # --- 5. OCR if needed ---
                ocr_result = None
                if use_ocr:
                    ocr_result = run_ocr_with_boxes(pre_path, lang="rus+eng")
                    all_confidences.append(ocr_result["avg_confidence"])

                # --- 6. Choose final text ---
                final_text = native_text if not use_ocr else ocr_result["text"]
                if not use_ocr and len(native_text.strip()) < 10 and ocr_result:
                    # Fallback: native almost empty but OCR has something
                    final_text = ocr_result["text"]

                # --- 7. Build structured data ---
                structured = {
                    "page_number": page_num,
                    "width": page_width,
                    "height": page_height,
                    "dpi": page_dpi,
                    "rotation": 0,
                    "native": {
                        "text": native_text,
                        "word_count": native_word_count,
                        "line_count": len(native.get("lines", [])),
                        "block_count": len(native["text"].split("\n\n")) if native_text else 0,
                    },
                    "ocr": {
                        "used": use_ocr,
                        "avg_confidence": ocr_result["avg_confidence"] if ocr_result else None,
                        "word_count": ocr_result["word_count"] if ocr_result else 0,
                        "blocks": [
                            {
                                "bbox": b["bbox"],
                                "line_count": len(b["lines"]),
                                "word_count": sum(len(l.get("words", [])) for l in b["lines"]),
                            }
                            for b in (ocr_result["blocks"] if ocr_result else [])
                        ],
                        "words": [
                            {
                                "text": w["text"],
                                "bbox": w["bbox"],
                                "confidence": w["confidence"],
                            }
                            for w in (ocr_result["words"] if ocr_result else [])
                        ][:1000],  # Cap at 1000 words to avoid huge JSON
                    },
                }

                # Save page
                DocumentPage.objects.create(
                    document=doc,
                    page_number=page_num,
                    width=page_width,
                    height=page_height,
                    dpi=page_dpi,
                    rotation=0,
                    structured_data=structured,
                    native_text=native_text,
                    ocr_text=ocr_result["text"] if ocr_result else "",
                    avg_confidence=ocr_result["avg_confidence"] if ocr_result else None,
                )

                if final_text.strip():
                    text_parts.append(f"--- Страница {page_num} ---\n{final_text}")

                # Cleanup
                os.remove(img_path)
                if pre_path != img_path and os.path.exists(pre_path):
                    os.remove(pre_path)

        # Cleanup folder if empty
        if os.path.isdir(doc_folder) and not os.listdir(doc_folder):
            os.rmdir(doc_folder)

        full_text = "\n\n".join(text_parts)
        doc.extracted_text = full_text
        doc.status = Document.Status.DONE
        doc.avg_confidence = round(sum(all_confidences) / len(all_confidences), 2) if all_confidences else None
        doc.save()

        return {
            "id": doc.id,
            "status": doc.status,
            "page_count": doc.page_count,
            "avg_confidence": doc.avg_confidence,
            "text_preview": full_text[:500] + "..." if len(full_text) > 500 else full_text,
        }

    except Exception as e:
        doc.status = Document.Status.ERROR
        doc.error_message = str(e)
        doc.save()
        return {"error": str(e)}
