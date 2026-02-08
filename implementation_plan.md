# Mega Implementation Plan: Pivot to Kalshi-Polymarket Arbitrage

## Goal Description
Migrate the existing specialized Sports/Crypto arbitrage infrastructure (**APU**) into a generalized **Event Contract Arbitrage Engine** targeting **Kalshi** (Regulated/US) vs **Polymarket** (DeFi). The goal is to reuse ~80% of the current "Brain" (Graph Resolution, Entity Logic, AI Enrichement) while replacing the data ingestion layer.

## User Review Required
> [!IMPORTANT]
> **Regulatory Barrier**: Kalshi is a CFTC-regulated exchange requiring US KYC. Polymarket is DeFi. Arb execution will require two distinct legal entities or a specific legal setup.
> **Asset Bridge**: Kalshi trades in USD; Polymarket trades in USDC. Real-time P&L will need a FX/Stablecoin peg tracker.

## Proposed Changes

### 1. Ingestion Layer (The Adapter)
#### [NEW] [kalshi_client.py](file:///c:/Users/alons/Desktop/FUTURO/APU/src/data/kalshi_client.py)
*   Implements Kalshi V2 API.
*   Maps Kalshi "Series" and "Markets" to internal `UnifiedMarket` format.
*   Handles Kalshi's limit-order-book structure (LOB) which differs from SX Bet's outcome-based quoting.

#### [MODIFY] [gamma_client.py](file:///c:/Users/alons/Desktop/FUTURO/APU/src/data/gamma_client.py)
*   Add filter for non-sports tags (Politics, Crypto, Econ, Pop Culture).

---

### 2. Matching Engine (The Brain Pivot)
#### [MODIFY] [entity_resolver_logic.py](file:///c:/Users/alons/Desktop/FUTURO/APU/src/arbitrage/entity_resolver_logic.py)
*   Add `politics` and `econ` as first-class citizens in the shard system.
*   Disable sport-specific logic (like "Both Teams to Score") when processing non-sports markets.

#### [MODIFY] [graph_resolution_engine.py](file:///c:/Users/alons/Desktop/FUTURO/APU/src/data/mining/graph_resolution_engine.py)
*   **Version 3.0 Integration**: Pivot the "Hub Pruning" context from teams to "Event Modifiers" (e.g., "Seasonally Adjusted", "Before EOY").

---

### 3. Execution & Risk
#### [NEW] [event_arb_executor.py](file:///c:/Users/alons/Desktop/FUTURO/APU/src/execution/event_arb_executor.py)
*   Handles the dual-path execution (Kalshi API + Polygon Smart Contract).
*   Includes a `USDC_USD_Peg_Guard` to ensure arbitrage isn't eaten by stablecoin slippage.

## Verification Plan

### Automated Tests
*   `tests/test_kalshi_poly_mapping.py`: Verify that "CPI Print" on Kalshi maps to the correct "O/U" on Polymarket using the reuseable `combinatorial_scanner`.
*   Mock Graph Resolution with political figure aliases (Biden/Trump variants).

### Manual Verification
*   Execute a dry-run audit: `python main.py --mode mega-audit --source kalshi` to verify match discovery rate.
