
import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def test_bypass_waf():
    username = os.getenv('BETFAIR_USERNAME')
    password = os.getenv('BETFAIR_PASSWORD')
    app_key = os.getenv('BETFAIR_APP_KEY_DELAY')
    cert_path = os.getenv('BETFAIR_CERT_PATH')
    key_path = os.getenv('BETFAIR_KEY_PATH')

    print(f"--- 🛡️ Betfair Spain WAF Bypass Test ---")
    
    # Cabeceras de Metadatos (Sec-Fetch) para simular navegador real
    headers = {
        "X-Application": app_key,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Origin": "https://www.betfair.es",
        "Referer": "https://www.betfair.es/",
    }

    data = {
        "username": username,
        "password": password
    }

    # Usamos el subdominio de identidad para España
    login_url = "https://identitysso.betfair.es/api/certlogin"

    try:
        # Forzamos HTTP/1.1 para evitar discrepancias de TLS/HTTP2 Fingerprinting básico
        async with httpx.AsyncClient(
            cert=(cert_path, key_path), 
            http1=True, 
            http2=False,
            verify=True
        ) as client:
            print(f"🚀 Enviando petición de login a: {login_url}")
            response = await client.post(login_url, headers=headers, data=data)
            
            print(f"📊 Código de Respuesta: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('loginStatus')
                print(f"✅ Respuesta JSON recibida: {status}")
                if status == 'SUCCESS':
                    print("💎 LOGIN EXITOSO!")
                    print(f"Token: {result.get('sessionToken')[:15]}...")
                else:
                    print(f"❌ Login rechazado por Betfair: {status}")
            elif response.status_code == 403:
                print("🛑 BLOQUEO 403 PERSISTENTE.")
                if "<!DOCTYPE html>" in response.text:
                    print("⚠️ El Firewall sigue detectando la huella digital.")
                else:
                    print(f"Detalle: {response.text[:200]}")
            else:
                print(f"❓ Código {response.status_code}: {response.text[:200]}")

    except Exception as e:
        print(f"💥 Error crítico: {e}")

if __name__ == "__main__":
    asyncio.run(test_bypass_waf())
