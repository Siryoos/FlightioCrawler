FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    git \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CRAWL4AI_BROWSER_PATH=/usr/bin/chromium
ENV PYTHONPATH=/app

# Create app user for security
RUN groupadd -r flightio && useradd -r -g flightio flightio

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

# Copy application code
COPY . .

# Create required directories and set permissions
RUN mkdir -p logs data/storage requests/pages models \
    && chown -R flightio:flightio /app

# Switch to non-root user
USER flightio

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 