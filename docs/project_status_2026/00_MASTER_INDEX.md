
# 📂 FUTURO ARBITRAGE BOT - PROJECT STATUS 2026

**Fecha Actual**: 03/02/2026
**Estado**: 🟢 OPERATIVO (Paper Mode / Real Scanner)

Este directorio contiene toda la documentación relevante del proyecto, consolidada para facilitar la navegación.

## 📌 Punto de Encuentro (Current State)

Hemos logrado estabilizar los cimientos del sistema y ejecutar el **Primer Escaneo Real** conectando Polymarket (CLOB) y Betfair España (Exchange).

### ✅ Logros Recientes
1.  **Conexión Real Cross-Platform**: El bot ya no usa datos "Mock". Se conecta a APIs reales.
2.  **Solución Betfair España**: Detectamos que la API `.es` no tiene política, así que el bot cambia automáticamente a **Deportes** (Fútbol/Tenis).
3.  **Polymarket Hydration**: Solucionado el bug de "0 mercados" implementando una descarga profunda de metadatos (Preguntas/Títulos).
4.  **Estabilidad IA**: Implementado "Fallback Lite" para evitar crashes si el modelo `sentence-transformers` satura la RAM.

### 🚀 Cómo Ejecutar (The Launcher)
El sistema ahora se lanza con un único comando seguro:

```bash
python run_scanner.py
```

---

## 📚 Índice de Documentación

Aquí tienes los documentos clave del proyecto:

### 1. Visión y Estrategia
*   [📄 README.md](./01_README.md) - Visión general y configuración rápida.
*   [📄 ESTRATEGIA_DUAL.md](./02_ESTRATEGIA_DUAL.md) - Explicación de la operativa Híbrida (Polymarket + Betfair).

### 2. Estado Técnico
*   [📄 SYSTEM_STATUS.md](./03_SYSTEM_STATUS.md) - Lista de bugs conocidos y componentes "Green".
*   [📄 ROADMAP.md](./04_ROADMAP.md) - Pasos futuros (Trading Real, Scaling).

### 3. Informes de Ejecución
*   [📄 WALKTHROUGH.md](./05_WALKTHROUGH.md) - Bitácora de los cambios técnicos y pruebas de estrés.
*   [📄 AUDIT_REPORT.md](./06_AUDIT_REPORT.md) - Resultados de la auditoría de seguridad y latencia.

### 4. Histórico
*   [📄 INFORME_COMPLETO.md](./07_INFORME_COMPLETO.md) - Análisis profundo previo.
*   [📄 POST_MORTEM.md](./08_POST_MORTEM.md) - Análisis de fallos antiguos.

---

## 🛠️ Estructura del Código

*   `src/arbitrage/`: Lógica de Mapeo y Escaneo.
*   `src/execution/`: CLOB Client (Polymarket).
*   `src/data/`: Clientes API (Betfair, etc).
*   `tools/`: Scripts de depuración (`debug_auth.py`, `infra_debugger.py`).
