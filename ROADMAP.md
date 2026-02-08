# 🗓️ APU ROADMAP: Kalshi-Polymarket Migration
## Backlog for Feb-Mar 2026
### Last Updated: 2026-02-08

---

## 📊 High-Level Status

| Milestone | Status | Deadline |
|------------|--------|----------|
| **Phase 1: Knowledge Pivot** | ✅ COMPLETE | Feb 08 |
| **Phase 2: Kalshi Ingestion** | 🔵 IN PROGRESS | Feb 12 |
| **Phase 3: Event Matching Logic** | ⏳ PLANNED | Feb 18 |
| **Phase 4: Execution Engine** | ⏳ PLANNED | Feb 25 |
| **Phase 5: Production Go-Live** | ⏳ PLANNED | Mar 05 |

---

## 🚀 PHASE 2: Data Ingestion (Feb 9-12)

### Kalshi API v2 Adapter
- [ ] Implement `KalshiClient` with Protobuf/JSON support.
- [ ] WebSocket streaming for Order Book snapshots.
- [ ] Handle maker-taker fee structures in `unified_price_feed`.

### Polymarket Enrichment
- [ ] Tag-based filtering (Economics, Politics, Science).
- [ ] Historic series recording for macro events.

---

## 🧠 PHASE 3: Advance Matching (Feb 13-18)

### Graph Engine v3.0 Deep Pivot
- [ ] Transition "Team" hubs to "Event" hubs (e.g., "Seasonally Adjusted").
- [ ] Implement **Geographic Voronoi Matching** for weather events.
- [ ] Retrain `ml_match_classifier` for non-sports event pairs.

### Niche Logic Shards
- [ ] **Econ Shard**: Basis points to percentage normalization.
- [ ] **Politics Shard**: Source of Truth verification (AP vs official).

---

## ⚡ PHASE 4: Execution & Risk (Feb 19-25)

### Dual-Platform Arb Executor
- [ ] Atomic-loop for Kalshi (REST) + Polymarket (On-chain).
- [ ] Implement `Stablecoin_USD_Peg_Guard` to protect against drift.

### Risk Management v2
- [ ] Position sizing based on UMA Oracle certainty.
- [ ] Exposure limits per event category.

---

## 🛡️ PHASE 5: Hardening (Feb 26-Mar 5)

### Monitoring & Infrastructure
- [ ] Institutional-grade structured logging.
- [ ] Latency profiling for economic print bursts.
- [ ] Dual-region node deployment (US East for Kalshi, Global for Poly).

---

## 🔧 SUCCESS METRICS
- **Latency**: <50ms end-to-end for HFT Econ prints.
- **Match Accuracy**: >98% for political entity resolution.
- **ROI Target**: >2.5% per event (net of fees).

---
*Last refresh: 2026-02-08*
