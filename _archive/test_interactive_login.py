import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Sustituye con tus valores reales
username = os.getenv('BETFAIR_USERNAME')
password = os.getenv('BETFAIR_PASSWORD')
app_key = os.getenv('BETFAIR_APP_KEY_DELAY')
app_key_live = os.getenv('BETFAIR_APP_KEY_LIVE')

# Endpoint oficial para login interactivo en España
url = 'https://identitysso.betfair.es/api/login'

def attempt_login(key_name, key_value):
    print(f"\n--- Probando login con {key_name} ---")
    headers = {
        'X-Application': key_value,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'User-Agent': 'QuantArbBot/2.0' # Identificación legítima
    }
    
    # Payload estándar, sin certificados
    payload = {
        'username': username,
        'password': password
    }

    try:
        print(f"Enviando POST a {url}...")
        response = requests.post(url, headers=headers, data=payload)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"DEBUG Response: {data}")
            if data.get('loginStatus') == 'SUCCESS' or data.get('status') == 'SUCCESS':
                session_token = data.get('sessionToken') or data.get('token')
                print(f'✅ Login EXITOSO.')
                print(f'🔑 Session Token: {session_token[:15]}...')
                return True
            else:
                print(f'❌ Error API: {data.get("loginStatus", "Unknown")}')
                if 'errorDetails' in data:
                    print(f'Detalles: {data["errorDetails"]}')
        elif response.status_code == 403:
             print("🛑 403 Forbidden - El WAF sigue activo.")
        else:
            print(f'⚠️ Error HTTP: {response.status_code} - {response.text[:200]}')
            
    except Exception as e:
        print(f"🔥 Excepción: {e}")
    
    return False

if __name__ == "__main__":
    # Intentar primero con la Delay Key
    if not attempt_login("DELAY Key", app_key):
        # Si falla, intentar con la Live Key (a veces requerida para login en España)
        if app_key_live:
             attempt_login("LIVE Key", app_key_live)
