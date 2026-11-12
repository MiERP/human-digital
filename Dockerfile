# Havs Robot (human-digital) — Doraemon English Buddy
# Python 3.12 + FastAPI/uvicorn. Cổng nội bộ: 1709.
#
# Build:  docker build -t havs-robot .
# Run:    docker run -p 127.0.0.1:1709:1709 -v ./data:/app/data --env-file .env havs-robot

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=production \
    HOST=0.0.0.0 \
    PORT=1709

# gcc để phòng trường hợp wheel không có sẵn cho platform này
RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependency trước để tận dụng cache layer
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Mã nguồn backend
COPY backend/ .

# Nơi chứa SQLite (child_memory.db) + emotions + audit log
RUN mkdir -p /app/data

EXPOSE 1709

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1709/health')" || exit 1

CMD ["python", "main.py"]
