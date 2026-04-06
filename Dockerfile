FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SIGNAL_ENV=production \
    QUEUE_MODE=memory \
    SQLITE_URL=sqlite+aiosqlite:///./signal_dev.db \
    PORT=8000

CMD python -c "import os; os.system(f'uvicorn signalapp.app.main:app --host 0.0.0.0 --port {os.environ.get(\"PORT\", \"8000\")}')"
