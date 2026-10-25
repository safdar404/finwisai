# FinWise AI — container image (bonus: Docker deployment)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Keep the SQLite cache in a volume so it survives container restarts.
ENV FINWISE_CACHE_PATH=/app/data/.langchain_cache.db
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
