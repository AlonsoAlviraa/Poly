# Estado del Sistema APU Dual-Mode y Reporte de Problemas
**Fecha:** 03/02/2026
**Versión:** 2.1 (Hybrid Entity Resolution)

Este documento resume el estado técnico actual del bot de arbitraje, la arquitectura implementada y los problemas críticos que impiden encontrar oportunidades de beneficio.

---

## 1. Arquitectura Actual (Implementada)

El sistema ha evolucionado de un enfoque puramente LLM a un enfoque **Híbrido "Occidental"** centrado en la Resolución de Entidades.

*   **Ingesta de Datos:**
    *   **Polymarket:** Usa `GammaAPIClient` con filtro `tag_id="100639"` (Game Bets) para obtener partidos individuales (~200-300 mercados activos).
    *   **Betfair:** Usa `BetfairClient` (España) con login interactivo. Recupera ~320 eventos deportivos activos.

*   **Motor de Emparejamiento (`SportsMarketMatcher`):**
    1.  **Entity Resolution (Hub & Spoke):** Nueva clase `EntityResolver` carga un JSON estático (`mappings.json`) para normalizar nombres ("Man City" -> "Manchester City").
    2.  **Pre-filtrado:** Busca candidatos en Betfair usando Fuzzy Matching (TheFuzz) y superposición de palabras clave.
    3.  **LLM (MiMo-V2-Flash):** Se usa para confirmar matches semánticos complejos o desambiguar.
    4.  **Guardrail (Mecanismo de Seguridad):**
        *   *Antes:* Rechazaba si no había matches de entidades perfectas.
        *   *Actual:* Usa **Tokenización Agresiva** (Regex) para aceptar matches si comparten tokens fuertes (ej: "Pisa" en "Pisa SC" vs "Verona v Pisa").

---

## 2. Problemas Críticos Identificados

### A. El "Abismo" de las Entidades (Entity Gap)
El problema principal es que **no tenemos un diccionario maestro**.
*   **Síntoma:** El log se llena de `[Matcher] No keyword candidates for: ...`.
*   **Causa:** Polymarket usa nombres completos ("Incarnate Word Cardinals", "Valorant: FUSION"), mientras que Betfair usa nombres cortos o diferentes. Nuestro `mappings.json` tiene ~50 entradas, pero necesitamos miles para cubrir NCAA, Esports y Ligas menores.
*   **Consecuencia:** El bot ignora el 90% de los mercados porque no sabe qué equipos buscar en Betfair.

### B. Limitaciones de Betfair España (Liquidez y Mercados)
*   **Problema:** Estamos escaneando contra **Betfair.es**.
*   **Observación:** Muchos mercados de Polymarket son de deportes de EE.UU. (NCAA Basketball, NBA Player Props) o Esports. Es muy probable que estos mercados **no existan** en Betfair España o tengan liquidez nula.
*   **Riesgo:** Estamos gastando recursos buscando arbitraje en pares que no existen geográficamente.

### C. Eficiencia del Guardrail vs. Falsos Negativos
*   **Problema:** El Guardrail anterior era demasiado estricto (`REJECTED: Spread: Charlton...`).
*   **Estado:** Hemos relajado la lógica para usar intersección de tokens limpios (`len(shared_tokens) >= 1`).
*   **Riesgo:** Esto puede permitir **Falsos Positivos** (ej: emparejar "Madrid" (Real) con "Atletico Madrid" solo por la palabra "Madrid"). Se necesita vigilancia.

### D. Coste Computacional (LLM)
*   **Problema:** A pesar de las optimizaciones, seguimos lanzando peticiones al LLM para "descubrir" matches cuando el filtrado por palabras clave falla.
*   **Mejora:** El uso de `EntityResolver` debería reducir esto, pero solo si el diccionario crece. Si el diccionario está vacío, el sistema recae en fuerza bruta o falla.

---

## 3. Estado de los Componentes

| Componente | Estado | Notas |
| :--- | :---: | :--- |
| **Polymarket Client** | 🟢 OK | Parsea correctamente precios y outcomes (JSON strings). |
| **Betfair Client** | 🟡 Regular | Conexión estable, pero limitado a ES. SSL Login falló, usa Interactive. |
| **Entity Resolver** | 🟢 OK | Lógica implementada. Tokenización agresiva añadida. |
| **Matching Logic** | 🟢 OK | Guardrails relajados y normalización por Regex funcionando. |
| **Arbitrage Calc** | ⚪ Sin Datos | No se ha validado porque no llegan matches aprobados al final del pipeline. |

---

## 4. Próximos Pasos Recomendados

1.  **Expansión Masiva de Mappings:** No podemos escribir el JSON a mano. Necesitamos un script que haga *scraping* de alias o usar una fuente de datos abierta (ej: `openfootball`) para poblar `mappings.json` con miles de equipos.
2.  **Validación de Mercados:** Verificar manualmente si los mercados de Esports/NCAA de Polymarket existen realmente en Betfair ES. Si no, debemos filtrar esos deportes en la entrada para no perder tiempo.
3.  **Test de "Spread Negativo":** Es posible que estemos comparando precios inversos (Back vs Lay) incorrectamente o que el mercado sea eficiente. Necesitamos ver *un* match exitoso, aunque no de beneficio, para validar la matemática.
