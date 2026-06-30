FROM python:3.12-slim

# opencv-python-headless needs libgomp; add fonts so server-side rendering works
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

ENV PYTHONPATH=/app/backend
ENV PORT=8080
EXPOSE 8080

# Most container hosts inject $PORT; default to 8080 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
