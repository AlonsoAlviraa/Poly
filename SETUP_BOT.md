# Automated Arbitrage Bot - Setup Guide

## 🎯 Qué hace este bot

Bot completamente automático que:
1. Escanea Polymarket y SX Bet cada 60 segundos
2. Detecta oportunidades de arbitraje (min 3% profit)
3. **Ejecuta trades automáticamente** sin intervención
4. Te notifica en Telegram de cada operación

## 📋 Requisitos Previos

### 1. Crear Wallet de Polygon

```bash
# Instalar MetaMask o usar este script
python -c "from eth_account import Account; acc = Account.create(); print(f'Address: {acc.address}\\nPrivate Key: {acc.key.hex()}')"
```

⚠️ **GUARDA LA PRIVATE KEY EN LUGAR SEGURO**

### 2. Conseguir USDC

1. Compra USDC en Binance/Coinbase
2. Envía $500 USDC a tu wallet en **Polygon network**
3. Bridge $250 a SX Network:
   - Ve a https://sx.bet
   - Click "Bridge with Glide"
   - Deposit $250 USDC

## 🚀 Instalación

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar .env
cp .env.template .env
nano .env

# Añadir:
# PRIVATE_KEY=0x... (tu private key)
# WALLET_ADDRESS=0x... (tu wallet address)

# 3. Probar wallet
python src/wallet/wallet_manager.py

# 4. Probar SX Bet
python src/exchanges/sx_bet_client.py

# 5. Probar detector
python src/core/arbitrage_detector.py
```

## ▶️ Ejecutar Bot

### Modo Manual (testing)
```bash
python automated_bot.py
```

### Modo 24/7 (servidor)
```bash
# En tu servidor Oracle Cloud
nohup python automated_bot.py > bot.log 2>&1 &

# Ver logs en tiempo real
tail -f bot.log
```

## 📊 Monitoring

El bot envía notificaciones a Telegram:
- ✅ Cada trade ejecutado
- 💰 Profit acumulado
- ⚠️ Errores y problemas

## ⚙️ Configuración

Edita `.env` para ajustar parámetros:

```bash
MIN_PROFIT_PERCENT=3.0      # Mínimo 3% profit
MAX_POSITION_SIZE=100       # Max $100 por trade
SCAN_INTERVAL_SECONDS=60    # Escanear cada 60s
```

## 🛡️ Seguridad

- ✅ Private key solo en `.env` (NUNCA en git)
- ✅ Límites de posición para proteger capital
- ✅ Slippage protection
- ✅ Emergency stop si detecta problemas

## 📈 Rendimiento Esperado

Con $500 capital:
- 2-5 trades/día
- 3-7% profit por trade
- **$10-30/día** estimado
- **$300-900/mes** (60-180% ROI)

## 🔧 Troubleshooting

**"PRIVATE_KEY not found"**
→ Revisa que .env tenga la private key

**"Insufficient balance"**
→ Añade más USDC a tu wallet

**"No opportunities found"**
→ Normal, espera. Oportunidades vienen en oleadas

**Bot se para solo**
→ Revisa logs: `tail -f bot.log`

## 📞 Soporte

Revisa logs en Telegram o archivo `bot.log` para debugging.
