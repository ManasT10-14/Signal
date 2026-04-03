FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install signalapp in development mode
COPY . .
RUN pip install -e .

# Expose Streamlit port
EXPOSE 8501

# Environment defaults
ENV SIGNAL_ENV=production \
    QUEUE_MODE=memory \
    DATABASE_URL=postgresql+asyncpg://signal:signal@postgres:5432/signal \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
