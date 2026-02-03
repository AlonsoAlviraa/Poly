
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_betfair_spain_connection():
    username = os.getenv('BETFAIR_USERNAME')
    password = os.getenv('BETFAIR_PASSWORD')
    app_key = os.getenv('BETFAIR_APP_KEY_DELAY')
    cert_path = os.getenv('BETFAIR_CERT_PATH')
    key_path = os.getenv('BETFAIR_KEY_PATH')

    print(f"--- Diagnóstico de Conexión Betfair España ---")
    print(f"Cert path: {cert_path}")
    print(f"Key path: {key_path}")

    # Cabeceras sugeridas por el usuario para saltar el WAF
    headers = {
        "X-Application": app_key,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    data = {
        "username": username,
        "password": password
    }

    login_url = "https://identitysso.betfair.es/api/certlogin"

    try:
        async with httpx.AsyncClient(cert=(cert_path, key_path), http1=True) as client:
            print(f"Enviando POST a {login_url}...")
            response = await client.post(login_url, headers=headers, data=data)
            
            print(f"Código de Estado: {response.status_code}")
            print(f"Headers de Respuesta: {response.headers.get('Content-Type')}")
            
            if response.status_code == 200:
                print("¡ÉXITO! Conexión establecida.")
                print(f"Respuesta: {response.json()}")
            elif response.status_code == 403:
                print("ERROR 403: El Firewall sigue bloqueando la petición.")
                if "<!DOCTYPE html>" in response.text:
                    print("Confirmado: Respuesta HTML detectada (WAF Block).")
            else:
                print(f"Error inesperado ({response.status_code}): {response.text[:200]}")

    except Exception as e:
        print(f"Excepción durante la conexión: {e}")

if __name__ == "__main__":
    asyncio.run(test_betfair_spain_connection())
