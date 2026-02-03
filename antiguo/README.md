# Arbitrage Bot

Bot de arbitraje entre Polymarket y SX Bet para detectar oportunidades de trading.

## Características

- 🔍 Escaneo automático de mercados en Polymarket y SX Bet
- 📊 Cálculo de VWAP (Volume Weighted Average Price) para precios reales
- 🔔 Notificaciones por Telegram
- 🚫 Sistema anti-spam con deduplicación de señales
- 🐳 Despliegue con Docker

## Configuración

1. Copia `.env.template` a `.env`
2. Configura las variables de entorno:
   - `ODDS_API_KEY` - API key para datos
   - `TELEGRAM_BOT_TOKEN` - Token del bot de Telegram
   - `TELEGRAM_CHAT_ID` - ID del chat de Telegram
   - `MIN_PROFIT_PERCENT` - Umbral mínimo de rentabilidad (default: 1.0)

## Despliegue

```bash
# Local
python automated_bot.py

# Docker
docker-compose up -d --build

# Oracle Cloud
powershell -ExecutionPolicy Bypass -File .\deploy_fast.ps1
```

## Estructura del Proyecto

```
├── src/
│   ├── core/
│   │   └── arbitrage_detector.py    # Lógica principal de detección
│   ├── collectors/
│   │   └── polymarket.py            # Cliente de Polymarket
│   ├── exchanges/
│   │   └── sx_bet_client.py         # Cliente de SX Bet
│   └── utils/
│       ├── telegram_bot.py          # Notificaciones
│       ├── cache_manager.py         # Deduplicación
│       └── normalization.py         # Normalización de texto
├── automated_bot.py                  # Bot principal
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Notas

- El bot requiere que haya eventos coincidentes entre Polymarket y SX Bet
- Actualmente hay poco overlap entre las plataformas (Polymarket = política/crypto, SX Bet = tenis/fútbol sudamericano)
