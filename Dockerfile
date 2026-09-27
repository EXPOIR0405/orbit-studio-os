FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/backend src/backend
COPY data data
ENV PYTHONPATH=/app/src/backend
CMD ["uvicorn", "orbit.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
