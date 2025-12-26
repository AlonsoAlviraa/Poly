# 🤖 Configuración del Bot de Telegram

## Paso 1: Crear el Bot

1. Abre Telegram y busca: **@BotFather**
2. Envía el comando: `/newbot`
3. Sigue las instrucciones:
   - Elige un nombre para tu bot (ej: "Arbitrage Scanner")
   - Elige un username (debe terminar en "bot", ej: "my_arbitrage_bot")
4. **BotFather te dará un TOKEN** - ¡Guárdalo!
   - Formato: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

## Paso 2: Obtener tu Chat ID

1. Dale click a "Start" en tu nuevo bot
2. Busca en Telegram: **@userinfobot**
3. Dale "Start" y te dará tu **ID numérico**
   - Formato: `123456789`

## Paso 3: Guardar la Configuración

Una vez tengas ambos valores, avísame y los configuraremos automáticamente en el servidor.

## Alternativa: Configuración Manual

Si prefieres hacerlo manualmente:

```bash
ssh -i "C:\Users\alons\Downloads\ssh-key-2025-12-04.key" ubuntu@158.179.214.56

# Editar el archivo .env
nano /home/ubuntu/arbitrage_platform/.env

# Añadir estas líneas (con tus valores):
TELEGRAM_BOT_TOKEN=TU_TOKEN_AQUI
TELEGRAM_CHAT_ID=TU_CHAT_ID_AQUI

# Guardar: Ctrl+O, Enter, Ctrl+X
```

## Paso 4: Activar el Cron Job

Una vez configurado el bot, ejecutaremos:
```bash
crontab -e
# Añadir: */5 * * * * /home/ubuntu/arbitrage_platform/run_scanner.sh
```

Esto ejecutará el scanner cada 5 minutos y te enviará alertas de oportunidades de arbitraje por Telegram.
