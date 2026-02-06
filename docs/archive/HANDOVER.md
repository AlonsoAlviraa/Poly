# Handover & Project Status (Phase 3 Initiation)

This document summarizes the current state of the Poly Sports Arbitrage Bot for the engineering team.

## ✅ Completed Features (Ready for Use)

### 1. Persistent Learning (Task A3)
- **Files**: `src/data/dual_lane_resolver.py`, `src/data/learned_mappings.json`
- **Logic**: The bot now uses a two-tier mapping system. 
    - `mappings.json`: Master read-only file.
    - `learned_mappings.json`: Persistent storage for aliases discovered via LLM during sessions.
- **Benefit**: No more re-asking the LLM for the same team mappings.

### 2. Aggressive Normalization (Task A4)
- **File**: `src/utils/text_utils.py`, `src/arbitrage/sports_matcher.py`
- **Logic**: Centralized utility `clean_entity_name` strips sports suffixes (FC, CF, S.A.D., Esports) and noise tokens.
- **Benefit**: Dramatically increases matching rate without needing LLM calls for variations like "Girona FC" vs "Girona".

### 3. Mega Debugger (AuditLogger)
- **File**: `src/utils/audit_logger.py`
- **Logic**: Full pipeline traceability. Every market evaluation is logged into an HTML report (`debug_reports/`).
- **Benefit**: "Glass Box" system. You can see exactly why a market was rejected (Math, Whitelist, No match).

### 4. Marketplace Expansion
- **Config**: `config/betfair_event_types.py`
- **Updates**: Added **Esports** keywords and **Totals (Over/Under)** mapping support.

---

## 🚀 Work in Progress (Phase 3: Speed & Stealth)

### 1. Stealth Ops (In Progress)
- **File**: `src/utils/stealth_config.py`
- **Status**: Implemented User-Agent rotation and basic browser-like header generation.
- **Next Step**: Implement TLS Fingerprinting (JA3) and proxy rotation middleware.

### 2. WebSockets Migration (Skeleton)
- **File**: `src/data/wss_manager.py`
- **Status**: Created skeletons for `PolyWSSManager` (CLOB) and `BetfairStreamManager`.
- **Next Step**: Connect the `DualArbitrageScanner` to these streams to replace polling.

### 3. Liquidity Gatekeeper (Pending Integration)
- **Target**: `dual_mode_scanner.py`
- **Goal**: Implement a depth filter to ensure at least $500 liquidity in the top 3 levels before reporting an arb.
- **Current Issue**: Need to safely inject `min_liquidity_depth` into the scanner constructor without breaking colleague's recent 1X2 changes.

### 4. Timeseries Database (The Black Box)
- **Requirement**: Install InfluxDB.
- **Goal**: Log every price tick for future backtesting ("What happened on Tuesday nights?").

---

## 🛠 Next Steps for You
1.  **Refactor `dual_mode_scanner.py`**: Fully integrate the `wss_manager.py` to move away from the `while True` sleep cycle.
2.  **Order Book Depth**: Finish the `_check_liquidity_gatekeeper` logic to filter out low-liquidity Esports/NCAA traps.
3.  **InfluxDB Connection**: Create `src/data/price_logger.py` to start pushing data.

"Lo que no es tiempo real, es historia antigua."
