FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (e.g. for ClamAV binding if needed later)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create storage directory
RUN mkdir -p storage

# Environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

EXPOSE 5001

CMD ["python", "app.py"]
