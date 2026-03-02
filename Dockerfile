# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install system dependencies (Tesseract OCR + Vietnamese language pack)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-vie \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 5 -r requirements.txt

# Pre-download ML models during build so first query is instant
# multilingual-e5-large ~560 MB + ms-marco reranker ~80 MB
RUN python -c "\
from fastembed import TextEmbedding; \
from fastembed.rerank.cross_encoder import TextCrossEncoder; \
print('Downloading multilingual-e5-large...'); \
TextEmbedding('intfloat/multilingual-e5-large'); \
print('Downloading ms-marco reranker...'); \
TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2'); \
print('Models ready.')"

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
