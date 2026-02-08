# Kalshi Pilot: The Efficiency Optimizer Perspective
## Focus: High-Frequency Economic Arbitrage (HFEA)

### Niche: US Macroeconomic Pulsing
*   **Target Contracts**: Federal Reserve Interest Rate Decisions (Fed Funds Rate), CPI (Consumer Price Index) Prints, Non-Farm Payrolls (NFP), and Weekly Jobless Claims.
*   **Why**: These events have "Instant Resolution Windows" where prices move in milliseconds. The discrepancies between Kalshi's US-regulated limit order book and Polymarket's global liquidity pool are extreme during the first 500ms of a print.

### Implementation Logic (The "Latency-Zero" Path)
1.  **WebSocket-First Ingestion**:
    *   **Kalshi**: Implement the `MarketSnapshot` and `Orderbook` streams via Kalshi API v2 WebSockets. Use high-speed JSON parsers (like `orjson`) to minimize processing overhead.
    *   **Polymarket**: Connect to the Polymarket CLOB via the Polygon-based API. Monitor the `OrderBook` snapshots for the 5-10 specific contracts matching the Kalshi economic series.
2.  **Order Book Mechanics & Fee Optimization**:
    *   **Kalshi LOB Handling**: Kalshi uses a Maker-Taker model. For HFT, we prioritize "Taker" orders (Immediate-or-Cancel) during prints for certainty, but we must factor in the $0.07-$0.12 contract fee.
    *   **Synthetic Liquidity**: If the spread is thin, the bot will act as a Market Maker on Kalshi while hedging with "Taker" orders on Polymarket, capturing the Maker rebate where possible.
3.  **The "First-to-Wire" Execution**:
    *   **Economic Print Trigger**: Direct integration with RSS or specialized data feeds (like Bloomberg/Refinitiv if available, or low-latency web scrapers) to trigger the trade logic the moment the value is released.
    *   **Pre-Signed Transactions**: For Polymarket, use "EIP-712" pre-signed order packets to bypass the local signing latency during the execution burst.

### Reusability Matrix (Legacy -> New)
| Module | Reuse (%) | Adaptation Required |
| :--- | :--- | :--- |
| `combinatorial_scanner` | 90% | Map Kalshi's "Yes/No" series (e.g., 5.25%, 5.50%) to Poly's categorical markets. |
| `vector_matcher` | 80% | Index "Economic Semantic Drift" (e.g., "Basis Points" vs "%"). |
| `gas_estimator` | 100% | Critical for ensuring Polymarket orders land on-chain during high congestion prints. |
| `circuit_breaker` | 100% | Prevents over-exposure if one side fills and the other hangs due to API rate-limit. |

### Advanced Technical Knowledge
*   **Kalshi API-v2 Protobuf**: If using high-frequency, consider the binary serialization support mentioned in developer forums to reduce data size.
*   **Polygon Cluster Deployment**: Deploy the Polymarket-side execution bot in AWS regions (typically us-east-1) closest to the Polygon RPC nodes to minimize "Time-to-Mempool".
