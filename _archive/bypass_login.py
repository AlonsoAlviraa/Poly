from curl_cffi import requests
import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN ---
APP_KEY = os.getenv('BETFAIR_APP_KEY_DELAY') 
USERNAME = os.getenv('BETFAIR_USERNAME')
PASSWORD = os.getenv('BETFAIR_PASSWORD')

# Rutas absolutas para evitar errores de lectura
CERT_FILE = os.path.abspath('./certs/client-2048.crt')
KEY_FILE = os.path.abspath('./certs/client-2048.key')

URL_ES = "https://identitysso.betfair.es/api/certlogin"

def login_with_bypass():
    print(f"🔧 Cargando certificado desde: {CERT_FILE}")
    print(f"👤 Usuario: {USERNAME}")
    print(f"🔑 App Key: {APP_KEY[:5]}...") # Obfuscated log
    
    # Cabeceras exactas de un navegador Chrome 120
    headers = {
        "X-Application": APP_KEY,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Origin": "https://www.betfair.es",
        "Referer": "https://www.betfair.es/"
    }

    payload = {
        "username": USERNAME,
        "password": PASSWORD
    }

    try:
        # Usamos 'impersonate="chrome120"' para clonar la huella TLS
        # Esto evita el error 403 del Firewall y el error 0x80092002 de Windows
        print(f"🚀 Enviando petición a {URL_ES}...")
        response = requests.post(
            URL_ES,
            data=payload,
            headers=headers,
            cert=(CERT_FILE, KEY_FILE),
            impersonate="chrome120", 
            timeout=10
        )

        # Análisis de respuesta
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('loginStatus')
            if status == 'SUCCESS':
                print("\n✅ ¡ÉXITO! LOGIN CONFIRMADO")
                print(f"🔑 Session Token: {data.get('sessionToken')}")
            else:
                print(f"\n❌ Login rechazado por API: {status}")
                if status == 'AUTHORIZED_ONLY_FOR_DOMAIN_ES':
                    print("⚠️ Cuenta restringida a dominio ES.")
            return data.get('sessionToken')
            
        elif response.status_code == 403:
            print("\n❌ FALLO 403 (Forbidden)")
            print("El Firewall ha dejado pasar la conexión (ya no es HTML), pero la API rechaza las credenciales o la IP.")
            print(f"Respuesta API: {response.text}")
            
        else:
            print(f"\n⚠️ Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"\n🔥 Error Crítico: {e}")

if __name__ == "__main__":
    login_with_bypass()
