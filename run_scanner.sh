#!/bin/bash
# Arbitrage Scanner Cron Job
# Runs every 5 minutes to detect betting arbitrage opportunities

cd /home/ubuntu/arbitrage_platform

# Log file with timestamp
LOG_FILE="logs/cron_$(date +%Y%m%d).log"

# Ensure logs directory exists
mkdir -p logs

# Run the scanner and log output
echo "=== Scan started at $(date) ===" >> "$LOG_FILE"
python3 qa_sweep.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "=== Scan finished with exit code $EXIT_CODE at $(date) ===" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Keep only last 7 days of logs
find logs/ -name "cron_*.log" -mtime +7 -delete
