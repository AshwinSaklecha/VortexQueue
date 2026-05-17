import base64
import io

import pytest
from PIL import Image

from src.worker import tasks


class FakeImageResponse:
    def __init__(self, content: bytes):
        self.headers = {"Content-Length": str(len(content))}
        self._content = content

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        yield self._content


class FakeHtmlResponse:
    text = """
    <html>
      <body>
        <h1>Example Domain</h1>
        <p>First paragraph</p>
        <p>Second paragraph</p>
      </body>
    </html>
    """

    def raise_for_status(self):
        return None


@pytest.fixture
def tiny_png_bytes() -> bytes:
    image = Image.new("RGB", (8, 6), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_processing_returns_encoded_image(monkeypatch, tiny_png_bytes):
    def fake_get(*args, **kwargs):
        return FakeImageResponse(tiny_png_bytes)

    monkeypatch.setattr(tasks.requests, "get", fake_get)

    result = tasks.image_processing(
        {
            "image_url": "https://example.com/image.png",
            "operations": ["resize", "grayscale"],
        }
    )

    assert result["format"] == "PNG"
    assert result["mode"] == "L"
    assert result["original_size"] == [8, 6]
    assert result["final_size"] == [4, 3]
    assert result["operations_applied"] == ["resize", "grayscale"]
    assert base64.b64decode(result["image_b64"])


def test_image_processing_requires_image_url():
    with pytest.raises(KeyError):
        tasks.image_processing({"operations": ["resize"]})


def test_web_scraping_returns_selected_text(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeHtmlResponse()

    monkeypatch.setattr(tasks.requests, "get", fake_get)

    result = tasks.web_scraping(
        {"url": "https://example.com", "selectors": ["h1", "p"]}
    )

    assert result["url"] == "https://example.com"
    assert result["scraped"]["h1"] == ["Example Domain"]
    assert result["scraped"]["p"] == ["First paragraph", "Second paragraph"]


def test_bulk_invoice_returns_encoded_pdf():
    result = tasks.bulk_invoice(
        {
            "customer_id": "DEMO-001",
            "line_items": [{"name": "Widget", "qty": 2, "unit_price": 49.99}],
            "email": "demo@example.com",
        }
    )

    assert result["filename"] == "invoice_DEMO-001.pdf"
    assert result["total"] == 99.98
    assert result["items_count"] == 1
    assert result["email"] == "demo@example.com"
    assert base64.b64decode(result["pdf_b64"]).startswith(b"%PDF")
