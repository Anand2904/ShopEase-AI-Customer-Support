
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Copy Python dependencies.
COPY requirements.txt ./

# Install required packages.
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy the ShopEase application.
COPY . .

# Streamlit default port.
EXPOSE 8501

# Start the unified ShopEase application.
CMD ["streamlit", "run", "unified_portal.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--server.fileWatcherType=none"]
