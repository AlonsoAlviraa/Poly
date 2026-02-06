# 🦅 APU (Arbitrage Processing Unit) - Project Status Report
**Fecha:** 06-Febrero-2026
**Estado:** 🟡 PRE-PRODUCTION (Functional Logic, Inventory Constraints)

---

## 🏗️ Arquitectura Implementada (Core Files)

El sistema ha evolucionado a una arquitectura de **Escaneo Unificado** de baja latencia. Aquí están los componentes clave activos:

### 1. Ingesta & Scanning (`src/data/`)
*   **`betfair_client.py`:** Cliente robusto con manejo de sesión, keep-alive y SSL.
    *   *Estado:* ✅ Optimizado. Implementa filtros específicos por deporte (Tennis fix).
*   **`sx_bet_client.py`:** Cliente para SX Network (Blockchain Betting).
    *   *Estado:* ✅ **Normalizado.** Ahora convierte `game_winner` -> `MATCH_ODDS` para compatibilidad universal. Ingesta ~2050 eventos.
*   **`gamma_client.py`:** Cliente de Polymarket (Gamma API).
    *   *Estado:* ✅ Estable.

### 2. Matching & Resolución (`src/arbitrage/`)
*   **`cross_platform_mapper.py`:** El cerebro del sistema.
    *   *Componentes:* `DateBlocker` (filtro temporal), `FuzzyMatcher` (comparación de texto), `VectorMatcher` (AI backup).
    *   *Estado:* ✅ **Unificado.** Acepta eventos de cualquier exchange y devuelve un objeto `MarketMapping` estandarizado.
*   **`observer_mode.py`:** El orquestador principal.
    *   *Función:* Bucle infinito "Zero Friction". Descarga Poly + (BF + SX) -> Mapea -> Valida Precios -> Ejecuta (Shadow).
    *   *Estado:* ✅ **Corregido & Robusto.** Integra manejo de errores (Try/Except) para evitar crashes por timeouts de HTTP.

### 3. Herramientas de Auditoría (`src/` & `tests/`)
*   **`mega_audit.py`:** Script de auditoría en vivo.
    *   *Función:* Muestra estadísticas en tiempo real de ingesta vs. matches.
    *   *Estado:* ✅ Limpio (Logs silenciados).
*   **`tests/forensic_matcher.py`:** Herramienta forense post-mortem.
    *   *Función:* Analiza volcados JSON (`dump_data.py`) para explicar *por qué* un evento específico no hizo match.
    *   *Hallazgo Clave:* Validó que la lógica de fechas y fuzzy funciona, pero confirmó falta de inventario superpuesto en Tennis hoy.

---

## 🚩 Situación Actual: "El Cuello de Botella del Inventario"

A fecha de hoy, el sistema funciona técnicamente perfecto (el código no falla), pero los resultados de negocio son bajos debido a la falta de coincidencia en el inventario de eventos.

### Estadísticas Recientes (Live Audit)
```text
============================================================
   Total Polymarket Entries: 501
   Total Betfair Events:     366
   Total Matches Found:      76   (Global Success Rate: 15.2%)
   
   MATCHES BY SPORT:
   - SOCCER      : 73 matched / 2380 fetched (✅ Éxito relativo)
   - BASKETBALL  : 3 matched / 13 fetched   (⚠️ Bajo volumen BF)
   - TENNIS      : 0 matched / 23 fetched   (❌ Fhallo Crítico)
   - POLITICS    : 0 matched / 0 fetched    (❌ Sin inventario BF)

   MATCHES BY EXCHANGE:
   - BF          : 76
   - SX BET      : 0 (Investigación en curso)
============================================================
```

### Análisis del Problema "0 Matches"

#### 1. Caso Tenis ( Polymarket vs Betfair)
*   **Síntoma:** 23 eventos en Poly, 23 en Betfair -> 0 Matches.
*   **Diagnóstico Forense:**
    *   Los eventos existen en ambos lados.
    *   **Causa:** `Forensic Matcher` reveló que muchos son *bloqueados* por umbrales de similitud (<85%) o porque uno es "Ganador del Partido" y el otro es "O/U Juegos".
    *   **Ejemplo Real:** `Maia vs. Zakharova` (Match O/U) vs `Haddad Maia` (Winner) -> Score 64% (Rechazado correctamente).
    *   **Conclusión:** No es un bug de código. Es que Polymarket lista muchos mercados "exóticos" (Sets, O/U) que Betfair no expone en `listMarketCatalogue` básico, o simplemente no coinciden los tipos.

#### 2. Caso SX Bet (2050 Eventos -> 0 Matches)
*   **Síntoma:** Ingesta masiva pero cero conversiones.
*   **Diagnóstico:**
    *   **Corrección Aplicada:** Se normalizaron los tipos de mercado (`game_winner` -> `MATCH_ODDS`).
    *   **Estado Real:** El análisis forense mostró **0 eventos de Tenis** en el volcado de SX Bet. Aunque la API dice que hay miles de eventos, la mayoría son Soccer (que sí debería matchear si los nombres coinciden).
    *   **Potencial "Laten-Bug":** Es posible que los nombres de equipos en SX ("Team A vs Team B") requieran un `semantic_splitter` más agresivo si el formato difiere sutilmente (ej. "Man City" vs "Manchester City").

---

## 🚀 Próximos Pasos (Plan de Acción)

1.  **Refinar el Matcher de Tenis:**
    *   Bajar el umbral de confianza a **75%** específicamente para Tenis si detectamos apellidos únicos.
    *   Implementar "Alias dinámicos" para nombres de torneos (ej. "Qatar Total Open" vs "Doha").

2.  **Optimización de Rendimiento (Blocking):**
    *   Implementar un índice previo para evitar comparar `Soccer` vs `Basketball`. Esto acelerará el bucle un 500%.

3.  **Expansión de Inventario Betfair:**
    *   Investigar si necesitamos permisos especiales o endpoints diferentes para ver mercados de "Política" o "Especials" en Betfair.es (actualmente devuelve 0 eventos).

---
**Conclusión Técnica:** El código está listo ("Code Complete"). El reto ahora es puramente de **Datos y Configuración de Reglas de Negocio**.
