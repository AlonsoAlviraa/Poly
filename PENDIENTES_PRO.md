# 📊 PENDIENTES PRO: Kalshi-Polymarket Pivot
**Last Updated:** 2026-02-08

---

## 🎯 PRIORIDAD ALTA (Implementación Core)

### 1. Ingesta de Datos (Kalshi)
- [ ] Implementar `kalshi_client.py` base (Auth + Session).
- [ ] Mapeo de `Kalshi.Series` a `Gamma.Event`.
- [ ] Suscripción a WebSockets para OrderBook real-time.
- [ ] Test de latencia: Kalshi vs Polymarket (Shadow).

### 2. Matching de Eventos (Econ/Politics)
- [ ] Configurar `GraphResolutionEngine` para "Niveles de Interés" (Econ).
- [ ] Implementar `bracket_resolver.py` (ej. Kalshi [5.0-5.25] -> Poly [O/U 5.1]).
- [ ] Validar resolución semántica para elecciones (Decision Desk HQ).

### 3. Execution Engine
- [ ] Crear `event_arb_executor.py`.
- [ ] Implementar `PegGuard` para slippage USDC-USD.
- [ ] Integrar `CircuitBreaker` para halts regulatorios de Kalshi.

---

## 🟡 PRIORIDAD MEDIA (Optimización)

### 1. Risk Management v2.1
- [ ] Position sizing basado en la probabilidad de "Resolution Contestation".
- [ ] Matriz de correlación para desastres climáticos (Huracanes).

### 2. HFT & Latency
- [ ] Migrar el `Math Filter` de Hacha Protocol a pre-evaluación en Kalshi.
- [ ] Optimizar el parsing JSON con `msgpack` o `orjson` para el flujo de Kalshi.

---

## 🟢 PRIORIDAD BAJA (Monitoring & UI)

- [ ] Dashboard de arbitraje en tiempo real (Streamlit).
- [ ] Alertas de Telegram específicas para "Large Orders" en Kalshi.
- [ ] Histórico de "P&L Teórico" para backtesting de eventos pasados.

---
**Nota:** El sistema deportivo queda en mantenimiento pasivo. Todo el desarrollo nuevo se centra en esta rama.
