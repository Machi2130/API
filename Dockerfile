# ============================
# Dockerfile (FastAPI + app)
# ============================
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Make entrypoint executable
RUN chmod +x entry.sh

# Expose port
EXPOSE 8000

# Start app
CMD ["./entry.sh"]
