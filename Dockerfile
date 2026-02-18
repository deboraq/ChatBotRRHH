FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-full.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -r requirements-full.txt

COPY . .

ENV PORT=8080

CMD ["sh", "-c", "gunicorn web_chat:flask_app --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120"]
