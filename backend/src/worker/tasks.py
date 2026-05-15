"""
The three concrete task implementations.

Each function:
  - Accepts a `payload: dict`
  - Returns a result dict on success
  - Raises an exception on failure (triggers retry logic in executor)
"""

import io
import logging
import time

import requests
from bs4 import BeautifulSoup
from PIL import Image
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. image_processing — CPU-bound
#    payload: { "image_url": str, "operations": ["resize", "grayscale", "watermark"] }
# ---------------------------------------------------------------------------

def image_processing(payload: dict) -> dict:
    image_url: str = payload["image_url"]
    operations: list = payload.get("operations", [])

    logger.info("[Task] image_processing: fetching %s", image_url)
    response = requests.get(image_url, timeout=15)
    response.raise_for_status()

    img = Image.open(io.BytesIO(response.content))
    original_size = img.size

    for op in operations:
        if op == "resize":
            img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
            logger.debug("[Task] resized to %s", img.size)

        elif op == "grayscale":
            img = img.convert("L")
            logger.debug("[Task] converted to grayscale")

        elif op == "watermark":
            # Convert to RGBA so we can paste text safely
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "VortexQueue", fill=(255, 255, 255, 180))
            logger.debug("[Task] watermark applied")

        else:
            logger.warning("[Task] unknown operation '%s', skipping", op)

    # In production: save to object storage. Here we just record dimensions.
    return {
        "original_size": original_size,
        "final_size": img.size,
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
    response.raise_for_status()   # 4xx / 5xx → exception → retry

    soup = BeautifulSoup(response.text, "html.parser")
    results: dict = {}

    for selector in selectors:
        elements = soup.select(selector)
        results[selector] = [el.get_text(strip=True) for el in elements]
        logger.debug("[Task] selector '%s' → %d matches", selector, len(elements))

    return {"url": url, "scraped": results}


# ---------------------------------------------------------------------------
# 3. bulk_invoice — I/O-bound (idempotency matters most here)
#    payload: { "customer_id": str, "line_items": [...], "email": str }
# ---------------------------------------------------------------------------

def bulk_invoice(payload: dict) -> dict:
    customer_id: str = payload["customer_id"]
    line_items: list = payload.get("line_items", [])
    email: str = payload["email"]

    logger.info("[Task] bulk_invoice: generating invoice for customer %s", customer_id)

    # Build PDF in memory
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
    logger.info(
        "[Task] bulk_invoice: PDF generated (%d bytes), 'sending' to %s",
        len(pdf_bytes),
        email,
    )

    # Simulate sending email (log only — no real SMTP)
    logger.info("[Task] bulk_invoice: EMAIL SENT to %s (simulated)", email)

    return {
        "customer_id": customer_id,
        "email": email,
        "total": total,
        "invoice_size_bytes": len(pdf_bytes),
        "items_count": len(line_items),
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
    """Route task_type to the correct handler. Raises KeyError for unknown types."""
    handler = TASK_MAP.get(task_type)
    if handler is None:
        raise ValueError(f"Unknown task_type: '{task_type}'")
    return handler(payload)
