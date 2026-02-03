#!/bin/bash
# Deploy Arbitrage Platform to Oracle Cloud Server

SERVER_IP="158.179.214.56"
SERVER_USER="ubuntu"
SSH_KEY="C:\Users\alons\Downloads\ssh-key-2025-12-04.key"
REMOTE_PATH="/home/ubuntu/arbitrage_platform"
LOCAL_PATH="C:\Users\alons\Desktop\FUTURO\APU"

echo "=== Deploying Arbitrage Platform to Oracle Cloud ==="

# Step 1: Create remote directory
echo "Step 1: Creating remote directory..."
ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP "mkdir -p $REMOTE_PATH"

# Step 2: Upload files
echo "Step 2: Uploading files..."
scp -i "$SSH_KEY" -r "$LOCAL_PATH"/* $SERVER_USER@$SERVER_IP:$REMOTE_PATH/

# Step 3: SSH into server and deploy
echo "Step 3: Building and starting Docker containers..."
ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP << 'ENDSSH'
cd /home/ubuntu/arbitrage_platform

# Copy environment file
cp .env.docker .env

# Build and start containers
docker-compose down
docker-compose up -d --build

# Show logs
docker-compose logs --tail=50

echo "=== Deployment Complete ==="
echo "View logs: docker-compose logs -f arbitrage_scanner"
echo "Check matches: cat output/qa_matches.csv"
ENDSSH

echo "=== Done ==="
