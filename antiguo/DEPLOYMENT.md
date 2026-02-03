# Deployment README

## Quick Deploy to Oracle Cloud

### Prerequisites
- SSH key file at: `C:\Users\alons\Downloads\ssh-key-2025-12-04.key`
- Server IP: `158.179.214.56`

### Deploy Command (PowerShell)
```powershell
.\deploy.ps1
```

### What Gets Deployed
- **Service**: Arbitrage Scanner (runs every 5 minutes)
- **Output**: `output/qa_matches.csv` with arbitrage opportunities
- **Logs**: `logs/` directory

### Monitor After Deployment

**View live logs:**
```powershell
ssh -i "C:\Users\alons\Downloads\ssh-key-2025-12-04.key" ubuntu@158.179.214.56 "cd /home/ubuntu/arbitrage_platform && docker-compose logs -f arbitrage_scanner"
```

**Check for matches:**
```powershell
ssh -i "C:\Users\alons\Downloads\ssh-key-2025-12-04.key" ubuntu@158.179.214.56 "tail -20 /home/ubuntu/arbitrage_platform/output/qa_matches.csv"
```

**SSH to server:**
```powershell
ssh -i "C:\Users\alons\Downloads\ssh-key-2025-12-04.key" ubuntu@158.179.214.56
```

### On the Server

**Check status:**
```bash
cd /home/ubuntu/arbitrage_platform
docker-compose ps
```

**View logs:**
```bash
docker-compose logs -f arbitrage_scanner
```

**Restart service:**
```bash
docker-compose restart arbitrage_scanner
```

**Update code:**
1. Run `.\deploy.ps1` from your local machine (it will re-upload and rebuild)

### Configuration

Edit `.env.docker` before deploying to set:
- `ODDS_API_KEY`: Your Odds API key
- `POLY_KEY`: Your Polymarket key (if using)
