# Multi-stage build optimized for production
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---

# Stage 1: Build dependencies and install packages
FROM base as builder

# Install build dependencies
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt \
    && playwright install chromium --with-deps

# ---

# Stage 2: Runtime stage with distroless approach
FROM python:3.11-slim as runtime

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-noto \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    curl \
    postgresql-client \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/*

# Create non-root user
RUN groupadd -r flightio && useradd -r -g flightio flightio

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CRAWL4AI_BROWSER_PATH=/usr/bin/chromium \
    PYTHONPATH=/app \
    PATH="/home/flightio/.local/bin:$PATH"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/flightio/.local

# Copy application code (optimized order for better caching)
COPY --chown=flightio:flightio requirements.txt ./
COPY --chown=flightio:flightio config/ ./config/
COPY --chown=flightio:flightio data/statics/ ./data/statics/
COPY --chown=flightio:flightio *.py ./
COPY --chown=flightio:flightio adapters/ ./adapters/
COPY --chown=flightio:flightio api/ ./api/
COPY --chown=flightio:flightio crawlers/ ./crawlers/
COPY --chown=flightio:flightio utils/ ./utils/
COPY --chown=flightio:flightio monitoring/ ./monitoring/

# Create required directories with proper permissions
RUN mkdir -p logs data/storage requests/pages models \
    && chown -R flightio:flightio /app \
    && chmod -R 755 /app

# Switch to non-root user
USER flightio

# Expose port
EXPOSE 8000

# Enhanced health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/system/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "main_v2:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"] 