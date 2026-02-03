# 🏦 Guía Maestra: Configuración de Billeteras (Desde Cero)

Esta guía asume que **NO tienes nada**. Vamos a montar una estructura **profesional** de 2 Billeteras para proteger tu dinero.

---

## 🏗️ La Arquitectura (¿Por qué 2?)

1.  **👮 Billetera PROPIETARIO (Tu Caja Fuerte)**
    *   **Dónde vive**: En tu navegador (MetaMask).
    *   **Función**: Recibe dinero de tu banco/Exchange. Controla todo.
    *   **Seguridad**: Máxima. Nunca entra en el servidor.
2.  **🤖 Billetera BOT (El Obrero)**
    *   **Dónde vive**: En el servidor (código).
    *   **Función**: Ejecuta las operaciones rápidas.
    *   **Seguridad**: Media/Baja. **SOLO le enviamos el dinero justo para trabajar ($20-50).** Si el bot se vuelve loco, solo pierdes eso.

---

## PASO 1: Crear tu "Billetera Propietario" (MetaMask) 🦊
*Si ya tienes MetaMask, salta este paso.*

1.  Ve a [metamask.io](https://metamask.io/) en tu navegador (Chrome/Brave/Edge).
2.  Dale a **"Download"** e instala la (Extensión).
3.  Abre la extensión y dale a **"Crear una cartera nueva"**.
4.  🛑 **MUY IMPORTANTE**: Te dará **12 PALABRAS SECRETAS**.
    *   Escríbelas en un **PAPEL**.
    *   **NUNCA** las guardes en un archivo de texto en el ordenador.
    *   Si pierdes estas palabras, pierdes tu dinero para siempre.
5.  ¡Listo! Ya tienes tu dirección personal (empieza por `0x...`). Cópiala y guárdala.

---

## PASO 2: Generar la "Billetera Bot" 🤖
Vamos a crear una billetera virgen exclusiva para el bot. Lo haremos usando el código que ya tenemos en tu PC.

1.  Abre una terminal en tu PC (PowerShell) en la carpeta del proyecto.
2.  Ejecuta este comando:
    ```powershell
    python generate_wallet.py
    ```
    *(Si no tienes las librerías, instálalas primero: `pip install eth-account`)*
3.  El programa te escupirá algo así:
    ```text
    Address:     0x1234abcd...  <-- ESTA ES LA DIRECCIÓN PÚBLICA DEL BOT
    Private Key: 0x9876fedc...  <-- ESTA ES LA LLAVE MAESTRA DEL BOT
    ```
4.  🛑 **LA PRIVATE KEY ES SECRETA**. Cópiala.

---

## PASO 3: Poner fondos (El flujo de dinero) 💸
Necesitamos meter dinero real (USDC) y "gasolina" (MATIC/POL) en la Billetera del Bot.

**Ruta del dinero:**
`Tu Banco` ➡️ `Exchange (Binance/Coinbase)` ➡️ `Tu MetaMask (Propietario)` ➡️ `Billetera Bot`

### A. Consigue Crypto en un Exchange (Binance/Kraken/Coinbase)
1.  Compra **USDC** (ej. $50).
2.  Compra **POL (antes MATIC)** (ej. $10). *Es necesario para pagar las comisiones de la red Polygon.*

### B. Manda a tu MetaMask
1.  Desde el Exchange, dale a "Retirar" (Withdraw).
2.  Elige la cripto (**USDC**).
3.  **Red (Network)**: Elige **Polygon (MATIC)**. ⚠️ ¡IMPORTANTE! No uses Ethereum (es muy caro).
4.  **Destino**: Pega la dirección de tu **MetaMask (Propietario)**.
5.  Repite lo mismo para el **POL (MATIC)**.

### C. Manda al Bot (La asignación de riesgo)
Ahora tienes el dinero en tu MetaMask. Vamos a darle su "paga" al bot.
1.  Abre MetaMask.
2.  Asegúrate de estar en la red **Polygon Mainnet**.
3.  Dale a **"Enviar"**.
4.  Pega la `Address` de la **Billetera BOT** (la que generaste en el Paso 2).
5.  Envía:
    *   **5 POL** (Para gasolina).
    *   **20 USDC** (Capital de trabajo).

🎉 **Resultado**: Tu bot ahora tiene dinero en la red Polygon.

---

## PASO 4: El Puente a SX Network (El paso avanzado) 🌉
El bot arbitra entre **Polygon** y **SX Network**. Necesitamos dinero en AMBOS lados.
SX Network es una blockchain especial para apuestas.

1.  Ve a [SX Bridge](https://sx.technology/bridge) (o busca el puente oficial de SX).
2.  Conecta tu **MetaMask**.
3.  Selecciona "Bridge from Polygon to SX Network".
4.  Pasa la mitad de tus USDC (ej. 10 USDC) de Polygon a SX Network.
5.  Pasa un poco de POL o ETH para obtener **SX** (el token de gas de esa red). *A veces el puente te da un poco de gas gratis la primera vez.*

**Alternativa Fácil:**
Si esto es muy lío, empieza solo operando en Polygon (aunque el bot perderá oportunidades). Pero para arbitraje real, necesitas las dos.

**Resumen de Saldos Ideales para Test:**
*   **Bot Wallet (Polygon)**: 10 USDC + 2 POL
*   **Bot Wallet (SX Net)**: 10 USDC + 1 SX

---

## PASO 5: Configurar el Bot ⚙️
Hora de conectar el cerebro al dinero.

1.  Entra al servidor:
    ```powershell
    ssh -i "tu-llave.key" ubuntu@IP
    ```
2.  Abre el archivo de configuración:
    ```bash
    nano arbitrage_platform/.env
    ```
3.  Edita estas líneas con los datos de la **Billetera BOT** (Paso 2):
    ```ini
    MODE=LIVE
    PRIVATE_KEY=0x9876fedc... (La clave privada del bot que generaste)
    WALLET_ADDRESS=0x1234abcd... (La dirección pública del bot)
    ```
4.  Guarda (`Ctrl+O`, `Enter`, `Ctrl+X`).

✅ **¡Listo! Tu bot ahora tiene acceso a fondos reales.**
