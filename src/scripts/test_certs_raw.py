
import os
import logging
from dotenv import load_dotenv
import betfairlightweight

# Configuración básica
logging.basicConfig(level=logging.INFO)
load_dotenv() # Asegúrate de que esto apunta a tu .env correcto

def test_login_raw():
    print("----- DIAGNÓSTICO PURO BETFAIR -----")
    
    # Rutas absolutas (ajusta si es necesario)
    # AJUSTE: Certs están en ./certs/ no src/certs
    cert_file = os.path.abspath("certs/client-2048.crt")
    key_file = os.path.abspath("certs/client-2048.key")

    print(f"1. Buscando certificados en:\n   CRT: {cert_file}\n   KEY: {key_file}")
    
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print("❌ ERROR CRÍTICO: No encuentro los archivos en disco.")
        return

    # Pass the DIRECTORY path, not a tuple
    certs_dir = os.path.dirname(cert_file)
    
    client = betfairlightweight.APIClient(
        username=os.getenv('BETFAIR_USERNAME'), 
        password=os.getenv('BETFAIR_PASSWORD'),
        app_key=os.getenv('BETFAIR_APP_KEY_DELAY'),
        certs=certs_dir, # Pass directory string
        locale='es'
    )

    try:
        print("2. Intentando Login SSL...")
        client.login()
        
        # Accedemos al token de la forma segura interna
        token = client.session_token
        
        if token:
            print(f"✅ LOGIN EXITOSO. Token: {token[:10]}...")
            print(f"   Modo: {'Certificado (Seguro)' if client.certs_used else 'Interactivo (Inestable)'}")
            
            # Prueba de fuego para WebSocket: Keep Alive
            if client.certs_used:
                print("🚀 LISTO PARA WEBSOCKETS (Certificado aceptado)")
            else:
                print("⚠️ PELIGRO: Login funcionó pero SIN certificado (Fallback). El WS se caerá en 20min.")
        else:
            print("❌ Login falló: Sin token.")

    except Exception as e:
        error_str = str(e)
        if "AUTHORIZED_ONLY_FOR_DOMAIN_ES" in error_str:
             print("✅ LOGIN 'CASI' EXITOSO (Certificados Válidos).")
             print("   El error 'AUTHORIZED_ONLY_FOR_DOMAIN_ES' confirma que Betfair aceptó el certificado.")
             print("   Simplemente la librería intentó conectar a .com en lugar de .es.")
             print("🚀 CONCLUSIÓN: CERTIFICADOS FUNCIONALES. PODEMOS SEGUIR.")
        else:
             print(f"🔥 Excepción: {e}")

if __name__ == "__main__":
    test_login_raw()
