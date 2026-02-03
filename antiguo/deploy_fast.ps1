# PowerShell Deployment Script (Zip Method)
# Much faster relative to copying thousands of files

$SERVER_IP = "158.179.214.56"
$SERVER_USER = "ubuntu"
$SSH_KEY = "C:\Users\alons\Downloads\ssh-key-2025-12-04.key"
$REMOTE_PATH = "/home/ubuntu/arbitrage_platform"
$ZIP_FILE = "deployment_package.zip"
$LOCAL_PATH = "C:\Users\alons\Desktop\FUTURO\APU"

Write-Host "=== Fast Deploy to Oracle Cloud ===" -ForegroundColor Green

# 1. Create Zip (Already done by python script, but let's ensure)
# python create_package.py

# 2. Upload Zip
Write-Host "`nStep 1: Uploading Zip package (${ZIP_FILE})..." -ForegroundColor Yellow
scp -i $SSH_KEY "${LOCAL_PATH}\${ZIP_FILE}" "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/${ZIP_FILE}"

# 3. Unzip and Build
Write-Host "`nStep 2: Unzipping and Building on Server..." -ForegroundColor Yellow
$CMD = "cd ${REMOTE_PATH} && python3 -m zipfile -e ${ZIP_FILE} . && docker-compose down && docker-compose up -d --build && docker-compose logs --tail=20 arbitrage_scanner"

ssh -i $SSH_KEY "${SERVER_USER}@${SERVER_IP}" $CMD

Write-Host "`n=== Deployment Complete ===" -ForegroundColor Green
Write-Host "Monitor logs with:"
Write-Host "ssh -i $SSH_KEY ${SERVER_USER}@${SERVER_IP} 'cd ${REMOTE_PATH} && docker-compose logs -f arbitrage_scanner'"
