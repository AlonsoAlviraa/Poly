# PowerShell Deployment Script for Arbitrage Platform
# Deploy to Oracle Cloud Server

$SERVER_IP = "158.179.214.56"
$SERVER_USER = "ubuntu"
$SSH_KEY = "C:\Users\alons\Downloads\ssh-key-2025-12-04.key"
$REMOTE_PATH = "/home/ubuntu/arbitrage_platform"
$LOCAL_PATH = "C:\Users\alons\Desktop\FUTURO\APU"

Write-Host "=== Deploying Arbitrage Platform to Oracle Cloud ===" -ForegroundColor Green

# Step 1: Create remote directory
Write-Host "`nStep 1: Creating remote directory..." -ForegroundColor Yellow
ssh -i $SSH_KEY "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${REMOTE_PATH}"

# Step 2: Upload files
Write-Host "`nStep 2: Uploading files..." -ForegroundColor Yellow
scp -i $SSH_KEY -r "${LOCAL_PATH}\*" "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/"

# Step 3: Deploy on server
Write-Host "`nStep 3: Building and starting Docker containers..." -ForegroundColor Yellow

# Execute commands separately to avoid line ending issues
ssh -i $SSH_KEY "${SERVER_USER}@${SERVER_IP}" "cd /home/ubuntu/arbitrage_platform && cp .env.docker .env"
ssh -i $SSH_KEY "${SERVER_USER}@${SERVER_IP}" "cd /home/ubuntu/arbitrage_platform && docker-compose down"
ssh -i $SSH_KEY "${SERVER_USER}@${SERVER_IP}" "cd /home/ubuntu/arbitrage_platform && docker-compose up -d --build"
ssh -i $SSH_KEY "${SERVER_USER}@${SERVER_IP}" "cd /home/ubuntu/arbitrage_platform && docker-compose ps"
ssh -i $SSH_KEY "${SERVER_USER}@${SERVER_IP}" "cd /home/ubuntu/arbitrage_platform && docker-compose logs --tail=20 arbitrage_scanner"

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Green
Write-Host "`nUseful commands:" -ForegroundColor Cyan
Write-Host "  View logs:     ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_IP} 'cd ${REMOTE_PATH} && docker-compose logs -f arbitrage_scanner'"
Write-Host "  Check matches: ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_IP} 'cat ${REMOTE_PATH}/output/qa_matches.csv'"
Write-Host "  SSH to server: ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_IP}"
