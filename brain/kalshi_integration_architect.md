# Kalshi Pilot: The Integration Architect Perspective
## Focus: Environmental & Structural Grid Arbitrage (ESGA)

### Niche: Cross-Asset Resilience & Climate Matrices
*   **Target Contracts**: Hurricane Landfall (State/County Grids), Daily Temperature Records (O/U 90°F), Rocket Launch Success/Window, and Renewable Energy Generation Peaks.
*   **Why**: These markets are "Multidimensional". A single hurricane can have contracts for "Landfall in Florida", "Strength Category 3+", and "Total Damage > $10B". Polymarket often combines these into complex categorical markets.

### Implementation Logic (The "Systemic" Path)
1.  **Grid-Based Matrix Mapping**:
    *   **The Probability Polytope**: Reuse the `polytope.py` module to ensure "Systemic Coherence". If Kalshi prices Landfall in *Miami* at 40% and *Florida* at 35%, the Polytope check will flag a "Logical Impossibility" (Dutch-book opportunity) across platforms.
    *   **Categorical-to-Binary Conversion**: The architect builds a mapping layer where a 10-outcome "Categorical" market on Polymarket is decomposed into 10 separate "Binary" contracts on Kalshi for 1:1 cross-platform coverage.
2.  **Cross-Asset Hedging & Synthetic Exposure**:
    *   **The Weather-to-Econ Bridge**: Integrate logic to hedge weather contracts on Kalshi against insurance-related equity markets (e.g., reinsurance stocks) or energy futures.
    *   **Delta-Neutral Grids**: Calculate the "Joint Probability" of multiple related events (e.g., Hurricane Landfall AND Power Outage) using the `combinatorial_scanner.py`.
3.  **Institutional-Level Safety (Circuit Breakers)**:
    *   **Regulated Halt Management**: Kalshi, as a CFTC exchange, has specific trading halts during high-volatility events. The `circuit_breaker.py` must prevent the Polymarket-side (which never halts) from becoming unhedged if Kalshi enters a cooling period.

### Reusability Matrix (Legacy -> New)
| Module | Reuse (%) | Adaptation Required |
| :--- | :--- | :--- |
| `polytope` (Math) | 100% | Essential for checking sum-of-probability consistency in climate grids. |
| `combinatorial_scanner` | 95% | Used to identify synthetic "Yes" opportunities across multiple disjoint contracts. |
| `sports_matcher` | 80% | Pivot "Participant" logic to "Geographical Nodes" (e.g., GPS coordinates for landfall). |
| `metrics` | 100% | Track "Drift Between Platforms" as a feature for opportunity scoring. |

### Advanced Technical Knowledge
*   **Geometric Probability Scoring**: For Hurricane landfall, the bot will use a "Voronoi-based" matching system. If Kalshi specifies a landfall radius, the bot calculates the geometric overlap with Polymarket's defined boundaries.
*   **Regulatory API Sync**: Monitor the Kalshi *Regulatory Filing API* to receive automated alerts on new contract approvals by the CFTC, giving the bot a 24-hour head start on mapping before liquidity arrives.
