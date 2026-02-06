# 🗓️ ROADMAP DE MEJORAS TÉCNICAS
## Polymarket Arbitrage Bot - Backlog de 30 Días
### Actualizado: 2026-02-02T13:05

---

## 📊 Estado Actual del Sistema

| Componente | Estado | Última Actualización |
|------------|--------|---------------------|
| Market Discovery | ✅ Corregido | 2026-02-02 |
| Circuit Breaker | ✅ Fail-Closed | 2026-02-02 |
| Multi-Market Arb | ✅ Implementado | 2026-02-02 |
| Orderbook Access | ✅ Funcional | 2026-02-02 |
| Tests | ✅ 35 Passing | 2026-02-02 |
| **Combinatorial Scanner** | ✅ **NUEVO** | 2026-02-02 |
| **NegRisk Detection** | ✅ **NUEVO** | 2026-02-02 |
| **LLM Dependency** | ✅ **NUEVO** | 2026-02-02 |
| **Data Recording** | ✅ **NUEVO** | 2026-02-02 |
| **Backtesting Engine** | ✅ **NUEVO** | 2026-02-02 |
| **Telegram Alerts** | ✅ **NUEVO** | 2026-02-02 |
| **Unified Bot Runner** | ✅ **NUEVO** | 2026-02-02 |

---

## 🎉 NUEVAS IMPLEMENTACIONES (2026-02-02)

### 1. Combinatorial Arbitrage Scanner (`src/arbitrage/combinatorial_scanner.py`)
- Sum-to-One detection across multi-outcome events
- NegRisk arbitrage for N>2 outcomes
- Gamma API integration for event grouping
- LLM-based dependency detection (OpenAI optional)
- Parallel scanning with ThreadPoolExecutor

### 2. Historical Data & Backtesting (`src/data/backtesting.py`)
- SQLite-based market data recording
- Background recording thread
- Replay engine for strategy testing
- Performance metrics (PnL, Sharpe, Win Rate)

### 3. Real-Time Alerts (`src/alerts/telegram_notifier.py`)
- Telegram Bot API integration
- Rate limiting and deduplication
- Priority-based alerting
- Integration with arbitrage scanner

### 4. Unified Bot Runner (`run_arb_bot.py`)
- Multiple modes: scan, monitor, record, full
- CLI arguments for configuration
- Graceful shutdown handling
- Combined component orchestration

---

## 🚀 SEMANA 2 (Feb 9-15): Performance

### Día 8-10: Cache de Matrices Polytope
- [ ] Implementar LRU cache para matrices de constraints
- [ ] Pre-compute common projections
- [ ] Target: <5ms por proyección (actual ~50ms)
- [ ] Benchmark con 100+ mercados

### Día 11-12: Parallel Orderbook Fetching
- [ ] Batch requests para múltiples token_ids
- [ ] Async fetching con `asyncio.gather()`
- [ ] Rate limiting para evitar 429s

### Día 13-15: Latency Optimization
- [ ] Eliminar I/O síncrono del hot path
- [ ] Profile con `cProfile` y `line_profiler`
- [ ] Target: <100ms total cycle time

---

## 🔬 SEMANA 3 (Feb 16-22): Arbitraje Avanzado

### Día 16-18: Cross-Market Scanner
- [x] Implementar `MultiMarketArbitrageDetector`
- [ ] Auto-detectar mercados relacionados por keywords
- [ ] Construir grafo de dependencias lógicas
- [ ] Calcular arbitraje entre "Team wins" vs "Team wins by +10"

### Día 19-21: Constraint Learning
- [ ] Aprender constraints de histórico de precios
- [ ] Detectar correlaciones estadísticas entre mercados
- [ ] Scoring de oportunidades por confianza

### Día 22: Integration Testing
- [ ] End-to-end tests con mercados reales
- [ ] Simular ejecución multi-leg
- [ ] Validate P&L calculations

---

## 📈 SEMANA 4 (Feb 23-Mar 1): Production Hardening

### Día 23-25: Monitoring & Alerts
- [ ] Dashboard con métricas Prometheus
- [ ] Alertas Telegram para oportunidades > 2%
- [ ] Logs estructurados para análisis

### Día 26-28: Risk Management v2
- [ ] Position limits por mercado
- [ ] Correlation-aware sizing
- [ ] Drawdown tracking by strategy

### Día 29-30: Documentation & Handoff
- [ ] Actualizar README.md
- [ ] Documentar APIs internas
- [ ] Runbooks para operaciones

---

## 📋 BACKLOG TÉCNICO DETALLADO

### Módulo: Discovery
| Tarea | Prioridad | Estimación | Estado |
|-------|-----------|------------|--------|
| Integrar GammaClient.get_markets(order_by=volume_24h) | Alta | 2h | ⏳ |
| Filtrar mercados con spread > 5% | Media | 1h | ⏳ |
| Cache de conditionId -> tokenIds | Media | 2h | ⏳ |
| Auto-refresh cada 5 minutos | Baja | 1h | ⏳ |

### Módulo: Execution
| Tarea | Prioridad | Estimación | Estado |
|-------|-----------|------------|--------|
| Órdenes FOK (Fill or Kill) | Alta | 4h | ⏳ |
| Retry con backoff exponencial | Media | 2h | ✅ |
| Multi-leg atomic execution | Alta | 6h | ⏳ |
| Slippage protection | Media | 3h | ✅ |

### Módulo: Math
| Tarea | Prioridad | Estimación | Estado |
|-------|-----------|------------|--------|
| LRU Cache para matrices | Alta | 3h | ⏳ |
| Pre-compute binary market polytopes | Media | 2h | ⏳ |
| Cross-market constraint solver | Alta | 8h | ✅ |
| Numba JIT para hot loops | Baja | 4h | ⏳ |

### Módulo: Risk
| Tarea | Prioridad | Estimación | Estado |
|-------|-----------|------------|--------|
| Heartbeat cada 30s | Alta | 1h | ✅ |
| Balance Type Guard | Crítica | 1h | ✅ |
| Position limits por mercado | Media | 2h | ⏳ |
| Daily PnL tracking | Media | 2h | ⏳ |

---

## 🔧 MÉTRICAS DE ÉXITO

| Métrica | Actual | Target | Deadline |
|---------|--------|--------|----------|
| Latencia por ciclo | ~200ms | <100ms | 2026-02-15 |
| Proyección polytope | ~50ms | <5ms | 2026-02-12 |
| Mercados monitoreados | 10 | 100+ | 2026-02-08 |
| Uptime | 95% | 99.5% | 2026-02-28 |
| Oportunidades detectadas/día | 0 | 10+ | 2026-02-10 |

---

## 🚨 RIESGOS IDENTIFICADOS

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|--------------|------------|
| API Polymarket cambia formato | Alto | Media | Validación de schemas, alertas |
| Liquidez insuficiente | Alto | Alta | Filtrar por volume, slippage checks |
| Rate limiting | Medio | Media | Exponential backoff, caching |
| Latency spikes RPC | Medio | Alta | RPCRacer multi-node |
| Balance sync failure | Alto | Baja | Fail-closed, heartbeat |

---

## 📝 NOTAS DE DESARROLLO

### Decisiones de Arquitectura
1. **Fail-Closed**: Ante duda, asumir peor caso y detener trading
2. **Idempotencia**: Todas las operaciones deben ser seguras de reintentar
3. **Observabilidad**: Logs estructurados, métricas, traces

### Convenciones de Código
- Type hints en todas las funciones públicas
- Docstrings con formato Google
- Tests para cada módulo nuevo
- Max 200 líneas por archivo

---

*Última actualización: 2026-02-02T12:52*
