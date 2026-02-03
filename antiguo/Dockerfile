# Arbitrage Platform - Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY config.py .
COPY main.py .
COPY qa_sweep.py .
COPY automated_bot.py .

# Create output directories
RUN mkdir -p logs output

# Run the arbitrage scanner
CMD ["python", "-u", "qa_sweep.py"]
