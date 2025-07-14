#!/bin/bash

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "PostgreSQL started"

# Start the FastAPI app
exec uvicorn app:app --host 0.0.0.0 --port 8000 --reload
