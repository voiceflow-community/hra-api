# Hallucination Risk Assessment API - Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY .env.example .env

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --user-group appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose the default port (can be overridden with .env)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-8080}/api/health || exit 1

# Default command - runs with environment variables from .env
CMD ["python", "api/rest_api.py", "--host", "0.0.0.0"]