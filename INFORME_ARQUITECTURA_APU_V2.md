# INFORME TÉCNICO: ARQUITECTURA AI-HÍBRIDA v2.1 (Kalshi-Polymarket)

**Fecha:** 8 de Febrero, 2026
**Versión:** 2.1
**Objetivo:** Arbitraje de Eventos Económicos, Políticos y Climáticos.

---

## 1. Visión Holística del Sistema
La arquitectura v2.1 evoluciona desde un matcheador de deportes hacia un **Motor de Grafo de Conocimiento** capaz de reconciliar entidades complejas entre mercados regulados (Kalshi) y descentralizados (Polymarket).

### Flujo de Datos
1.  **Ingesta Dual**: Kalshi (REST/WS) y Polymarket (Gamma API).
2.  **Resolución de Grafos**: El motor construye clústeres de eventos relacionados (ej. "Inflación US", "Tasas Fed").
3.  **Auditoría Semántica**: Protocolo Hacha filtra oportunidades basándose en valor esperado (EV) y caché semántica.
4.  **Ejecución**: Coordinador de órdenes atómicas con protección de slippage y peg.

---

## 2. El Cerebro: Graph Resolution Engine
El corazón de la v2.1 es el enfoque de grafos:
- **Nodos**: Contratos, Entidades (Biden, Fed, Florida), Fechas.
- **Aristas**: Relaciones de similitud y dependencia lógica.
- **Algoritmo**: Modularity Maximization para detectar "Comunidades de Eventos".
- **Hub Pruning**: Eliminación automática de términos genéricos que causan colisiones (ej. "State", "City").

---

## 3. Estrategias de Nicho

### A. Arbitraje Económico (HFT)
Se centra en la ventana de milisegundos tras la publicación de datos macro.
- **Optimización**: Pre-firmado de transacciones Polymarket (EIP-712).
- **Control**: Manejo de brackets numéricos inconsistentes entre plataformas.

### B. Arbitraje Político (Precisión)
Maneja la ambigüedad de nombres en elecciones y legislación.
- **Validación**: Conexión con Decision Desk HQ para verdad fundamental (Ground Truth).
- **Mapeo**: Aliasing dinámico (EOP, POTUS, GOP, Dems).

### C. Arbitraje Climático (Matrices)
Resuelve eventos geográficos mediante mallas y mallas.
- **Matemáticas**: Uso de `polytope.py` para asegurar que las probabilidades de landfall no violen leyes lógicas.
- **Geometría**: Mapeo Voronoi de coordenadas para landfall de huracanes.

---

## 4. Gestión de Riesgos y "Peg Guard"
Dado que operamos en USD (Kalshi) y USDC (Polymarket), la arquitectura incluye:
- **Slippage Protection**: Cancela órdenes si el spread se mueve >0.5% durante el ciclo.
- **Peg Guard**: Bloqueo de ejecución si el USDC se desvía del USD en mercados secundarios.
- **Regulatory Circuit Breakers**: Sincronización con los estados de trading de la CFTC.

---
**Conclusión:** APU v2.1 es un sistema de grado institucional diseñado para absorber la volatilidad informativa y convertirla en arbitraje puro.
