# Base Image: Python 3.12 Slim (Lightweight)
FROM python:3.12-slim

# Environment Variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install System Dependencies
# pulp requires CBC solver. We install coinor-cbc.
RUN apt-get update && apt-get install -y \
    coinor-cbc \
    coinor-libcbc-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# Install Python Deps
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy Code
COPY . .

# Expose Metrics Port
EXPOSE 8000

# Entrypoint
CMD ["python", "main.py"]
