FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and multimedia processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy backend package specification
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN cd /app/backend && uv pip install --system -e .

# Copy application code and shared runtime assets
COPY backend/ /app/backend/
COPY configs/ /app/configs/
COPY data/ /app/data/
COPY models/ /app/models/

ENV PYTHONPATH=/app/backend
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
