# INFORME TÉCNICO: ARQUITECTURA DEL SISTEMA DE ARBITRAJE AI-HÍBRIDO

**Fecha:** 6 de Febrero, 2026
**Autor:** Antigravity (Lead AI Architect & Data Scientist)
**Versión del Sistema:** 2.1 (Graph-Enhanced Integration)
**Proyecto:** APU (Arbitrage Processing Unit)

---

## 1. RESUMEN EJECUTIVO

Este documento detalla la arquitectura técnica, los flujos de datos y la lógica algorítmica del sistema **APU**, una plataforma avanzada de arbitraje deportivo multi-exchange. A diferencia de los bots de arbitraje convencionales que dependen de reglas estáticas, APU implementa una arquitectura **Híbrida Semántica-Gráfica** que le permite "aprender" y resolver entidades complejas (equipos, jugadores, eventos) a través de múltiples fuentes de datos dispares (Polymarket, SX Bet, Betfair).

El sistema ha evolucionado desde un *simple matcher* a un **Motor de Inteligencia de Grafos (Graph Intelligence Engine)** capaz de detectar oportunidades de arbitraje en la "larga cola" de mercados, resolviendo automáticamente discrepancias de nombres y estructuras mediante algoritmos de detección de comunidades y aliasing semántico.

---

## 2. ARQUITECTURA DE ALTO NIVEL

El sistema sigue un patrón de diseño modular basado en micro-servicios asíncronos (Python `asyncio`), orquestados por un núcleo central.

### Componentes Principales:
1.  **Ingestion Layer (Capa de Ingesta):** Clientes API robustos que normalizan datos de fuentes heterogéneas.
2.  **Normalization & Enrichment Layer:** Normalización semántica dinámica y generación de alias.
3.  **Core Matching Engine (El "Cerebro"):**
    *   *Static Matcher:* Reglas heurísticas rápidas.
    *   *Graph Resolution Engine:* Red neuronal/gráfica para resolver casos complejos.
4.  **Arbitrage & Execution:** Cálculo de oportunidades matemáticas y ejecución de órdenes.
5.  **Memory & Persistence:** Sistema de aprendizaje continuo que almacena mapeos validados.

---

## 3. ANÁLISIS DETALLADO DE COMPONENTES (.PY)

A continuación, se desglosa cada módulo crítico del sistema, explicando su función, lógica interna y rol en la arquitectura global.

### 3.1. `src/mega_audit.py` (El Orquestador)
Este es el punto de entrada principal para el modo de auditoría y descubrimiento.
*   **Función:** Coordina la descarga masiva de datos de Polymarket, SX Bet y Betfair.
*   **Lógica:** Ejecuta un pipeline secuencial: (1) Fetch de Polymarket, (2) Fetch de Exchanges, (3) Invocación del `CrossPlatformMapper`, (4) Análisis de ROIs, y (5) Activación del `GraphResolutionEngine` para eventos huérfanos.
*   **Innovación:** Implementa un sistema de "persistencia al cierre" (`finally block`) que asegura que cualquier conocimiento nuevo adquirido durante la ejecución (vía grafos o AI) se guarde en disco antes de terminar.

### 3.2. `src/arbitrage/cross_platform_mapper.py` (El Enrutador de Mapeo)
El corazón de la lógica de comparación directa.
*   **Función:** Itera sobre cada mercado de Polymarket e intenta encontrar su contraparte en los exchanges.
*   **Lógica:**
    *   Usa "Blocking" (filtrado previo) por deporte y fecha para reducir el espacio de búsqueda.
    *   Delega la comparación detallada a `entity_resolver_logic.py`.
    *   Implementa filtros de seguridad ("Safety Locks") para evitar falsos positivos críticos, como la distinción estricta entre "Illinois" e "Illinois State" (detectada por tokens como 'state', 'tech', 'univ').

### 3.3. `src/arbitrage/entity_resolver_logic.py` (Lógica de Resolución Semántica)
El módulo de inteligencia lingüística y semántica.
*   **Función:** Determina si dos cadenas de texto (e.g., "J. Sinner" y "Jannik Sinner") refieren a la misma entidad.
*   **Innovación - Dynamic Name Normalization:**
    *   No usa listas estáticas interminables. En su lugar, analiza la *estructura* del nombre.
    *   Detecta patrones como "Apellido, Inicial" o "Inicial. Apellido".
    *   Si detecta un match de apellido + compatibilidad de inicial, valida el match sin necesidad de hardcoding.
*   **Semantic Parsers:** Descompone nombres de mercados complejos (e.g., "Celtics vs Lakers - 1st Half Winner") en componentes: `ScrubbedName` (Celtics vs Lakers), `Scope` (1st Half), `Type` (Winner).

### 3.4. `src/data/mining/graph_resolution_engine.py` (Motor de Grafos v2.1)
La "joya de la corona" de la arquitectura reciente.
*   **Concepto:** Transforma el problema de matching de "comparación par-a-par" a un problema de "detección de comunidades en un grafo".
*   **Arquitectura:**
    *   Construye un grafo (usando `networkx`) donde nodos = Eventos y Axones (Edges) = Similitud Híbrida.
    *   **Hybrid Scoring:** Calcula el peso del edge basado en: 70% Overlap de Tokens + 20% Alineación Exacta de Fecha + 10% Contexto.
    *   **Enrichment:** Genera dinámicamente nodos "fantasma" con alias (e.g., "Sinner") para forzar conexiones.
    *   **Hub Pruning:** Usa *Betweenness Centrality* para detectar y cortar nodos "puente" maliciosos (e.g., la palabra "United" conectando equipos distintos).
    *   **Clustering:** Aplica *Greedy Modularity Maximization* para agrupar nodos en comunidades. Todos los nodos en una comunidad se consideran el mismo evento.

### 3.5. `src/data/sx_bet_client.py` (Cliente SX Bet)
El adaptador para el exchange descentralizado SX Bet.
*   **Función:** Interactúa con la API de SX Network.
*   **Desafíos Resueltos:**
    *   *Timestamp Bug:* Corrigió un error crítico donde timestamps en milisegundos se interpretaban como segundos (año 50.000 d.C.), causando invisibilidad de eventos.
    *   *Normalization:* Mapea los `marketKeys` propietarios de SX (e.g., "game_winner") a los estándares internos del sistema (`MATCH_ODDS`), permitiendo que el `CrossPlatformMapper` entienda de qué trata el mercado.

### 3.6. `src/arbitrage/arbitrage_validator.py` (Validador de Estructura)
El policía de calidad del sistema.
*   **Función:** Asegura que, incluso si los nombres coinciden, las *apuestas* sean equivalentes.
*   **Lógica:** Implementa un `MarketSemanticParser`.
    *   Evita que el sistema compare, por ejemplo, "Ganador del Partido" con "Ganador del 1er Cuarto".
    *   Verifica la compatibilidad estructural "profunda" (Scope, Entity, Type).

---

## 4. FLUJO DE DATOS INTELIGENTE (DATA FLOW)

1.  **Harvesting:** `mega_audit.py` despierta a los clientes (`sx_bet_client`, `betfair_client`). Se descargan miles de eventos crudos.
2.  **Standardization:** Los clientes convierten JSONs propietarios a un formato interno unificado (`UnifiedMarket`).
3.  **Level 1 Filtering (Blocking):** Se descartan cruces imposibles (e.g., Tenis con Fútbol, eventos con >24h de diferencia).
4.  **Level 2 Matching (Heurístico):** `entity_resolver_logic` intenta matches directos y rápidos. Si tiene éxito, se marca como `MATCHED` y se calcula ROI.
5.  **Level 3 Orphan Resolution (Graph Engine):**
    *   Todos los eventos NO resueltos se envían al `GraphResolutionEngine`.
    *   El grafo los "digiere", crea enlaces ocultos, detecta comunidades y escupe nuevas *Sugerencias*.
6.  **Persistence Loop:**
    *   Las sugerencias validadas se guardan en `data/learning/graph_suggestions.json`.
    *   El script `ingest_suggestions.py` inyecta estas sugerencias en `entities.json`.
    *   En la **siguiente ejecución**, estos casos complejos son resueltos instantáneamente en el Nivel 2 (Memoria), haciendo el sistema más rápido e inteligente con cada uso.

---

## 5. CONCLUSIÓN Y ESTADO ACTUAL

La arquitectura **APU v2.1** representa un salto cualitativo en tecnología de arbitraje. Al mover la complejidad del "código hardcodeado" a "estructuras de datos dinámicas" (Grafos y Memoria Persistente), hemos logrado:
1.  **Resiliencia:** El sistema se adapta a nuevas variaciones de nombres sin intervención humana.
2.  **Precisión:** La combinación de Graph Pruning y Filtros Semánticos Básicos ha eliminado los falsos positivos (como el caso de "Illinois").
3.  **Escalabilidad:** El enfoque de grafos permite procesar miles de eventos huérfanos en segundos, descubriendo valor en mercados ilíquidos u olvidados.

Este sistema no es solo un bot de trading; es un **motor de descubrimiento de liquidez cruzada**.
