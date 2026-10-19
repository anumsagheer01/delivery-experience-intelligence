FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
COPY scripts/ scripts/
COPY configs/ configs/
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8080"]
