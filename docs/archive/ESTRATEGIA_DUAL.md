# 🎯 ESTRATEGIA DE ARBITRAJE DUAL - RESUMEN EJECUTIVO

## 📍 Problema Original
Tu cuenta de Betfair España está **restringida legalmente a deportes** por la regulación española (DGOJ). No tienes acceso a mercados de Política, Crypto, o Especiales en Betfair.es.

---

## ✅ Solución Implementada: Estrategia Dual

### MODO A: Arbitraje Deportivo 
**Polymarket Sports ↔ Betfair España**

| Componente | Estado | Descripción |
|------------|--------|-------------|
| Betfair España | ✅ Conectado | 1170+ mercados de Soccer, 16+ Basketball |
| Polymarket Sports | ✅ 16+ mercados | World Cup, Super Bowl, NBA, etc. |
| Matching | ✅ LLM Habilitado | MiMo-V2-Flash para matching semántico |

**Mercados Deportivos en Polymarket:**
- 🏈 NFL: Super Bowl MVP, OPOY awards
- ⚽ FIFA World Cup 2026, Premier League, Bundesliga  
- 🏀 NBA: Conference Finals, Coach of Year
- 🏔️ Winter Olympics 2026

### MODO B: Arbitraje Crypto/Politics
**Polymarket ↔ SX Bet (Blockchain Exchange)**

| Componente | Estado | Descripción |
|------------|--------|-------------|
| SX Bet | ✅ Conectado | API funcional, 50+ mercados activos |
| Polymarket | ✅ Conectado | 100+ mercados activos |
| Categorías SX | ⚠️ Limitado | Solo Soccer activo ahora |

---

## 🧠 Matching con LLM (MiMo-V2-Flash)

El scanner ahora incluye matching inteligente usando IA:

```python
# Ejemplo de cómo funciona el matcher
Polymarket: "Will Brazil win the 2026 FIFA World Cup?"
Betfair: "Brazil" (en mercado "World Cup 2026 Winner")

# El LLM entiende que son el mismo evento
→ Match con 85% de confianza
```

**Ventajas del LLM:**
- Entiende variaciones de nombres (Real Madrid = RM = Los Blancos)
- Reconoce formatos de fecha diferentes (2026 vs '26)
- Detecta equivalencias semánticas
- Usa caché para evitar llamadas repetidas ($0.001 por 20 mercados)

---

## 📁 Archivos Creados/Modificados

### Nuevos Archivos:
1. `src/data/sx_bet_client.py` - Cliente completo de SX Bet
2. `src/arbitrage/sports_matcher.py` - **Matcher con LLM** 🆕
3. `dual_mode_scanner.py` - Scanner de arbitraje dual (ahora con --use-llm)
4. `test_sx_categories.py` - Explorador de API SX Bet
5. `test_sx_leagues.py` - Mercados por liga
6. `test_poly_sports.py` - Mercados deportivos Polymarket

### Archivos Modificados:
1. `config/betfair_event_types.py` - Documentación de limitación jurisdiccional
2. `check_mapping_prereqs.py` - Diagnóstico completo con opciones
3. `.env` - Añadido BETFAIR_ENDPOINT=SPAIN

---

## 🚀 Cómo Usar

### Opción 1: Solo Deportes con LLM (Recomendado)
```bash
python dual_mode_scanner.py --mode sports --use-llm --min-spread 0.5
```

### Opción 2: Solo Deportes (keyword matching básico)
```bash
python dual_mode_scanner.py --mode sports --min-spread 1.0
```

### Opción 3: Solo Politics/Entertainment (Poly ↔ SX Bet)
```bash
python dual_mode_scanner.py --mode politics --min-spread 1.0
```

### Opción 4: Ambos Modos con LLM
```bash
python dual_mode_scanner.py --mode both --use-llm
```

### Verificar Prerequisitos
```bash
python check_mapping_prereqs.py
```

---

## 📊 Estado Actual de Mercados (2026-02-03)

| Plataforma | Categoría | Mercados |
|------------|-----------|----------|
| Polymarket | Politics/Crypto | 180 |
| Polymarket | Sports | 20 |
| Betfair.es | Sports | 320 eventos |
| SX Bet | Soccer | 50 (10 con liquidez) |
| SX Bet | Entertainment | 35 (Academy Awards) |
| SX Bet | Politics | 0 (sin eventos activos) |

---

## ⚠️ Limitaciones Conocidas

1. **Formato de mercados diferente**: Polymarket tiene predicciones a largo plazo (ej: "¿Ganará Brasil el Mundial 2026?") vs Betfair que tiene apuestas en partidos individuales
2. **Betfair 15min Delay**: Datos de Betfair tienen 15 min de retraso (tier gratuito)
3. **Politics en SX Bet**: Sin mercados activos ahora (depende de eventos)
4. **Mejor durante eventos grandes**: Las oportunidades aparecen durante eventos importantes

---

## 🔮 Próximos Pasos

- [x] Implementar matching con LLM ✅
- [ ] Añadir Kalshi como tercera plataforma
- [ ] Modo de ejecución real (ahora es shadow/simulación)
- [ ] Alertas de Telegram cuando detecte oportunidades
- [ ] Monitoreo continuo con logging a base de datos

---

*Actualizado: 2026-02-03T00:20*
