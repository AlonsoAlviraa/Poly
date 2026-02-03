# Walkthrough: Mega Debugger + Ejecución Matemática

Este documento resume el estado actual del **Mega Debugger** y detalla los siguientes pasos para completar la **ejecución matemática** del sistema de arbitraje. Está pensado como guía operativa para avanzar rápido desde el matching hasta la ejecución con control de riesgo y trazabilidad end-to-end.

## 1) Estado actual del Mega Debugger (traceabilidad “glass box”)

### 1.1 Núcleo: `AuditLogger`
El **Mega Debugger** está implementado como `AuditLogger`, que registra eventos por mercado y genera un reporte HTML con el pipeline completo por cada condición escaneada. Esto permite ver el historial de filtros, rechazos y la razón de salida final por mercado. El HTML se guarda en `debug_reports/` y se imprime la ruta al finalizar cuando se habilita el flag `--debug`.【F:src/utils/audit_logger.py†L1-L134】【F:dual_mode_scanner.py†L820-L894】

**Qué registra hoy:**
- `TraceableEvent` por mercado con categoría, pasos y estado final.
- Pasos con status `PASS | FAIL | SKIP`.
- Rechazos y razón final por evento (cuando un paso falla).【F:src/utils/audit_logger.py†L1-L134】

### 1.2 Pasos trazados en el pipeline (matching + math)
Los pasos más importantes ya están instrumentados en el pipeline de matching y cálculo de spread:

**Matching (Sports, LLM + filtros):**
- `Whitelist` → valida categoría vs tags y descarta deportes no viables.
- `PreFilter` → descarta mercados sin candidatos con keywords/overlap.
- `Guardrail` → valida entidades compartidas antes de aceptar un match LLM/híbrido.【F:src/arbitrage/sports_matcher.py†L340-L620】

**Math (spread):**
- `MathCalc` → registra el spread y marca `PASS/FAIL` según `min_spread` configurado.
- Si `--debug-math` está activo, se imprime el detalle de cálculo (precio Poly, odds BF, spread).【F:dual_mode_scanner.py†L456-L531】

### 1.3 Generación del reporte HTML
Si se ejecuta el scanner con `--debug`, se genera automáticamente el informe final del Mega Debugger. El reporte deja todos los pasos ordenados por PASS/FAIL para facilitar el análisis. 【F:dual_mode_scanner.py†L879-L894】

## 2) Cómo usar el Mega Debugger (quick start)

### 2.1 Comando recomendado (sports con LLM + matemáticas)
```bash
python dual_mode_scanner.py --mode sports --use-llm --debug --debug-math
```

### 2.2 Requisitos mínimos
El matcher LLM necesita `API_LLM` en `.env`. Para sports, si se usa Betfair, también se requiere configuración Betfair. 【F:README.md†L23-L69】

## 3) Próximos pasos para ejecución matemática (math → ejecución real)

El sistema ya cuenta con un **Smart Router** que implementa un flujo matemático de pre-flight (VWAP, fees, gating de profit). Para completar la “ejecución matemática” faltan integraciones clave entre el **scanner** y la **capa de ejecución**.

### 3.1 Lo que ya está disponible
El `SmartRouter` calcula:
- VWAP por leg (buy/sell) y valida liquidez.
- Fees de on-chain (estimados) y gating de beneficio mínimo (`min_net_profit`).
- Ejecución en paralelo, con recuperación ante fills parciales. 【F:src/execution/smart_router.py†L1-L195】

### 3.2 Lo que falta conectar (próximos pasos concretos)
1. **Transformar oportunidades en legs ejecutables**
   - Desde `ArbitrageOpportunity` crear `strategy_legs` con `token_id`, `side`, `size`, `limit_price` y `order_book`.
   - Incluir fuente de precios (CLOB vs on-chain) y tipos de leg (`CLOB` o `ON_CHAIN`).【F:src/execution/smart_router.py†L1-L195】

2. **Unificar cálculo matemático**
   - En vez de solo `spread_pct`, calcular `expected_payout` y **net profit** con:
     - Fees CLOB, comisiones Betfair, gas y slippage estimado.
   - El resultado debe alimentar directamente `execute_strategy(...)` del SmartRouter. 【F:dual_mode_scanner.py†L456-L531】【F:src/execution/smart_router.py†L1-L195】

3. **Instrumentar la ejecución en el Mega Debugger**
   - Añadir pasos: `ExecutionGate`, `VWAP`, `Fees`, `Execution`, `Recovery`.
   - Guardar en el `AuditLogger` el net profit real y si se activó recovery.
   - Mantener la trazabilidad completa desde matching → ejecución.

4. **Persistencia y replay**
   - Guardar snapshots (order book + pricing inputs) para replay offline.
   - Esto permite verificar la matemática a posteriori con el mismo dataset.

## 4) Checklist de implementación inmediata

- [ ] Crear un “builder” de legs desde `ArbitrageOpportunity`.
- [ ] Integrar `SmartRouter.execute_strategy()` al final del pipeline.
- [ ] Enriquecer `MathCalc` con net profit y fees reales.
- [ ] Agregar nuevos pasos de ejecución al Mega Debugger.

---
Si quieres, puedo implementar el builder de legs y el gating matemático directamente en el flujo `dual_mode_scanner.py` o crear una capa intermedia `execution_bridge.py` para mantenerlo modular.
