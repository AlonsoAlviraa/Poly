# Kalshi Pilot: The Quality Auditor Perspective
## Focus: High-Precision Political & Legal Arbitrage (HPLA)

### Niche: Geopolitical Integrity & Electoral Margins
*   **Target Contracts**: US Presidential State Margins, Congressional Control (House/Senate), Supreme Court Ruling Outcomes, and EU-Regulation Effective Dates.
*   **Why**: These markets suffer from "Source of Truth Drift". Kalshi might resolve based on the *AP Decision Desk*, while Polymarket might resolve based on *Official State Certification*. This creates a 5-10 day "Exposure Window".

### Implementation Logic (The "Bulletproof" Path)
1.  **Deep Semantic Resolution (DSR)**:
    *   **Graph Linking**: Reuse the `GraphResolutionEngine.py` to cluster political candidates and parties. 
    *   **Contextual Hubs**: Create hubs for "Party Control" where "Democrat" on Kalshi must be semantically linked to "Left-Leaning" or "Blue" on some Polymarket community pools.
    *   **Pruning False Positives**: Block matches where modifiers like "with majority" vs "total seats" exist in the prompt (Audit logic borrowed from the `Illinois Filter`).
2.  **Source of Truth (SoT) Verification**:
    *   **Automated Scrapers**: Link the bot to direct RSS/API feeds from the *Federal Election Commission (FEC)* and *Decision Desk HQ*.
    *   **Resolution Audit Trail**: Use `structured_log.py` to record the *exact* resolution string of the contract on both platforms. If the wording differs by more than 5% (simulated in `forensic_matcher.py`), the bot will calculate a "Probability of Contestation".
3.  **Handling "The Long Tail" of Resolution**:
    *   **Contingency Execution**: Polymarket markets often have a "UMAs (Optimistic Oracle)" resolution process. The Quality Auditor bot will monitor UMA voting patterns to predict if a Polymarket resolution will match Kalshi's regulated certitude.

### Reusability Matrix (Legacy -> New)
| Module | Reuse (%) | Adaptation Required |
| :--- | :--- | :--- |
| `graph_resolution_engine` | 95% | New "Political Aliasing" layer (e.g., "GOP" -> "Republicans"). |
| `ai_mapper` | 85% | Prompt tuning for legal/electoral wording (e.g., "Certification" vs "Decision Desk"). |
| `structured_log` | 100% | Critical for audit-ready transaction history (required for regulated side). |
| `forensic_matcher` | 100% | Essential for analyzing why historical political matches failed during backtest. |

### Advanced Technical Knowledge
*   **Official Citation Parsing**: The bot must parse the "Market Resolution" section of the Kalshi Rulebook (filed with the CFTC). This is the *Legal Anchor* for the audit.
*   **Late-Night Liquidity Handling**: Political markets peak at 3 AM EST during election cycles. The `recovery_handler.py` must stay active to handle network congestion and node failures during these spikes.
