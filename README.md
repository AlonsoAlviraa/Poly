# 🦅 APU (Arbitrage Processing Unit) v2.1
**Hybrid Graph-Semantic Arbitrage Engine for Prediction Markets**

APU is an advanced AI-driven system designed to exploit price discrepancies between **Kalshi** (Regulated US Event Contracts) and **Polymarket** (DeFi Prediction Markets). 

It features a high-performance **Graph Resolution Engine** that allows it to bridge the gap between structured regulated data and community-driven decentralized liquidity.

## 📊 Project Status (Pivot Phase)

| Component | Status | Description |
|------------|----------|-------------|
| **Graph Engine v2.1** | ✅ ACTIVE | Cross-entity aliasing and semantic reconciliation |
| **Kalshi Integration** | 🟡 IN PROGRESS | Ingestion layer and order book handling |
| **Polymarket Gamma** | ✅ ACTIVE | Full CLOB support and event grouping |
| **Hacha Protocol** | ✅ ACTIVE | LLM call optimization (30-60% savings) |
| **Niche Support** | ✅ ACTIVE | Economics, Politics, and Climate/Grid markets |

---

## 🚀 Key Strategic Niches

### 1. [Efficiency Optimizer](file:///c:/Users/alons/Desktop/FUTURO/APU/brain/kalshi_efficiency_optimizer.md) (Economic)
- **Focus**: HFT Arbitrage on US Macro Prints (Fed Rate, CPI, NFP).
- **Tech Stack**: Kalshi API v2 WebSockets, EIP-712 pre-signed triggers.

### 2. [Quality Auditor](file:///c:/Users/alons/Desktop/FUTURO/APU/brain/kalshi_quality_auditor.md) (Political)
- **Focus**: High-precision Electoral and Legislative arbitrage.
- **Tech Stack**: Graph Resolution for party/candidate aliasing, UMA Oracle prediction.

### 3. [Integration Architect](file:///c:/Users/alons/Desktop/FUTURO/APU/brain/kalshi_integration_architect.md) (Climate/Grid)
- **Focus**: Multidimensional risk (Hurricanes, Temperature, Sci-Tech).
- **Tech Stack**: Polytope Math, Grid-to-Binary mapping, Voronoi geo-spatial matching.

---

## 🧠 Core Architecture: The "Brain"

### Graph Resolution Engine v2.1
Instead of simple pairwise string matching, APU builds a **knowledge graph** of all active events:
- **Semantic Aliasing**: Automatically creates aliases (e.g., "Jannik Sinner" ↔ "J. Sinner").
- **Hub Pruning**: Uses Betweenness Centrality to ignore generic "hub" terms (e.g., "United", "State") during event matching.
- **Community Detection**: Clusters related contracts using Greedy Modularity Maximization.

### Hacha Protocol (Token Optimization)
1. **Math Filter**: Skips LLM calls if EV is inherently negative or spread is too wide.
2. **Semantic Cache**: Local ChromaDB store for O(1) matching of previously seen entities.
3. **Model Cascade**: Uses cheap local models for initial screening before escalating to MiMo-V2-Flash.

---

## 🛠️ Getting Started

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup Environment
cp .env.template .env
# Fill in your Kalshi and Polymarket credentials

# 3. Run Audit Mode (Intelligence Gathering)
python main.py --mode mega-audit

# 4. Run Live Scanner (Shadow Mode)
python main.py --mode scanner
```

## 📚 Project Documentation

Explore the project's technical depth and roadmap:
- **[Architecture](docs/architecture.md)**: Deep dive into the Graph Resolution Engine and high-level design.
- **[Migration Plan](docs/migration_plan.md)**: The technical roadmap for the Kalshi-Polymarket pivot.
- **[Project Status](docs/project_status.md)**: Current state of the build and recent wins.
- **[Roadmap](docs/roadmap.md)**: Upcoming milestones (Feb-Mar 2026).
- **[Backlog (PRO)](docs/backlog.md)**: Pending high-priority tasks and professional upgrades.
- **[Data Quality](docs/data_quality.md)**: Metrics on entity resolution and logic hardening.
- **[Walkthrough](docs/walkthrough.md)**: A step-by-step summary of the project's evolution.


## 📁 Repository Structure

```
src/
├── ai/
│   ├── mimo_client.py        # High-speed LLM client
│   └── hacha_protocol.py     # Protocolo de optimización
├── arbitrage/
│   ├── cross_platform_mapper.py  # Hybrid Entity Resolver
│   └── combinatorial_scanner.py  # Multi-outcome logic
├── data/
│   ├── kalshi_client.py      # [NEW] Kalshi API v2
│   ├── gamma_client.py       # Polymarket Gamma API
│   └── mining/
│       └── graph_resolution_engine.py # The Graph "Brain"
└── execution/
    └── event_arb_executor.py # [NEW] Dual-exchange execution
```

---

*Contact the Lead AI Architect for API access and institutional credentials.*
