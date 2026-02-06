# 🤖 Polymarket-Betfair Arbitrage Bot

**Sistema de arbitraje cross-platform con optimización AI (Protocolo Hacha)**

## 📊 Estado Actual

| Componente | Progreso | Descripción |
|------------|----------|-------------|
| Core Infrastructure | 85% | CLOB Executor, Smart Router, Circuit Breaker |
| AI/ML Integration | 85% | MiMo-V2-Flash, Semantic Cache, Hacha Protocol |
| Cross-Platform | 60% | Betfair Client, Market Mapper, Shadow Scanner |
| Production | 40% | Docker, Deployment scripts |
| **Tests** | **65/65** | ✅ All passing |

## 🚀 Quick Start

```bash
# 1. Clonar y entrar
cd APU

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar
cp .env.template .env
# Editar .env con tus API keys

# 4. Ejecutar tests
python -m pytest tests/ -v

# 5. Demo del sistema
python -m src.arbitrage.cross_platform_mapper
```

## 🔧 Configuración Requerida

### .env (mínimo necesario)
```env
# Polymarket
PRIVATE_KEY=0x_tu_clave_privada
POLY_KEY=tu_api_key_polymarket

# LLM (OpenRouter)
API_LLM=sk-or-v1-tu_api_key_openrouter

# Betfair (opcional, para cross-platform)
BETFAIR_USER=tu_usuario
BETFAIR_PASS=tu_contraseña
BETFAIR_APP_KEY=tu_app_key
```

## 🎯 Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    POLYMARKET API                           │
│                   (Real-time prices)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 PROTOCOLO "HACHA"                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ Math Filter │──│Semantic Cache│──│ Model Cascade      │ │
│  │ (EV > 0.5%) │  │ (ChromaDB)   │  │ (cheap → primary)  │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
│                                                             │
│  Reduce LLM calls 30-60% sin perder oportunidades          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CROSS-PLATFORM MAPPER                          │
│  ┌─────────────────────┐    ┌─────────────────────────────┐│
│  │ Polymarket Markets  │───▶│ Betfair Events             ││
│  │ "BTC > $100k?"      │    │ ID: 1.123456789            ││
│  └─────────────────────┘    └─────────────────────────────┘│
│                                                             │
│  MiMo-V2-Flash matching (95%+ accuracy, cached 24h)        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    BETFAIR API                              │
│                (⚠️ 15-min delayed - free tier)              │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Estructura de Archivos

```
src/
├── ai/
│   ├── mimo_client.py        # MiMo-V2-Flash via OpenRouter
│   └── hacha_protocol.py     # Protocolo de optimización
├── arbitrage/
│   ├── combinatorial_scanner.py
│   └── cross_platform_mapper.py  # Mapper Poly-Betfair
├── data/
│   ├── gamma_client.py       # Polymarket API
│   └── betfair_client.py     # Betfair Exchange API
└── execution/
    ├── clob_executor.py      # Order execution
    └── smart_router.py       # Multi-leg routing

tests/
├── test_ai_integration.py    # AI tests (11 tests)
├── test_hacha_protocol.py    # Hacha Protocol (19 tests)
└── ...                       # 35 more tests
```

## 🛡️ Protocolo Hacha - Ahorro de Tokens

El sistema usa 3 capas de optimización:

### 1. Filtro Matemático (antes de LLM)
```python
EV_net = (Poly_price - BF_implied) - Gas - Commission(2%)
if EV_net <= 0: skip  # No gasta tokens
```

### 2. Caché Semántica (ChromaDB)
- **Exact match**: Hash MD5, O(1)
- **Semantic match**: Embeddings locales, cosine > 0.90
- **TTL dinámico**: 5min (volatile) → 1h (stable)

### 3. Model Cascading
- **Cheap model**: `.../nous-capybara-7b:free` para checks
- **Primary model**: `xiaomi/mimo-v2-flash` para análisis

**Resultado**: 30-60% menos llamadas a LLM

## 📈 Métricas del Demo

```
╔════════════════════════════════════════════════╗
║ SHADOW MODE ARBITRAGE REPORT                   ║
╠════════════════════════════════════════════════╣
║ Total Scans: 2                                 ║
║ Opportunities Found: 2                         ║
║ Total Theoretical Profit: €3.54                ║
║ Cache Savings: 50%                             ║
║ LLM Tokens Used: 298                           ║
╚════════════════════════════════════════════════╝
```

## 🔐 Betfair: Generar Certificados SSL

1. Ir a [developer.betfair.com](https://developer.betfair.com)
2. Crear Application Key (gratis)
3. Generar Self-Signed Certificate:

```bash
# Generar key
openssl genrsa -out betfair.key 2048

# Generar CSR
openssl req -new -key betfair.key -out betfair.csr

# Generar CRT
openssl x509 -req -days 365 -in betfair.csr -signkey betfair.key -out betfair.crt
```

4. Subir `.crt` a developer.betfair.com
5. Guardar archivos en `./certs/`

## ⚠️ Notas Importantes

1. **Betfair Delay**: Free tier tiene 15 min de retraso. Real-time = €350/mes
2. **Polymarket**: Requiere wallet con fondos en Polygon
3. **LLM Tokens**: ~200 tokens por mapping (con cache hit: 0 tokens)

## 📝 Tareas Pendientes

- [ ] Certificados SSL reales para Betfair
- [ ] Kalshi API integration
- [ ] Execution coordinator
- [ ] Production deployment (Docker)
- [ ] Real-time Betfair (si se paga subscription)

---
*Última actualización: 2026-02-02*
