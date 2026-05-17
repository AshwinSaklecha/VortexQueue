"""
The three concrete task implementations.

Each function:
  - Accepts a `payload: dict`
  - Returns a result dict on success (stored in DB, returned via API)
  - Raises an exception on failure (triggers retry logic in executor)
"""

import base64
import io
import logging

import requests
from bs4 import BeautifulSoup
from PIL import Image
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB hard cap on input image download


# ---------------------------------------------------------------------------
# 1. image_processing — CPU-bound
#    payload: { "image_url": str, "operations": ["resize", "grayscale", "watermark"] }
# ---------------------------------------------------------------------------

def image_processing(payload: dict) -> dict:
    image_url: str = payload["image_url"]
    operations: list = payload.get("operations", [])

    logger.info("[Task] image_processing: fetching %s", image_url)

    # Stream the download and enforce a hard size limit
    response = requests.get(image_url, timeout=15, stream=True)
    response.raise_for_status()

    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image too large: {int(content_length) // 1024}KB (max 5MB)"
        )

    chunks = []
    downloaded = 0
    for chunk in response.iter_content(chunk_size=65536):
        downloaded += len(chunk)
        if downloaded > MAX_IMAGE_BYTES:
            raise ValueError(f"Image exceeds 5MB limit during download")
        chunks.append(chunk)
    raw_bytes = b"".join(chunks)

    img = Image.open(io.BytesIO(raw_bytes))
    original_size = list(img.size)

    for op in operations:
        if op == "resize":
            img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
            logger.debug("[Task] resized to %s", img.size)

        elif op == "grayscale":
            img = img.convert("L")
            logger.debug("[Task] converted to grayscale")

        elif op == "watermark":
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "VortexQueue", fill=(255, 255, 255, 180))
            logger.debug("[Task] watermark applied")

        else:
            logger.warning("[Task] unknown operation '%s', skipping", op)

    # Encode the processed image as base64 PNG for storage and download
    out_buf = io.BytesIO()
    save_format = "PNG"
    # Grayscale (L mode) saves fine as PNG; RGBA also fine; RGB fine
    img.save(out_buf, format=save_format)
    image_b64 = base64.b64encode(out_buf.getvalue()).decode("utf-8")

    logger.info(
        "[Task] image_processing: done — original %s → final %s, mode=%s, encoded=%dKB",
        original_size, list(img.size), img.mode, len(image_b64) // 1024,
    )

    return {
        "image_b64": image_b64,
        "format": save_format,
        "original_size": original_size,
        "final_size": list(img.size),
        "mode": img.mode,
        "operations_applied": operations,
    }


# ---------------------------------------------------------------------------
# 2. web_scraping — Network-bound
#    payload: { "url": str, "selectors": ["h1", ".price", "#description"] }
# ---------------------------------------------------------------------------

def web_scraping(payload: dict) -> dict:
    url: str = payload["url"]
    selectors: list = payload.get("selectors", ["h1"])

    logger.info("[Task] web_scraping: fetching %s", url)
    response = requests.get(url, timeout=20, headers={"User-Agent": "VortexQueue/1.0"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    scraped: dict = {}

    for selector in selectors:
        elements = soup.select(selector)
        scraped[selector] = [el.get_text(strip=True) for el in elements]
        logger.debug("[Task] selector '%s' → %d matches", selector, len(elements))

    total_matches = sum(len(v) for v in scraped.values())
    logger.info("[Task] web_scraping: done — %d total matches across %d selectors", total_matches, len(selectors))

    return {"url": url, "scraped": scraped}


# ---------------------------------------------------------------------------
# 3. bulk_invoice — I/O-bound (idempotency matters most here)
#    payload: { "customer_id": str, "line_items": [...], "email": str }
# ---------------------------------------------------------------------------

def bulk_invoice(payload: dict) -> dict:
    customer_id: str = payload["customer_id"]
    line_items: list = payload.get("line_items", [])
    email: str = payload["email"]

    logger.info("[Task] bulk_invoice: generating invoice for customer %s", customer_id)

    buffer = io.BytesIO()
    pdf = rl_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, height - 60, f"Invoice — Customer: {customer_id}")
    pdf.setFont("Helvetica", 12)

    y = height - 100
    total = 0.0
    for item in line_items:
        name = item.get("name", "Item")
        qty = item.get("qty", 1)
        unit_price = item.get("unit_price", 0.0)
        subtotal = qty * unit_price
        total += subtotal
        pdf.drawString(50, y, f"  {name}  x{qty}  @ ${unit_price:.2f}  =  ${subtotal:.2f}")
        y -= 20

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y - 10, f"Total: ${total:.2f}")
    pdf.save()

    pdf_bytes = buffer.getvalue()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    logger.info(
        "[Task] bulk_invoice: PDF generated (%d bytes), 'sending' to %s (simulated)",
        len(pdf_bytes), email,
    )

    return {
        "pdf_b64": pdf_b64,
        "filename": f"invoice_{customer_id}.pdf",
        "total": round(total, 2),
        "items_count": len(line_items),
        "email": email,
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

TASK_MAP = {
    "image_processing": image_processing,
    "web_scraping": web_scraping,
    "bulk_invoice": bulk_invoice,
}


def run(task_type: str, payload: dict) -> dict:
    """Route task_type to the correct handler. Raises ValueError for unknown types."""
    handler = TASK_MAP.get(task_type)
    if handler is None:
        raise ValueError(f"Unknown task_type: '{task_type}'")
    return handler(payload)
