FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/

# Default command — overridden per-service in docker-compose.yml
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
