FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SIGNAL_ENV=production \
    QUEUE_MODE=memory \
    SQLITE_URL=sqlite+aiosqlite:///./signal_dev.db

CMD ["python", "start.py"]
