import json
import requests
import os

# Placeholder for Webhook URLs
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(opportunity):
    """
    Sends an alert to configured channels.
    :param opportunity: Dictionary containing opportunity details
    """
    message = format_message(opportunity)
    print(f"ALERT: {message}") # Always print to console

    if DISCORD_WEBHOOK_URL:
        send_discord_alert(message)
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        send_telegram_alert(message)

def format_message(opp):
    return (
        f"🚨 **ARBITRAGE OPPORTUNITY** 🚨\n"
        f"Event: {opp['event']}\n"
        f"Bet On: {opp.get('bet_team', 'N/A')}\n"
        f"Bookie Prob: {opp['bookie_prob']*100:.1f}% (Odds: {opp['bookie_odds']:.2f})\n"
        f"Polymarket Price: {opp['poly_price']*100:.1f}%\n"
        f"💰 **EV: +{opp.get('ev_percent', 0):.2f}%**\n"
        f"💧 Liquidity: ${opp.get('poly_liquidity', 0):.2f}\n"
        f"🔗 [Buy on Polymarket]({opp['poly_link']})"
    )

def send_discord_alert(message):
    data = {"content": message}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
